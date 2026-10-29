from __future__ import annotations

import asyncio
from pathlib import Path

from .game_bridge import SaveError, Snapshot, read_snapshot
from .manifest import Manifest
from .persistence import State
from .render import atomic_text, reward_script

POLL_INTERVAL = 0.25


def file_signature(path: Path) -> tuple:
    info = path.stat()
    return (str(path.resolve()), info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class Synchronizer:
    def __init__(self, manifest: Manifest, state: State, output: Path) -> None:
        self.manifest = manifest
        self.state = state
        self.output = output
        self._snapshot_key = None
        self._snapshot = None
        self._exported_script = None
        self._output_key = None

    def write_export(self, text: str) -> None:
        try:
            unchanged = self._output_key == file_signature(self.output)
        except OSError:
            unchanged = False
        if self._exported_script != text or not unchanged:
            atomic_text(self.output, text)
            self._output_key = file_signature(self.output)
            self._exported_script = text

    def invalidate(self) -> None:
        self._snapshot_key = self._snapshot = None
        self.write_export("# Synchronization blocked. Check the EU4 client error log.\n")

    def observe(self, snapshot: Snapshot) -> None:
        m = self.manifest
        if snapshot.country != m.country or m.binding_flag not in snapshot.flags:
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
        if not self.state.checks() <= checks:
            raise SaveError("Previously observed checks disappeared: save rollback detected")
        if m.goal_flag in snapshot.flags:
            if not all(m.charter_flag(n) in snapshot.flags for n in range(m.charters_required)):
                raise SaveError("Goal flag exists without its required Royal Charters")
        if self.state.get("goal") == "1" and m.goal_flag not in snapshot.flags:
            raise SaveError("Previously confirmed goal disappeared: save rollback detected")
        self.state.record_snapshot(checks,
                                   {r[0] for r in self.state.items() if m.item_flag(r[0]) in snapshot.flags},
                                   date, m.goal_flag in snapshot.flags)

    def poll(self, path: Path) -> None:
        try:
            self.export_snapshot(read_snapshot(path, self.manifest.country))
        except (OSError, ValueError):
            # Invalidate an earlier export whenever the current save cannot be trusted.
            self.invalidate()
            raise

    def export_snapshot(self, snapshot: Snapshot) -> None:
        self.observe(snapshot)
        self.write_export(reward_script(self.manifest, self.state.items()))
        self.state.mark_exported()

    async def poll_async(self, path: Path, can_export=lambda: True) -> bool:
        try:
            key = file_signature(path)
            snapshot = self._snapshot
            if key != self._snapshot_key:
                # Parse only new saves, off the GUI/WebSocket thread. Failed or
                # changing reads are never cached as a validated snapshot.
                snapshot = await asyncio.to_thread(read_snapshot, path, self.manifest.country)
                if file_signature(path) != key:
                    raise SaveError("Save changed while reading; retry after writer finishes")
            if not can_export():
                return False
            # All state mutations remain on the event-loop thread.
            self.export_snapshot(snapshot)
            self._snapshot_key, self._snapshot = key, snapshot
            return True
        except (OSError, ValueError):
            self.invalidate()
            raise

    def messages(self, server_checks: set[int]) -> list[dict]:
        self.state.acknowledge(server_checks)
        messages = []
        pending = sorted(self.state.pending_checks())
        if pending:
            messages.append({"cmd": "LocationChecks", "locations": pending})
        if self.state.get("goal") == "1":
            messages.append({"cmd": "StatusUpdate", "status": 30})
        return messages
