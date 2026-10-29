"""A synthetic save round trip. This is explicitly NOT a real EU4 test."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apworld" / "eu4"))
from runtime.data import ITEMS, select_objectives
from runtime.manifest import Manifest
from runtime.persistence import State
from runtime.synchronization import Synchronizer


def synthetic_save(path: Path, flags: list[str]) -> None:
    body = " ".join(f"{f}=1445.1.1" for f in flags)
    path.write_text(f'EU4txt\ndate=1445.1.1\nplayer="FRA"\ncountries={{ FRA={{ flags={{ {body} }} }} }}', encoding="cp1252")


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        m = Manifest("OFFLINE-POC", 1, 0, "FRA", tuple(o.id for o in select_objectives(12, True, True)))
        state = State(root / "state.sqlite3", m.token)
        sync = Synchronizer(m, state, root / "eu4ap_sync.txt")
        flags = [m.binding_flag, m.check_flag(m.locations[0])]
        synthetic_save(root / "campaign.eu4", flags)
        sync.poll(root / "campaign.eu4")
        assert sync.messages(set())[0]["locations"] == [m.locations[0]]
        state.receive(0, [(ITEMS["100 Ducats"][0], -1, 0, 0)])
        sync.poll(root / "campaign.eu4")
        assert state.items()[0][-1] == "pending"
        assert "add_treasury = 100" in sync.output.read_text()
        # The harness fabricates this flag; it does not run EU4's effect engine.
        synthetic_save(root / "campaign.eu4", flags + [m.item_flag(0)])
        sync.poll(root / "campaign.eu4")
        state.close()
        restored = State(root / "state.sqlite3", m.token)
        assert restored.items()[0][-1] == "confirmed"
        restored.close()
        print("PASS: SYNTHETIC check -> queued reward -> script -> fabricated save confirmation -> restart")
        print("EU4 and an AP server were not run.")


if __name__ == "__main__":
    main()
