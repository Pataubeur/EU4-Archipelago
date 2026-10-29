"""Read-only, bounded EU4 text save parser. Never edits a game's save."""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

MAX_SAVE = 256 * 1024 * 1024
TOKEN = re.compile(r'\s+|#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')


class SaveError(ValueError):
    pass


@dataclass(frozen=True)
class Snapshot:
    date: tuple[int, int, int]
    country: str
    flags: frozenset[str]


def _tokens(text: str):
    for match in TOKEN.finditer(text):
        value = match.group()
        if not value.isspace() and not value.startswith("#"):
            yield value


def parse_save(raw: bytes, country: str) -> Snapshot:
    if len(raw) > MAX_SAVE:
        raise SaveError("Save exceeds size limit")
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entry = archive.getinfo("gamestate")
                if entry.file_size > MAX_SAVE:
                    raise SaveError("Expanded save exceeds size limit")
                raw = archive.read(entry)
        except (KeyError, zipfile.BadZipFile, RuntimeError) as exc:
            raise SaveError("Invalid compressed save") from exc
    if not raw.startswith(b"EU4txt"):
        raise SaveError("Expected EU4txt; binary/Ironman saves are unsupported")
    text = raw.decode("cp1252")
    stack: list[str] = []
    key: str | None = None
    assignment = False
    flags: set[str] = set()
    date = None
    player = None
    found = False
    for token in _tokens(text[6:]):
        if token == "=":
            if key is None or assignment:
                raise SaveError("Malformed assignment")
            assignment = True
        elif token == "{":
            if len(stack) >= 256:
                raise SaveError("Save nesting exceeds limit")
            stack.append(key if assignment and key else "[]")
            if stack == ["countries", country]:
                found = True
            key, assignment = None, False
        elif token == "}":
            if not stack or assignment:
                raise SaveError("Malformed or truncated save block")
            stack.pop()
            key, assignment = None, False
        elif assignment:
            value = token.strip('"')
            if not stack and key == "date":
                try:
                    parts = tuple(int(p) for p in value.split("."))
                    if len(parts) != 3 or not 1 <= parts[1] <= 12 or not 1 <= parts[2] <= 31:
                        raise ValueError
                    date = parts
                except ValueError as exc:
                    raise SaveError("Invalid save date") from exc
            elif not stack and key == "player":
                player = value
            elif stack == ["countries", country, "flags"] and key:
                flags.add(key)
            key, assignment = None, False
        else:
            key = token.strip('"')
    if stack or assignment or date is None or not found:
        raise SaveError("Incomplete save or selected country missing")
    if player != country:
        raise SaveError(f"Save player {player!r} differs from selected country {country}")
    return Snapshot(date, country, frozenset(flags))


def read_snapshot(path: Path, country: str) -> Snapshot:
    before = path.stat()
    if before.st_size > MAX_SAVE:
        raise SaveError("Save exceeds size limit")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SaveError("Save changed while reading; retry after writer finishes")
    return parse_save(raw, country)
