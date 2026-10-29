"""Generate the checked-in OFFLINE PoC mod and manifest from the real renderer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))
from runtime.data import select_objectives
from runtime.manifest import Manifest
from runtime.render import atomic_text, install_mod


def prepare() -> None:
    m = Manifest("OFFLINE-POC", 1, 0, "FRA", tuple(o.id for o in select_objectives(12, True, True)))
    m.write(ROOT / "config/poc.apeu4.json")
    install_mod(m, ROOT)
    # A distributable descriptor uses the normal relative mod path. The installer
    # writes an absolute path when installing to the user's actual game directory.
    descriptor = (ROOT / "mod/eu4_archipelago/descriptor.mod").read_text()
    atomic_text(ROOT / "mod/eu4_archipelago.mod", descriptor + 'path="mod/eu4_archipelago"\n')
    print("Generated OFFLINE-POC mod and config/poc.apeu4.json; EU4 was not run.")


if __name__ == "__main__":
    prepare()
