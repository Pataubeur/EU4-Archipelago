"""SQLite transactions retain received/pending/confirmed state across crashes."""
from __future__ import annotations

from pathlib import Path


class ItemGapError(ValueError):
    pass


class State:
    def __init__(self, path: Path, token: str) -> None:
        import sqlite3
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS items (
                idx INTEGER PRIMARY KEY, item INTEGER NOT NULL, location INTEGER NOT NULL,
                player INTEGER NOT NULL, flags INTEGER NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS checks (id INTEGER PRIMARY KEY, acknowledged INTEGER NOT NULL DEFAULT 0);
        """)
        existing = self.get("token")
        if existing and existing != token:
            self.db.close()
            raise ValueError("State database belongs to a different seed/slot/configuration")
        self.set("token", token)

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    def receive(self, start: int, values: list[tuple[int, int, int, int]]) -> None:
        if start < 0:
            raise ValueError("Negative item index")
        known = self.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if start > known:
            raise ItemGapError("Item stream gap; waiting for CommonClient Sync replay")
        with self.db:
            for index, value in enumerate(values, start):
                old = self.db.execute("SELECT item,location,player,flags FROM items WHERE idx=?", (index,)).fetchone()
                if old is not None and old != tuple(value):
                    raise ValueError(f"Conflicting item replay at index {index}")
                self.db.execute("INSERT OR IGNORE INTO items VALUES (?, ?, ?, ?, ?, 'received')", (index, *value))

    def items(self) -> list[tuple[int, int, int, int, int, str]]:
        return self.db.execute("SELECT * FROM items ORDER BY idx").fetchall()

    def checks(self) -> set[int]:
        return {row[0] for row in self.db.execute("SELECT id FROM checks")}

    def observe_checks(self, ids: set[int]) -> None:
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO checks(id) VALUES (?)", [(i,) for i in ids])

    def acknowledge(self, ids: set[int]) -> None:
        with self.db:
            # The current server view is authoritative. If a server restores an
            # older apsave, resend local checks rather than trusting stale ACKs.
            self.db.execute("UPDATE checks SET acknowledged=0")
            self.db.executemany("UPDATE checks SET acknowledged=1 WHERE id=?", [(i,) for i in ids])

    def pending_checks(self) -> set[int]:
        return {r[0] for r in self.db.execute("SELECT id FROM checks WHERE acknowledged=0")}

    def confirm(self, indices: set[int]) -> None:
        with self.db:
            self.db.executemany("UPDATE items SET status='confirmed' WHERE idx=?", [(i,) for i in indices])

    def record_snapshot(self, checks: set[int], confirmed: set[int], date: str, goal: bool) -> None:
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO checks(id) VALUES (?)", [(i,) for i in checks])
            self.db.executemany("UPDATE items SET status='confirmed' WHERE idx=?", [(i,) for i in confirmed])
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('save_date', ?)", (date,))
            if goal:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('goal', '1')")

    def mark_exported(self) -> None:
        with self.db:
            self.db.execute("UPDATE items SET status='pending' WHERE status='received'")

    def close(self) -> None:
        self.db.close()
