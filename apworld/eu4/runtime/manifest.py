from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from functools import cached_property
from pathlib import Path

from .data import BY_ID, country_tag

LEGACY_FIELDS = ("seed", "slot", "team", "country", "locations", "charters_required",
                 "reward_strength", "schema")
TUPLE_FIELDS = ("locations", "fetters", "region_keys", "dlcs", "deathlink_codes")
NESTED_FIELDS = ("deliveries",)


@dataclass(frozen=True)
class Manifest:
    seed: str
    slot: int
    team: int
    country: str
    locations: tuple[int, ...]
    charters_required: int = 3  # Royal Charters (schema 1) or Seals (schema 2, goal mixed).
    reward_strength: int = 1
    schema: int = 1
    # Schema 2 only; schema 1 manifests must keep these defaults.
    save_mode: str = "normal"
    campaign_length: str = "standard"
    goal: str = "royal_charters"
    ambition: str = ""
    fetters: tuple[str, ...] = ()
    region_keys: tuple[str, ...] = ()
    dlcs: tuple[str, ...] = ()
    death_link: bool = False
    # Live deliveries (added after fill): (code, item id, sender slot, location id).
    deliveries: tuple[tuple[int, int, int, int], ...] = ()
    deathlink_codes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.seed, str) or not isinstance(self.country, str)
                or any(type(value) is not int for value in
                       (self.slot, self.team, self.schema, self.charters_required, self.reward_strength))
                or not isinstance(self.locations, tuple)
                or any(type(value) is not int for value in self.locations)
                or any(not isinstance(getattr(self, name), str)
                       for name in ("save_mode", "campaign_length", "goal", "ambition"))
                or any(not isinstance(getattr(self, name), tuple)
                       or any(not isinstance(v, str) for v in getattr(self, name))
                       for name in ("fetters", "region_keys", "dlcs"))
                or type(self.death_link) is not bool
                or not isinstance(self.deliveries, tuple)
                or any(not isinstance(row, tuple) or len(row) != 4 or any(type(v) is not int for v in row)
                       for row in self.deliveries)
                or not isinstance(self.deathlink_codes, tuple)
                or any(type(v) is not int for v in self.deathlink_codes)):
            raise ValueError("Invalid manifest field types")
        if self.schema not in (1, 2) or not self.seed or self.slot < 1 or self.team < 0:
            raise ValueError("Invalid manifest identity/schema: this client reads schemas 1 and 2 only")
        if country_tag(self.country) != self.country:
            raise ValueError("Manifest country tag must be uppercase without whitespace")
        if len(set(self.locations)) != len(self.locations):
            raise ValueError("Manifest objectives must be unique")
        if self.charters_required not in (2, 3, 4) or self.reward_strength not in (1, 2):
            raise ValueError("Invalid goal/reward setting")
        if self.schema == 1:
            self._validate_legacy()
        else:
            self._validate_v2()

    def _validate_legacy(self) -> None:
        if not 10 <= len(self.locations) <= 20:
            raise ValueError("Manifest requires 10-20 unique objectives")
        if any(i not in BY_ID for i in self.locations):
            raise ValueError("Unknown objective ID")
        defaults = Manifest.__dataclass_fields__
        if any(getattr(self, f.name) != defaults[f.name].default
               for f in fields(self) if f.name not in LEGACY_FIELDS):
            raise ValueError("Schema 1 manifests cannot use schema 2 settings")

    def _validate_v2(self) -> None:
        from .catalog import AMBITIONS, FETTERS, GOALS, KNOWN_DLCS, LENGTHS, LOCATION_DEFS, REGION_KEYS, SAVE_MODES
        if not 20 <= len(self.locations) <= 250:
            raise ValueError("Schema 2 manifests require 20-250 unique locations")
        if any(i not in LOCATION_DEFS or i in BY_ID for i in self.locations):
            raise ValueError("Unknown or legacy-only location ID in a schema 2 manifest")
        if (self.save_mode not in SAVE_MODES or self.campaign_length not in LENGTHS
                or self.goal not in GOALS or self.ambition not in AMBITIONS):
            raise ValueError("Invalid save mode, campaign length, goal or ambition")
        for name, allowed in (("fetters", FETTERS), ("region_keys", REGION_KEYS), ("dlcs", KNOWN_DLCS)):
            value = getattr(self, name)
            if any(v not in allowed for v in value) or list(value) != sorted(set(value)):
                raise ValueError(f"Invalid {name}: unknown, duplicated or unsorted values")
        from .catalog import ITEM_DEF_BY_ID
        codes = [row[0] for row in self.deliveries] + list(self.deathlink_codes)
        if (len(set(codes)) != len(codes) or any(not 1000 <= c <= 9999 for c in codes)
                or list(self.deliveries) != sorted(self.deliveries)
                or any(row[1] not in ITEM_DEF_BY_ID for row in self.deliveries)
                or (self.deathlink_codes and not self.death_link)):
            raise ValueError("Invalid deliveries: codes must be unique 4-digit numbers for known items")

    def delivery_item(self, code: int) -> int | None:
        return next((row[1] for row in self.deliveries if row[0] == code), None)

    # ------------------------------------------------------------------ identity

    def to_dict(self) -> dict:
        """Serialised form: schema 1 keeps its original fields (and thus its token)."""
        names = LEGACY_FIELDS if self.schema == 1 else [f.name for f in fields(self)]
        def value(name):
            if name in NESTED_FIELDS:
                return [list(row) for row in getattr(self, name)]
            return list(getattr(self, name)) if name in TUPLE_FIELDS else getattr(self, name)
        return {name: value(name) for name in names}

    @classmethod
    def from_dict(cls, data) -> Manifest:
        if not isinstance(data, dict) or not isinstance(data.get("locations"), (list, tuple)):
            raise ValueError("Expected an object containing a locations list")
        data = dict(data)
        for name in TUPLE_FIELDS:
            if name in data:
                if not isinstance(data[name], (list, tuple)):
                    raise ValueError("Invalid manifest field types")
                data[name] = tuple(data[name])
        for name in NESTED_FIELDS:
            if name in data:
                if not isinstance(data[name], (list, tuple)) or any(
                        not isinstance(row, (list, tuple)) for row in data[name]):
                    raise ValueError("Invalid manifest field types")
                data[name] = tuple(tuple(row) for row in data[name])
        return cls(**data)

    @cached_property
    def token(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    # --------------------------------------------------------------------- flags

    @property
    def binding_flag(self) -> str:
        return f"eu4ap_seed_{self.token}"

    def check_flag(self, location: int) -> str:
        return f"eu4ap_{self.token}_check_{location}"

    def done_flag(self, location: int) -> str:
        return f"eu4ap_{self.token}_done_{location}"

    def item_flag(self, index: int) -> str:
        return f"eu4ap_{self.token}_item_{index}"

    def charter_flag(self, index: int) -> str:
        return f"eu4ap_{self.token}_charter_{index}"

    def level_flag(self, family: str, level: int) -> str:
        """Level ``level`` (1-based) of a fetter, region key or seal."""
        return f"eu4ap_{self.token}_lvl_{family.replace(':', '_')}_{level}"

    def delivery_flag(self, code: int) -> str:
        return f"eu4ap_{self.token}_dlv_{code}"

    def deathlink_flag(self, index: int) -> str:
        return f"eu4ap_{self.token}_dl_{index}"

    @property
    def ambition_flag(self) -> str:
        return f"eu4ap_{self.token}_ambition"

    @property
    def goal_flag(self) -> str:
        return f"eu4ap_{self.token}_goal"

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> Manifest:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8-sig")))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid EU4 seed manifest {path.name}: {exc}. "
                             "Select the .apeu4.json supplied by the multiworld host, "
                             "not a player YAML or an .apworld package.") from exc
