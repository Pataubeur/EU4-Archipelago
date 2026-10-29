from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .data import BY_ID, COUNTRIES


@dataclass(frozen=True)
class Manifest:
    seed: str
    slot: int
    team: int
    country: str
    locations: tuple[int, ...]
    charters_required: int = 3
    reward_strength: int = 1
    schema: int = 1

    def __post_init__(self) -> None:
        if (not isinstance(self.seed, str) or not isinstance(self.country, str)
                or any(type(value) is not int for value in
                       (self.slot, self.team, self.schema, self.charters_required, self.reward_strength))
                or not isinstance(self.locations, tuple)
                or any(type(value) is not int for value in self.locations)):
            raise ValueError("Invalid manifest field types")
        if self.schema != 1 or not self.seed or self.slot < 1 or self.team < 0:
            raise ValueError("Invalid manifest identity/schema")
        if self.country not in COUNTRIES:
            raise ValueError("Unsupported starting country")
        if not 10 <= len(self.locations) <= 20 or len(set(self.locations)) != len(self.locations):
            raise ValueError("Manifest requires 10-20 unique objectives")
        if any(i not in BY_ID for i in self.locations):
            raise ValueError("Unknown objective ID")
        if self.charters_required not in (2, 3, 4) or self.reward_strength not in (1, 2):
            raise ValueError("Invalid goal/reward setting")

    @property
    def token(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    @property
    def binding_flag(self) -> str:
        return f"eu4ap_seed_{self.token}"

    def check_flag(self, location: int) -> str:
        return f"eu4ap_{self.token}_check_{location}"

    def item_flag(self, index: int) -> str:
        return f"eu4ap_{self.token}_item_{index}"

    def charter_flag(self, index: int) -> str:
        return f"eu4ap_{self.token}_charter_{index}"

    @property
    def goal_flag(self) -> str:
        return f"eu4ap_{self.token}_goal"

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> Manifest:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("locations"), list):
                raise ValueError("Expected an object containing a locations list")
            data["locations"] = tuple(data["locations"])
            return cls(**data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid EU4 seed manifest {path.name}: {exc}. "
                             "Select the .apeu4.json supplied by the multiworld host, "
                             "not a player YAML or an .apworld package.") from exc
