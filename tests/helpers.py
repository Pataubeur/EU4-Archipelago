import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))

from runtime.data import select_objectives
from runtime.manifest import Manifest


def manifest(**kwargs):
    values = dict(seed="TEST", slot=1, team=0, country="FRA",
                  locations=tuple(o.id for o in select_objectives(16, True, True)))
    values.update(kwargs)
    return Manifest(**values)


def save_bytes(flags=(), country="FRA", date="1445.1.1"):
    body = " ".join(f'{f}=1445.1.1' for f in flags)
    return (f'EU4txt\ndate={date}\nplayer="{country}"\n'
            f'countries={{ {country}={{ name="A {{ quoted }} name" flags={{ {body} }} }} '
            'ENG={ flags={ wrong_country=1444.1.1 } } }').encode("cp1252")


def manifest_v2(**kwargs):
    """A planned schema-2 manifest (BYZ standard, keys and default fetters)."""
    from runtime.planner import SlotOptions, plan_slot
    values = dict(seed="TEST", slot=1, country="BYZ")
    values.update(kwargs)
    return plan_slot(SlotOptions(**values)).manifest


def multi_save_bytes(countries: dict, player: str, date="1460.1.1"):
    """Text save with several countries: {tag: [flags]}."""
    body = " ".join(f"{tag}={{ flags={{ {' '.join(f'{f}=1445.1.1' for f in flags)} }} }}"
                    for tag, flags in countries.items())
    return f'EU4txt\ndate={date}\nplayer="{player}"\ncountries={{ {body} }}'.encode("cp1252")


SCRIPT_TOKEN = __import__("re").compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[^\s{}=#"]+')


def lint_script(text: str) -> list[str]:
    """Structural check of Paradox script: every entry is `key = value` or
    `key = { ... }`; braces balance. Catches bare words such as a missing
    `has_country_flag =` before a flag."""
    tokens = [t for t in SCRIPT_TOKEN.findall(text) if not t.isspace() and not t.startswith("#")]
    errors, depth, i = [], 0, 0
    while i < len(tokens):
        token = tokens[i]
        if token == "}":
            depth -= 1
            if depth < 0:
                errors.append(f"unbalanced closing brace at token {i}")
                depth = 0
            i += 1
            continue
        if token in ("{", "="):
            errors.append(f"unexpected {token!r} near {' '.join(tokens[max(0, i - 4):i + 3])}")
            i += 1
            continue
        if i + 1 >= len(tokens) or tokens[i + 1] != "=":
            errors.append(f"bare word {token!r} near {' '.join(tokens[max(0, i - 6):i + 3])}")
            i += 1
            continue
        if i + 2 >= len(tokens):
            errors.append(f"missing value for {token!r}")
            break
        if tokens[i + 2] == "{":
            depth += 1
            i += 3
        elif tokens[i + 2] in ("}", "="):
            errors.append(f"missing value for {token!r}")
            i += 2
        else:
            i += 3
    if depth:
        errors.append(f"{depth} unclosed brace(s)")
    return errors
