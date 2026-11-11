"""Regenerate apworld/eu4/runtime/missions_1375.py from a local EU4 installation.

Development tool. It reads ``missions/*.txt`` read-only and writes **identifiers
only** (mission keys, depth in the tree, DLC condition). No game text, script or
asset is copied. Existing location IDs are preserved; new missions get new IDs
after the highest one, so IDs are never reassigned.

    python scripts/extract_missions.py --game-dir "E:/Steam/steamapps/common/Europa Universalis IV"
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))

from runtime.countries import COUNTRY_NAMES  # noqa: E402
from runtime.data import BASE_ID  # noqa: E402

OUTPUT = ROOT / "apworld" / "eu4" / "runtime" / "missions_1375.py"
MISSION_BASE = BASE_ID + 20_000
MAX_DEPTH = 2          # Only the first three rows of a tree: reachable in a multiworld session.
MAX_PER_VARIANT = 14   # Per tag and DLC condition.
HEAD = re.compile(r"([A-Za-z0-9_]+)\s*=\s*\{")


def blocks(text: str):
    i = 0
    while (m := HEAD.search(text, i)):
        j, depth = m.end(), 1
        while depth and j < len(text):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            j += 1
        yield m.group(1), text[m.end():j - 1]
        i = j


def child(body: str, key: str) -> str:
    return next((b for k, b in blocks(body) if k == key), "")


def top_level(text: str) -> str:
    """Text of a block without its nested blocks, except a top-level NOT."""
    out, depth, i = [], 0, 0
    while i < len(text):
        not_block = re.match(r"NOT\s*=\s*\{\s*has_dlc\s*=\s*\"[^\"]+\"\s*\}", text[i:])
        if depth == 0 and not_block:
            out.append(not_block.group())
            i += not_block.end()
            continue
        depth += text[i] == "{"
        if depth == 0:
            out.append(text[i])
        depth -= text[i] == "}"
        i += 1
    return re.sub(r"\s+", " ", "".join(out))


def dlc_condition(series: str) -> tuple[str | None, str | None]:
    """(required DLC, excluded DLC) from top-level conditions of potential_on_load/potential.

    Conditions nested in OR/AND are ignored: they do not gate the whole series.
    """
    for key in ("potential_on_load", "potential"):
        text = top_level(child(series, key))
        negated = re.search(r'NOT\s*=\s*\{\s*has_dlc\s*=\s*"([^"]+)"\s*\}', text)
        if negated:
            return None, negated.group(1)
        required = re.search(r'has_dlc\s*=\s*"([^"]+)"', text)
        if required:
            return required.group(1), None
    return None, None


def without_not_blocks(text: str) -> str:
    """Drop NOT = { ... } blocks: ``NOT = { tag = MNG }`` must not select Ming."""
    while (m := re.search(r"\bNOT\s*=\s*\{", text)):
        j, depth = m.end(), 1
        while depth and j < len(text):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            j += 1
        text = text[:m.start()] + text[j:]
    return text


def scan(game_dir: Path) -> tuple[dict, dict]:
    series_by_tag: dict[str, list] = {}
    requires: dict[str, list[str]] = {}
    for path in sorted((game_dir / "missions").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", path.read_text(encoding="cp1252", errors="replace"))
        for _name, series in blocks(text):
            tags = set(re.findall(r"\btag\s*=\s*([A-Z][A-Z0-9]{2})\b",
                                  without_not_blocks(child(series, "potential"))))
            required, excluded = dlc_condition(series)
            missions = []
            for key, body in blocks(series):
                if re.search(r"\bicon\s*=", body):
                    requires[key] = re.findall(r"[A-Za-z0-9_]+", child(body, "required_missions"))
                    missions.append(key)
            for tag in tags:
                series_by_tag.setdefault(tag, []).append((missions, required, excluded))
    return series_by_tag, requires


def depth_of(mission: str, requires: dict, seen=()) -> int:
    if mission in seen:
        return 99
    parents = [p for p in requires.get(mission, []) if p in requires]
    return 0 if not parents else 1 + max(depth_of(p, requires, (*seen, mission)) for p in parents)


def existing_ids() -> dict[str, int]:
    """Mission key -> location ID. One ID per mission, even if several tags share it."""
    if not OUTPUT.is_file():
        return {}
    tree = ast.parse(OUTPUT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "MISSIONS":
            data = ast.literal_eval(node.value)
            return {row[1]: row[0] for rows in data.values() for row in rows}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-dir", type=Path, required=True)
    args = parser.parse_args()
    series_by_tag, requires = scan(args.game_dir)
    ids = existing_ids()
    next_id = max(ids.values(), default=MISSION_BASE) + 1
    result: dict[str, list[tuple]] = {}
    for tag in sorted(COUNTRY_NAMES):
        rows = []
        variants: dict[tuple, list] = {}
        for missions, required, excluded in series_by_tag.get(tag, []):
            for mission in missions:
                depth = depth_of(mission, requires)
                if depth <= MAX_DEPTH:
                    variants.setdefault((required, excluded), []).append((depth, mission))
        for (required, excluded), found in sorted(variants.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")):
            for depth, mission in sorted(set(found))[:MAX_PER_VARIANT]:
                if mission not in ids:
                    ids[mission] = next_id
                    next_id += 1
                rows.append((ids[mission], mission, depth, required, excluded))
        if rows:
            result[tag] = sorted(rows)
    lines = ['"""Mission identifiers for EU4 1.37.5, generated by scripts/extract_missions.py.',
             "",
             "Identifiers only (no game text). Row: (AP location id, mission key, depth in",
             "the tree, DLC required or None, DLC whose absence is required or None).",
             'IDs are stable: regenerate with the script, never renumber by hand."""',
             "", "MISSIONS = {"]
    for tag, rows in result.items():
        lines.append(f"    {tag!r}: (")
        lines += [f"        {row!r}," for row in rows]
        lines.append("    ),")
    lines.append("}")
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUTPUT}: {sum(map(len, result.values()))} missions for {len(result)} countries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
