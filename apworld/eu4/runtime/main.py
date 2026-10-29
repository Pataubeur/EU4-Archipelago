from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .data import ITEMS, country_tag, select_objectives
from .manifest import Manifest
from .locking import ProcessLock
from .persistence import State
from .render import install_mod
from .synchronization import POLL_INTERVAL, Synchronizer


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
    reward = sub.add_parser("poc-reward", help="Queue one test item; OFFLINE-POC manifests only")
    reward.add_argument("--manifest", type=Path, required=True)
    reward.add_argument("--state", type=Path, required=True)
    reward.add_argument("--item", choices=list(ITEMS), default="100 Ducats")
    install = sub.add_parser("install-mod", help="Generate the seed-specific mod BEFORE starting EU4")
    install.add_argument("--manifest", type=Path, required=True)
    install.add_argument("--eu4-user-dir", type=Path, required=True)
    for command in ("inspect", "connect"):
        target = sub.add_parser(command)
        target.add_argument("--manifest", type=Path, required=True)
        target.add_argument("--state", type=Path, required=True)
        target.add_argument("--save", type=Path, required=True)
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
            Manifest("OFFLINE-POC", 1, 0, args.country,
                     tuple(o.id for o in select_objectives(12, True, True))).write(args.output)
            print(f"Offline manifest written: {args.output}")
        elif args.command == "poc-reward":
            manifest = Manifest.read(args.manifest)
            if manifest.seed != "OFFLINE-POC":
                raise ValueError("Test items are forbidden for AP-generated manifests")
            args.state.parent.mkdir(parents=True, exist_ok=True)
            state = State(args.state, manifest.token)
            state.receive(len(state.items()), [(ITEMS[args.item][0], -1, 0, 0)])
            print("Offline test item received. Run inspect to export, then run the script in EU4 and save.")
        elif args.command == "install-mod":
            print(install_mod(Manifest.read(args.manifest), args.eu4_user_dir))
            print("Enable this mod in the launcher; select the configured tag and bind using its decision.")
        else:
            manifest = Manifest.read(args.manifest)
            args.state.parent.mkdir(parents=True, exist_ok=True)
            state = State(args.state, manifest.token)
            sync = Synchronizer(manifest, state, args.eu4_user_dir / "eu4ap_sync.txt")
            if args.command == "inspect":
                sync.poll(args.save)
                print(json.dumps({"checks": sorted(state.checks()), "items": state.items(),
                                  "goal": state.get("goal") == "1"}, indent=2))
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
