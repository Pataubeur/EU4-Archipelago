"""Generate the checked-in OFFLINE PoC mod and manifest from the real renderer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apworld" / "eu4"))
from runtime.main import offline_manifest
from runtime.render import atomic_text, install_mod


def prepare() -> None:
    m = offline_manifest("FRA", 2, "normal", "standard")
    m.write(ROOT / "config/poc-v2.apeu4.json")  # config/poc.apeu4.json stays the schema-1 fixture.
    install_mod(m, ROOT)
    # A distributable descriptor uses the normal relative mod path. The installer
    # writes an absolute path when installing to the user's actual game directory.
    descriptor = (ROOT / "mod/eu4_archipelago/descriptor.mod").read_text()
    atomic_text(ROOT / "mod/eu4_archipelago.mod", descriptor + 'path="mod/eu4_archipelago"\n')
    print("Generated OFFLINE-POC mod and config/poc-v2.apeu4.json; EU4 was not run.")


if __name__ == "__main__":
    prepare()
