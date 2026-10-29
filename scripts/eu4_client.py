"""Run from a source checkout without pip installing or importing the AP world."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apworld" / "eu4"))
from runtime.main import main

if __name__ == "__main__":
    raise SystemExit(main())
