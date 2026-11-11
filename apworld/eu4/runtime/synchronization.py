from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Callable

from .game_bridge import SaveError, Snapshot, read_snapshot
from .deliveries import match_deliveries
from .game_log import GameLog, LogEvent
from .manifest import Manifest
from .persistence import State
from .render import atomic_text, sync_script, write_inbox

POLL_INTERVAL = 0.25
STAGE_INTERVAL = 3.0       # Seconds between EU4 process checks for inbox staging.
TICK_TOLERANCE = 1         # Ironman: a crash may return to an autosave up to a year old.
DEATH_MEMORY = 200


def file_signature(path: Path) -> tuple:
    info = path.stat()
    return (str(path.resolve()), info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class Synchronizer:
    """Schema 1: save polling and console file (unchanged contract).

    Schema 2 adds game.log (checks, applied items, goal, DeathLink), the mod inbox
    rewritten while EU4 is closed, and optional save polling in normal mode.
    """

    def __init__(self, manifest: Manifest, state: State, output: Path, log_path: Path | None = None,
                 user_dir: Path | None = None, eu4_running: Callable[[], bool] | None = None) -> None:
        self.manifest = manifest
        self.state = state
        self.output = output
        self.v2 = manifest.schema == 2
        self.log = GameLog(log_path, manifest.token) if self.v2 and log_path else None
        self.user_dir = user_dir
        if eu4_running is None:
            from .process import eu4_running
        self.eu4_running = eu4_running
        self.warning = ""
        self.claim_warning = ""
        self.deaths: list[str] = []
        self._snapshot_key = None
        self._snapshot = None
        self._exported_script = None
        self._output_key = None
        self._last_stage = float("-inf")

    # ------------------------------------------------------------ console export

    def deathlinks_received(self) -> int:
        return int(self.state.get("deathlinks_in") or 0)

    def receive_deathlink(self) -> None:
        self.state.set("deathlinks_in", str(self.deathlinks_received() + 1))

    def script(self) -> str:
        return sync_script(self.manifest, self.state.items(), self.deathlinks_received())

    def write_export(self, text: str) -> None:
        try:
            unchanged = self._output_key == file_signature(self.output)
        except OSError:
            unchanged = False
        if self._exported_script != text or not unchanged:
            atomic_text(self.output, text)
            self._output_key = file_signature(self.output)
            self._exported_script = text

    def export(self) -> None:
        self.write_export(self.script())
        if not (self.v2 and self.manifest.save_mode == "ironman"):
            self.state.mark_exported()

    def invalidate(self) -> None:
        self._snapshot_key = self._snapshot = None
        self.write_export("# Synchronization blocked. Check the EU4 client error log.\n")

    # ------------------------------------------------------------------ saves

    def observe(self, snapshot: Snapshot) -> None:
        m = self.manifest
        if m.binding_flag not in snapshot.flags or (not self.v2 and snapshot.country != m.country):
            raise SaveError("Save is not bound to this seed/team/slot/country/configuration")
        bindings = {f for f in snapshot.flags if f.startswith("eu4ap_seed_")}
        if bindings != {m.binding_flag}:
            raise SaveError("Multiple seed bindings detected; restore an unmodified campaign")
        prior = self.state.get("save_date")
        date = ".".join(map(str, snapshot.date))
        if prior and snapshot.date < tuple(map(int, prior.split("."))):
            raise SaveError("Save date moved backwards; restore the latest synchronized save")
        for index, _item, _loc, _player, _flags, status in self.state.items():
            if status == "confirmed" and m.item_flag(index) not in snapshot.flags:
                raise SaveError("Confirmed reward disappeared: save rollback or incompatible campaign")
        checks = {i for i in m.locations if m.check_flag(i) in snapshot.flags}
        # Schema 2 also learns checks from game.log, before any save: compare saves with saves.
        previous = set(json.loads(self.state.get("save_checks") or "[]")) if self.v2 else self.state.checks()
        if not previous <= checks:
            raise SaveError("Previously observed checks disappeared: save rollback detected")
        goal = m.goal_flag in snapshot.flags
        if goal:
            required = ([m.ambition_flag] if self.v2 else
                        [m.charter_flag(n) for n in range(m.charters_required)])
            if not all(flag in snapshot.flags for flag in required):
                raise SaveError("Goal flag exists without its required native flags")
        prior_goal = self.state.get("save_goal" if self.v2 else "goal") == "1"
        if prior_goal and not goal:
            raise SaveError("Previously confirmed goal disappeared: save rollback detected")
        self.state.record_snapshot(checks,
                                   {r[0] for r in self.state.items() if m.item_flag(r[0]) in snapshot.flags},
                                   date, goal)
        if self.v2:
            self.state.set("save_checks", json.dumps(sorted(previous | checks)))
            if goal:
                self.state.set("save_goal", "1")

    def binding(self) -> str | None:
        return self.manifest.binding_flag if self.v2 else None

    def poll(self, path: Path) -> None:
        try:
            self.export_snapshot(read_snapshot(path, self.manifest.country, self.binding()))
        except (OSError, ValueError):
            # Invalidate an earlier export whenever the current save cannot be trusted.
            self.invalidate()
            raise

    def export_snapshot(self, snapshot: Snapshot) -> None:
        self.observe(snapshot)
        self.export()

    async def _read_save(self, path: Path):
        key = file_signature(path)
        snapshot = self._snapshot
        if key != self._snapshot_key:
            # Parse only new saves, off the GUI/WebSocket thread. Failed or
            # changing reads are never cached as a validated snapshot.
            arguments = (path, self.manifest.country) + ((self.binding(),) if self.v2 else ())
            snapshot = await asyncio.to_thread(read_snapshot, *arguments)
            if file_signature(path) != key:
                raise SaveError("Save changed while reading; retry after writer finishes")
        return key, snapshot

    async def poll_async(self, path: Path, can_export=lambda: True) -> bool:
        if self.v2:
            return await self.poll_v2_async(path, can_export)
        try:
            key, snapshot = await self._read_save(path)
            if not can_export():
                return False
            # All state mutations remain on the event-loop thread.
            self.export_snapshot(snapshot)
            self._snapshot_key, self._snapshot = key, snapshot
            return True
        except (OSError, ValueError):
            self.invalidate()
            raise

    # --------------------------------------------------------------- schema 2

    # ------------------------------------------------------- live deliveries

    def codes(self) -> dict[int, int]:
        """Received item index -> live-delivery code."""
        return match_deliveries(self.manifest, self.state.items())

    def claimed(self) -> set[int]:
        return set(json.loads(self.state.get("claimed_codes") or "[]"))

    def pending_codes(self) -> list[tuple[int, str]]:
        """Codes the player can enter in game now: received, not yet applied."""
        from .catalog import ITEM_DEF_BY_ID
        rows = {row[0]: row for row in self.state.items()}
        result = [(code, ITEM_DEF_BY_ID[rows[index][1]].name) for index, code in sorted(self.codes().items())
                  if rows[index][-1] not in ("applied", "confirmed")]
        claimed = self.claimed()
        for k in range(min(self.deathlinks_received(), len(self.manifest.deathlink_codes))):
            if self.manifest.deathlink_codes[k] not in claimed:
                result.append((self.manifest.deathlink_codes[k], "DeathLink"))
        return result

    def _observe_claims(self, claims: list[str]) -> set[int]:
        """Audit CLAIM lines; returns item indices now applied. A claim before the
        server delivered the item is remembered and honoured on arrival."""
        m = self.manifest
        valid = {row[0] for row in m.deliveries} | set(m.deathlink_codes)
        claimed = self.claimed()
        for code in claims:
            if code not in valid:
                continue
            claimed.add(code)
        by_code = {code: index for index, code in self.codes().items()}
        received_dl = set(m.deathlink_codes[:self.deathlinks_received()])
        unreceived = [code for code in sorted(claimed) if code not in by_code and code not in received_dl]
        self.claim_warning = (f"Livraisons réclamées en jeu sans avoir été reçues : {unreceived} "
                              "(code erroné ou anticipé ; appliquées sans contrepartie)." if unreceived else "")
        if claimed != self.claimed():
            self.state.set("claimed_codes", json.dumps(sorted(claimed)))
        return {by_code[code] for code in claimed if code in by_code}

    def observe_log(self, events: list[LogEvent]) -> None:
        m = self.manifest
        checks, applied, goal = set(), set(), False
        claims: list[int] = []
        seen = json.loads(self.state.get("death_seen") or "[]")
        for event in events:
            first = event.args[0] if event.args else ""
            if event.kind == "CHECK" and first.isdecimal() and int(first) in m.locations:
                checks.add(int(first))
            elif event.kind == "ITEM" and first.isdecimal():
                applied.add(int(first))
            elif event.kind == "CLAIM" and first.isdecimal():
                claims.append(int(first))
            elif event.kind == "CLAIM_UNKNOWN":
                self.warning = f"Code de livraison inconnu saisi en jeu ({first.split('.')[0]}) : vérifiez le code."
            elif event.kind == "CLAIM_EARLY":
                self.warning = f"Le piège {first} ne s'applique qu'à partir de 1450 : saisissez-le de nouveau plus tard."
            elif event.kind == "GOAL":
                goal = True
            elif event.kind == "HELLO" and len(event.args) >= 2:
                mode = event.args[1]
                self.state.set("detected_mode", mode)
                if mode != m.save_mode:
                    self.warning = (f"La partie EU4 est en mode {mode}, le manifeste prévoit {m.save_mode} : "
                                    "la logique (pièges, délais) suppose l'autre mode.")
            elif event.kind == "TICK" and first.isdecimal():
                self._observe_tick(int(first), event.session)
            elif event.kind == "DEATH":
                key = f"{event.session}|{event.line}"
                if key not in seen:
                    seen.append(key)
                    self.deaths.append(first)
        known = len(self.state.items())
        applied |= self._observe_claims(claims)
        if checks:
            self.state.observe_checks(checks)
        if applied:
            self.state.mark_applied({i for i in applied if i < known})
        if goal:
            self.state.set("goal", "1")
        if self.deaths:
            self.state.set("death_seen", json.dumps(seen[-DEATH_MEMORY:]))

    def _observe_tick(self, year: int, session: str) -> None:
        highest = int(self.state.get("log_year") or 0)
        if self.state.get("log_session") != session:
            self.state.set("log_session", session)
            if highest and year < highest - TICK_TOLERANCE:
                # Informative only: items repair themselves and AP checks are monotonic.
                self.warning = (f"Date de jeu revenue de {highest} à {year} : sauvegarde plus ancienne "
                                "chargée. Les objets manquants seront réappliqués automatiquement.")
        if year > highest:
            self.state.set("log_year", str(year))

    def stage_inbox(self) -> bool:
        """Install every received item into the mod inbox while EU4 is closed."""
        if self.user_dir is None or self.eu4_running():
            return False
        items = self.state.items()
        changed = write_inbox(self.manifest, self.user_dir, items, self.deathlinks_received())
        self.state.mark_staged({row[0] for row in items})
        return changed

    async def poll_v2_async(self, save_path: Path | None, can_export=lambda: True) -> bool:
        events = await asyncio.to_thread(self.log.poll) if self.log else []
        if not can_export():
            return False
        self.observe_log(events)
        if self.manifest.save_mode == "normal" and save_path and Path(save_path).is_file():
            try:
                key, snapshot = await self._read_save(Path(save_path))
                self.observe(snapshot)
                self._snapshot_key, self._snapshot = key, snapshot
            except (OSError, ValueError):
                self.invalidate()
                raise
        self.export()
        now = time.monotonic()
        if self.user_dir is not None and now - self._last_stage >= STAGE_INTERVAL:
            self._last_stage = now
            if not await asyncio.to_thread(self.eu4_running):
                self.stage_inbox()
        return True

    def status_warning(self) -> str:
        return "\n".join(w for w in (self.warning, self.claim_warning) if w)

    def take_deaths(self) -> list[str]:
        deaths, self.deaths = self.deaths, []
        return deaths

    def counts(self) -> dict[str, int]:
        rows = self.state.items()
        return {status: sum(r[-1] == status for r in rows)
                for status in ("received", "pending", "staged", "applied", "confirmed")}

    def messages(self, server_checks: set[int]) -> list[dict]:
        self.state.acknowledge(server_checks)
        messages = []
        pending = sorted(self.state.pending_checks())
        if pending:
            messages.append({"cmd": "LocationChecks", "locations": pending})
        if self.state.get("goal") == "1":
            messages.append({"cmd": "StatusUpdate", "status": 30})
        return messages
