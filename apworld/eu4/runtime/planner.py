"""Pure slot planning for schema 2: locations, item pool and guards.

No Archipelago import: the World calls this with its seeded random, and the
repository tests exercise it directly (options x countries x save modes).
"""
from __future__ import annotations

import random as _random
from collections import Counter
from dataclasses import dataclass, field

from .catalog import (AMBITIONS, CALENDAR, FETTERS, FILLER_ITEMS, GENERIC, HORIZON, ITEM_DEFS,
                      LOCATION_DEFS, MISSION_COUNT, REGION_KEYS, SEAL, TRAP_ITEMS, USEFUL_ITEMS,
                      family_item, goal_guards, late_year, length_index, location_guards, missions_for,
                      resolve_ambition)
from .manifest import Manifest

MIN_FREE_LOCATIONS = 15


@dataclass(frozen=True)
class SlotOptions:
    seed: str
    slot: int
    country: str
    team: int = 0
    save_mode: str = "normal"
    campaign_length: str = "standard"
    goal: str = "mixed"
    ambition: str = "auto"
    difficulty: int = 3
    reward_strength: int = 1
    fetters: tuple[str, ...] = ("admiralty", "chancery", "colonial", "guilds")
    region_keys: bool = True
    dlcs: tuple[str, ...] = ()
    missions: bool = True
    exclude_long: bool = True
    trap_percentage: int = 0
    ironman_traps: bool = False
    death_link: bool = False


@dataclass
class Plan:
    manifest: Manifest
    items: list[str]
    early_items: list[str] = field(default_factory=list)
    excluded: set[int] = field(default_factory=set)
    priority: set[int] = field(default_factory=set)

    @property
    def progression(self) -> list[str]:
        return [name for name in self.items if ITEM_DEFS[name].classification == "progression"]


def select_locations(options: SlotOptions, ambition_key: str) -> list[int]:
    length = length_index(options.campaign_length)
    chosen = [loc.id for loc in CALENDAR if int(loc.trigger.split()[-1]) <= HORIZON[options.campaign_length]]
    chosen += [loc.id for loc in GENERIC if length_index(loc.min_length) <= length]
    chosen += [loc.id for loc in AMBITIONS[ambition_key].milestone_defs()]
    if options.missions:
        chosen += missions_for(options.country, set(options.dlcs), MISSION_COUNT[options.campaign_length])
    return sorted(set(chosen))


def plan_slot(options: SlotOptions, rng: _random.Random | None = None) -> Plan:
    rng = rng or _random.Random(0)
    ambition_key = resolve_ambition(options.ambition, options.country, options.campaign_length,
                                    options.goal, set(options.dlcs))
    ambition = AMBITIONS[ambition_key]
    manifest = Manifest(
        seed=options.seed, slot=options.slot, team=options.team, country=options.country,
        locations=tuple(select_locations(options, ambition_key)),
        charters_required=options.difficulty, reward_strength=options.reward_strength, schema=2,
        save_mode=options.save_mode, campaign_length=options.campaign_length, goal=options.goal,
        ambition=ambition_key, fetters=tuple(sorted(set(options.fetters))),
        region_keys=tuple(sorted(ambition.keys)) if options.region_keys else (),
        dlcs=tuple(sorted(set(options.dlcs))), death_link=options.death_link)

    progression = [SEAL] * (manifest.charters_required + 1 if manifest.goal == "mixed" else 0)
    progression += [REGION_KEYS[k].item for k in manifest.region_keys]
    for key in manifest.fetters:
        progression += [FETTERS[key].item] * len(FETTERS[key].levels)
    slots = len(manifest.locations) - len(progression)
    if slots < 0:
        raise ValueError("More progression items than locations; enable more checks")
    useful = list(USEFUL_ITEMS) + (["Ambition Claims"] if ambition.claims else [])
    useful = useful[:slots]
    rest = slots - len(useful)
    traps = 0
    if options.trap_percentage and (options.save_mode == "normal" or options.ironman_traps):
        traps = rest * options.trap_percentage // 100
    pool = progression + useful
    pool += [rng.choice(TRAP_ITEMS) for _ in range(traps)]
    pool += [rng.choice(FILLER_ITEMS) for _ in range(rest - traps)]
    plan = Plan(manifest, pool,
                early_items=[REGION_KEYS[k].item for k in manifest.region_keys] if ambition.dated else [],
                excluded=excluded_locations(manifest, options.exclude_long),
                priority={m.id for m in ambition.milestone_defs() if m.priority})
    check_plan(plan)
    return plan


def is_long(location_id: int, length: str) -> bool:
    location = LOCATION_DEFS[location_id]
    if location.category == "calendar":
        return int(location.trigger.split()[-1]) > late_year(length)
    return location.long


def excluded_locations(manifest: Manifest, exclude_long: bool) -> set[int]:
    """Optional dated bonuses are always excluded; long checks on request (default)."""
    return {i for i in manifest.locations if LOCATION_DEFS[i].optional
            or (exclude_long and is_long(i, manifest.campaign_length))}


def check_plan(plan: Plan) -> None:
    """Static beatability: guards only name pooled items, in sufficient copies, and
    enough unguarded locations exist to hold every progression item (no cycle can
    then be forced: AP's fill places items only where the logic allows)."""
    m = plan.manifest
    counts = Counter(plan.items)
    if len(plan.items) != len(m.locations):
        raise ValueError("Item pool size differs from the location count")
    required = [*goal_guards(m)]
    free = 0
    for location in m.locations:
        guards = location_guards(location, m)
        required += guards
        free += not guards and location not in plan.excluded
    for family, level in required:
        if counts[family_item(family)] < level:
            raise ValueError(f"Guard {family} {level} cannot be satisfied by the item pool")
    if free < max(MIN_FREE_LOCATIONS, len(plan.progression)):
        raise ValueError(f"Only {free} unguarded locations for {len(plan.progression)} progression items")
