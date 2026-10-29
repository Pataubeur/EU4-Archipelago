"""Atomic campaign state for AP's frozen runtime, which does not ship SQLite."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .persistence import ItemGapError
from .render import atomic_text


class JsonState:
    def __init__(self, path: Path, token: str) -> None:
        self.path = path
        self.data = {"schema": 1, "meta": {"token": token}, "items": [], "checks": {}}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("schema") != 1
                    or not isinstance(data.get("meta"), dict)
                    or not isinstance(data.get("items"), list)
                    or not isinstance(data.get("checks"), dict)):
                raise ValueError("Invalid campaign state; restore the original state file")
            if data["meta"].get("token") != token:
                raise ValueError("State database belongs to a different seed/slot/configuration")
            if any(not isinstance(k, str) or not isinstance(v, str) for k, v in data["meta"].items()):
                raise ValueError("Invalid campaign metadata")
            for index, row in enumerate(data["items"]):
                if (not isinstance(row, list) or len(row) != 6 or row[0] != index
                        or not all(type(v) is int for v in row[:5])
                        or row[-1] not in ("received", "pending", "confirmed")):
                    raise ValueError("Invalid campaign item state")
            if any(not k.isdecimal() or type(v) is not bool for k, v in data["checks"].items()):
                raise ValueError("Invalid campaign check state")
            self.data = data
        else:
            atomic_text(path, json.dumps(self.data, indent=2) + "\n")

    def _change(self, change) -> None:
        updated = deepcopy(self.data)
        change(updated)
        if updated != self.data:
            atomic_text(self.path, json.dumps(updated, indent=2) + "\n")
            self.data = updated

    def get(self, key: str) -> str | None:
        return self.data["meta"].get(key)

    def set(self, key: str, value: str) -> None:
        self._change(lambda data: data["meta"].__setitem__(key, value))

    def receive(self, start: int, values: list[tuple[int, int, int, int]]) -> None:
        if start < 0:
            raise ValueError("Negative item index")
        if start > len(self.data["items"]):
            raise ItemGapError("Item stream gap; waiting for CommonClient Sync replay")

        def change(data):
            for index, value in enumerate(values, start):
                if index < len(data["items"]):
                    if tuple(data["items"][index][1:5]) != tuple(value):
                        raise ValueError(f"Conflicting item replay at index {index}")
                else:
                    data["items"].append([index, *value, "received"])
        self._change(change)

    def items(self) -> list[tuple]:
        return [tuple(row) for row in self.data["items"]]

    def checks(self) -> set[int]:
        return {int(key) for key in self.data["checks"]}

    def observe_checks(self, ids: set[int]) -> None:
        def change(data):
            for value in ids:
                data["checks"].setdefault(str(value), False)
        self._change(change)

    def acknowledge(self, ids: set[int]) -> None:
        self._change(lambda data: data.__setitem__("checks", {k: int(k) in ids for k in data["checks"]}))

    def pending_checks(self) -> set[int]:
        return {int(key) for key, acknowledged in self.data["checks"].items() if not acknowledged}

    def confirm(self, indices: set[int]) -> None:
        def change(data):
            for row in data["items"]:
                if row[0] in indices:
                    row[-1] = "confirmed"
        self._change(change)

    def record_snapshot(self, checks: set[int], confirmed: set[int], date: str, goal: bool) -> None:
        def change(data):
            for value in checks:
                data["checks"].setdefault(str(value), False)
            for row in data["items"]:
                if row[0] in confirmed:
                    row[-1] = "confirmed"
            data["meta"]["save_date"] = date
            if goal:
                data["meta"]["goal"] = "1"
        self._change(change)

    def mark_exported(self) -> None:
        def change(data):
            for row in data["items"]:
                if row[-1] == "received":
                    row[-1] = "pending"
        self._change(change)

    def close(self) -> None:
        pass  # Every change is flushed and atomically replaced before it returns.
