from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .catalog import ITEM_DEFS, LENGTHS, SAVE_MODES
from .data import country_tag, select_objectives
from .deliveries import START_INVENTORY, attach_deliveries
from .manifest import Manifest
from .locking import ProcessLock
from .persistence import State
from .planner import SlotOptions, plan_slot
from .process import eu4_running
from .render import install_mod
from .synchronization import POLL_INTERVAL, Synchronizer


def offline_manifest(country: str, schema: int, save_mode: str, length: str) -> Manifest:
    if schema == 1:
        return Manifest("OFFLINE-POC", 1, 0, country, tuple(o.id for o in select_objectives(12, True, True)))
    plan = plan_slot(SlotOptions("OFFLINE-POC", 1, country, save_mode=save_mode, campaign_length=length))
    # Offline: every pool item becomes a claimable delivery, as if from the start inventory.
    rows = [(ITEM_DEFS[name].id, 0, START_INVENTORY) for name in plan.items]
    return attach_deliveries(plan.manifest, rows, 0)


async def online(args, sync: Synchronizer) -> None:
    if args.ap_root:
        root = args.ap_root.resolve()
        if not (root / "CommonClient.py").is_file():
            raise ValueError("--ap-root must point to an Archipelago source runtime")
        sys.path.insert(0, str(root))
    # CommonClient handles WebSockets, protocol decoding, authentication and
    # exponential reconnect. We intentionally do not ship an alternate protocol.
    from CommonClient import server_loop
    from .connection import EU4Context

    ctx = EU4Context(sync, args.server, args.name, args.password)
    ctx.run_cli()
    ctx.server_task = asyncio.create_task(server_loop(ctx))
    logger = logging.getLogger("EU4")
    last_status = None
    try:
        while not ctx.exit_event.is_set():
            try:
                await ctx.tick(args.save)
            except (OSError, ValueError) as exc:
                if ctx.sync_error != str(exc):
                    logger.error("synchronization_error: %s", exc)
                ctx.sync_error = str(exc)
            status = ctx.status()
            if status != last_status:
                logger.info(status)
                last_status = status
            try:
                await asyncio.wait_for(ctx.exit_event.wait(), timeout=POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass
    finally:
        await ctx.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EU4 Archipelago experimental save/console client")
    sub = parser.add_subparsers(dest="command", required=True)
    gui = sub.add_parser("gui", help="Open the graphical EU4 client inside an Archipelago runtime")
    gui.add_argument("--ap-root", type=Path)
    poc = sub.add_parser("poc-manifest", help="Create an OFFLINE PoC identity, not an AP-generated seed")
    poc.add_argument("--output", type=Path, required=True)
    poc.add_argument("--country", type=country_tag, default="FRA", help="EU4 tag playable on 1444-11-11")
    poc.add_argument("--schema", type=int, choices=(1, 2), default=2)
    poc.add_argument("--save-mode", choices=SAVE_MODES, default="normal")
    poc.add_argument("--length", choices=LENGTHS, default="standard")
    reward = sub.add_parser("poc-reward", help="Queue one test item; OFFLINE-POC manifests only")
    reward.add_argument("--manifest", type=Path, required=True)
    reward.add_argument("--state", type=Path, required=True)
    reward.add_argument("--item", choices=sorted(ITEM_DEFS), default="100 Ducats")
    codes = sub.add_parser("delivery-codes", help="List live-delivery codes (all, or pending with --state)")
    codes.add_argument("--manifest", type=Path, required=True)
    codes.add_argument("--state", type=Path)
    stage = sub.add_parser("stage-inbox", help="Schema 2: write received items into the mod inbox (EU4 closed)")
    stage.add_argument("--manifest", type=Path, required=True)
    stage.add_argument("--state", type=Path, required=True)
    stage.add_argument("--eu4-user-dir", type=Path, required=True)
    install = sub.add_parser("install-mod", help="Generate the seed-specific mod BEFORE starting EU4")
    install.add_argument("--manifest", type=Path, required=True)
    install.add_argument("--eu4-user-dir", type=Path, required=True)
    for command in ("inspect", "connect"):
        target = sub.add_parser(command)
        target.add_argument("--manifest", type=Path, required=True)
        target.add_argument("--state", type=Path, required=True)
        target.add_argument("--save", type=Path, help="Text save; required for schema 1, optional otherwise")
        target.add_argument("--eu4-user-dir", type=Path, required=True)
        if command == "connect":
            target.add_argument("--server", required=True)
            target.add_argument("--name", required=True, help="AP slot name, not country tag")
            target.add_argument("--password")
            target.add_argument("--ap-root", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s level=%(levelname)s component=%(name)s %(message)s")
    state = None
    lock = None
    try:
        if args.command == "gui":
            if args.ap_root:
                if not (args.ap_root / "CommonClient.py").is_file():
                    raise ValueError("--ap-root must point to an Archipelago source runtime")
                sys.path.insert(0, str(args.ap_root.resolve()))
            from .gui import launch
            launch()
            return 0
        if hasattr(args, "eu4_user_dir"):
            lock = ProcessLock(args.eu4_user_dir / "eu4ap_client.lock")
        if args.command == "poc-manifest":
            offline_manifest(args.country, args.schema, args.save_mode, args.length).write(args.output)
            print(f"Offline manifest written: {args.output}")
        elif args.command == "poc-reward":
            manifest = Manifest.read(args.manifest)
            if manifest.seed != "OFFLINE-POC":
                raise ValueError("Test items are forbidden for AP-generated manifests")
            args.state.parent.mkdir(parents=True, exist_ok=True)
            state = State(args.state, manifest.token)
            state.receive(len(state.items()), [(ITEM_DEFS[args.item].id, -1, 0, 0)])
            print("Offline test item received. Run inspect to export, then run the script in EU4 and save.")
        elif args.command == "delivery-codes":
            manifest = Manifest.read(args.manifest)
            if args.state:
                state = State(args.state, manifest.token)
                rows = Synchronizer(manifest, state, args.state.with_suffix(".unused")).pending_codes()
            else:
                names = {item.id: item.name for item in ITEM_DEFS.values()}
                rows = [(code, names[item]) for code, item, _sender, _location in manifest.deliveries]
                rows += [(code, "DeathLink") for code in manifest.deathlink_codes]
            for code, name in rows:
                print(f"{code}  {name}")
        elif args.command == "stage-inbox":
            manifest = Manifest.read(args.manifest)
            if manifest.schema != 2:
                raise ValueError("stage-inbox requires a schema 2 manifest")
            state = State(args.state, manifest.token)
            sync = Synchronizer(manifest, state, args.eu4_user_dir / "eu4ap_sync.txt",
                                user_dir=args.eu4_user_dir, eu4_running=eu4_running)
            if eu4_running():
                raise ValueError("EU4 is running: close it before changing the mod inbox")
            print("Inbox updated" if sync.stage_inbox() else "Inbox already up to date")
        elif args.command == "install-mod":
            print(install_mod(Manifest.read(args.manifest), args.eu4_user_dir))
            print("Enable this mod in the launcher; select the configured tag and bind using its decision.")
        else:
            manifest = Manifest.read(args.manifest)
            args.state.parent.mkdir(parents=True, exist_ok=True)
            state = State(args.state, manifest.token)
            v2 = manifest.schema == 2
            if not v2 and not args.save:
                raise ValueError("--save is required for schema 1 manifests")
            if v2 and manifest.save_mode == "ironman":
                args.save = None
            sync = Synchronizer(manifest, state, args.eu4_user_dir / "eu4ap_sync.txt",
                                log_path=args.eu4_user_dir / "logs" / "game.log" if v2 else None,
                                user_dir=args.eu4_user_dir if v2 else None)
            if args.command == "inspect":
                if v2:
                    asyncio.run(sync.poll_async(args.save))
                else:
                    sync.poll(args.save)
                print(json.dumps({"checks": sorted(state.checks()), "items": state.items(),
                                  "goal": state.get("goal") == "1", "warning": sync.warning}, indent=2))
            else:
                handler = logging.FileHandler(args.state.with_suffix(".log"), encoding="utf-8")
                handler.setFormatter(logging.Formatter("%(asctime)s level=%(levelname)s component=%(name)s %(message)s"))
                logging.getLogger().addHandler(handler)
                asyncio.run(online(args, sync))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        logging.getLogger("EU4").error("startup_error: %s", exc)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if state:
            state.close()
        if lock:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
