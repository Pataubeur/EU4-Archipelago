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
