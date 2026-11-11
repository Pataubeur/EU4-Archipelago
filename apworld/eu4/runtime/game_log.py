"""Incremental, read-only reader of EU4's logs/game.log (outbound channel).

EU4 truncates game.log at every launch; the file starts with a ``Time:`` header.
A new header or a shrinking file starts a new session from offset 0. Only
complete lines are parsed; a partial last line waits for the next poll.
Lines of another campaign token are ignored and counted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_READ = 64 * 1024 * 1024
HEADER = re.compile(rb"Time:[^\r\n]*")
LINE = re.compile(r"EU4AP (?P<token>[0-9a-f]{24}) (?P<kind>[A-Z_]+)(?: (?P<rest>.*))?$")


@dataclass(frozen=True)
class LogEvent:
    kind: str
    args: tuple[str, ...]
    session: str
    line: int


class GameLog:
    def __init__(self, path: Path, token: str) -> None:
        self.path = path
        self.token = token
        self.session = ""
        self.offset = 0
        self.line = 0
        self.foreign = 0

    def _header(self, data: bytes) -> str:
        match = HEADER.search(data[:4096])
        return match.group().decode("cp1252", errors="replace") if match else ""

    def poll(self) -> list[LogEvent]:
        """New events since the previous poll. Missing file: no event."""
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []
        with self.path.open("rb") as stream:
            head = stream.read(4096)
            header = self._header(head)
            if header != self.session or size < self.offset:
                # New EU4 launch (or a header not yet written): restart this session.
                self.session, self.offset, self.line = header, 0, 0
            if size - self.offset > MAX_READ:
                raise ValueError("game.log is unexpectedly large; restart EU4 to rotate it")
            stream.seek(self.offset)
            data = stream.read(size - self.offset)
        end = data.rfind(b"\n")
        if end < 0:
            return []
        complete = data[:end + 1]
        self.offset += len(complete)
        events = []
        for raw in complete.split(b"\n")[:-1]:
            self.line += 1
            text = raw.decode("cp1252", errors="replace").rstrip("\r")
            index = text.find("EU4AP ")
            if index < 0:
                continue
            match = LINE.match(text[index:])
            if not match:
                continue
            if match.group("token") != self.token:
                self.foreign += 1
                continue
            args = tuple((match.group("rest") or "").split())
            events.append(LogEvent(match.group("kind"), args, self.session, self.line))
        return events
