"""EU4 world for Archipelago. Native game integration remains experimental."""
from pathlib import Path

from worlds.AutoWorld import WebWorld, World
from BaseClasses import Tutorial
from Options import OptionError, OptionGroup

from . import items, regions, rules
from .options import (CampaignLength, CustomStartingCountry, DeathLink, ExcludeLongChecks, Fetters, Goal,
                      IronmanTraps, MissionChecks, NationalAmbition, OwnedDLCs, RegionKeys, SaveMode,
                      TrapPercentage, EU4Options)
from .runtime.catalog import ALL_ITEMS, ALL_LOCATIONS, item_groups, location_groups
from .runtime.data import GAME, select_objectives
from .runtime.deliveries import START_INVENTORY, attach_deliveries
from .runtime.manifest import Manifest
from .runtime.planner import Plan, SlotOptions, plan_slot
from . import launcher  # Register the client without importing its GUI during generation.


class EU4WebWorld(WebWorld):
    option_groups = [
        OptionGroup("Campaign", [SaveMode, CampaignLength, Goal, NationalAmbition, OwnedDLCs]),
        OptionGroup("Progression", [Fetters, RegionKeys, MissionChecks, ExcludeLongChecks,
                                    TrapPercentage, IronmanTraps, DeathLink]),
        OptionGroup("Other country (advanced)", [CustomStartingCountry], start_collapsed=True),
    ]
    tutorials = [Tutorial("EU4 setup", "Install the Launcher client and seed-specific mod.",
                          "English", "setup_en.md", "setup/en", ["EU4 Archipelago contributors"])]


class EU4World(World):
    """Guide a country through EU4's early modern era: national ambitions,
    multiworld fetters and region keys, in normal or Ironman campaigns."""
    game = GAME
    web = EU4WebWorld()
    options_dataclass = EU4Options
    options: EU4Options
    item_name_to_id = {item.name: item.id for item in ALL_ITEMS}
    location_name_to_id = {location.name: location.id for location in ALL_LOCATIONS}
    item_name_groups = item_groups()
    location_name_groups = location_groups()
    plan: Plan | None = None
    _final: Manifest | None = None
    _code_seed: int = 0

    @property
    def classic(self) -> bool:
        return self.options.goal.value == Goal.option_royal_charters

    def generate_early(self) -> None:
        if self.classic:
            return
        o = self.options
        try:
            self.plan = plan_slot(SlotOptions(
                seed=str(self.multiworld.seed_name), slot=self.player, country=o.country_tag,
                save_mode=o.save_mode.current_key, campaign_length=o.campaign_length.current_key,
                goal=o.goal.current_key, ambition=o.national_ambition.current_key,
                difficulty=o.goal_difficulty.value, reward_strength=o.reward_strength.value,
                fetters=tuple(sorted(o.fetters.value)), region_keys=bool(o.region_keys),
                dlcs=tuple(sorted(o.owned_dlcs.value)), missions=bool(o.mission_checks),
                exclude_long=bool(o.exclude_long_checks), trap_percentage=o.trap_percentage.value,
                ironman_traps=bool(o.ironman_traps), death_link=bool(o.death_link)), self.random)
        except ValueError as exc:
            raise OptionError(f"EU4 player {self.player_name}: {exc}") from exc
        for name in self.plan.early_items:
            self.multiworld.early_items[self.player][name] = 1
        # Drawn now so delivery codes do not depend on later random use.
        self._code_seed = self.random.getrandbits(64)

    def final_manifest(self) -> Manifest:
        """After fill: the plan's manifest plus every item this slot will receive,
        each with a live-delivery code (Ironman claims without relaunching)."""
        if self._final is None:
            if not self.plan:
                self._final = self.manifest()
            else:
                rows = [(location.item.code, location.player, location.address)
                        for location in self.multiworld.get_filled_locations()
                        if location.item.player == self.player and location.item.code is not None
                        and location.address is not None]
                rows += [(item.code, 0, START_INVENTORY)
                         for item in self.multiworld.precollected_items[self.player] if item.code is not None]
                self._final = attach_deliveries(self.plan.manifest, rows, self._code_seed)
        return self._final

    def manifest(self) -> Manifest:
        """Before fill (regions, rules). Use final_manifest() for outputs."""
        if self.plan:
            return self.plan.manifest
        objectives = select_objectives(self.options.location_count.value,
                                       bool(self.options.enable_economic_checks),
                                       bool(self.options.enable_technology_checks))
        return Manifest(str(self.multiworld.seed_name), self.player, 0,
                        self.options.country_tag,
                        tuple(o.id for o in objectives), self.options.goal_difficulty.value,
                        self.options.reward_strength.value)

    def create_regions(self) -> None:
        if self.plan:
            regions.create_regions_v2(self, self.plan)
        else:
            regions.create_regions(self)

    def create_item(self, name: str) -> items.EU4Item:
        return items.create_item(name, self.player)

    def get_filler_item_name(self) -> str:
        return "Royal Treasury" if self.plan else "100 Ducats"

    def create_items(self) -> None:
        if self.plan:
            self.multiworld.itempool.extend(self.create_item(name) for name in self.plan.items)
            return
        required = self.options.goal_difficulty.value
        pool = [self.create_item("Royal Charter") for _ in range(required)]
        rewards = ["100 Ducats", "50 Administrative Power", "50 Diplomatic Power",
                   "50 Military Power", "10 Prestige"]
        pool.extend(self.create_item(name) for name in rewards)
        while len(pool) < self.options.location_count.value:
            pool.append(self.create_item(self.random.choice(rewards)))
        self.multiworld.itempool.extend(pool)

    def set_rules(self) -> None:
        if self.plan:
            rules.set_rules_v2(self, self.plan.manifest)
        else:
            rules.set_rules(self)

    def fill_slot_data(self) -> dict:
        return {"manifest": self.final_manifest().to_dict(), "death_link": bool(self.options.death_link)}

    def generate_output(self, output_directory: str) -> None:
        manifest = self.final_manifest()
        manifest.write(Path(output_directory) / f"AP_{manifest.token}_P{self.player}.apeu4.json")
