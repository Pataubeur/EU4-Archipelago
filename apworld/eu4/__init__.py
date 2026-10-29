"""EU4 world for Archipelago. Native game integration remains experimental."""
from dataclasses import asdict
from pathlib import Path

from worlds.AutoWorld import WebWorld, World
from BaseClasses import Tutorial

from . import items, regions, rules
from .options import EU4Options
from .runtime.data import COUNTRIES, GAME, ITEMS, OBJECTIVES, select_objectives
from .runtime.manifest import Manifest
from . import launcher  # Register the client without importing its GUI during generation.


class EU4WebWorld(WebWorld):
    tutorials = [Tutorial("EU4 setup", "Install the Launcher client and seed-specific mod.",
                          "English", "setup_en.md", "setup/en", ["EU4 Archipelago contributors"])]


class EU4World(World):
    """Collect Royal Charters while guiding a country through EU4's early modern era."""
    game = GAME
    web = EU4WebWorld()
    options_dataclass = EU4Options
    options: EU4Options
    item_name_to_id = {name: value[0] for name, value in ITEMS.items()}
    location_name_to_id = {o.name: o.id for o in OBJECTIVES}

    def manifest(self) -> Manifest:
        objectives = select_objectives(self.options.location_count.value,
                                       bool(self.options.enable_economic_checks),
                                       bool(self.options.enable_technology_checks))
        return Manifest(str(self.multiworld.seed_name), self.player, 0,
                        COUNTRIES[self.options.starting_country.value],
                        tuple(o.id for o in objectives), self.options.goal_difficulty.value,
                        self.options.reward_strength.value)

    def create_regions(self) -> None:
        regions.create_regions(self)

    def create_item(self, name: str) -> items.EU4Item:
        return items.create_item(name, self.player)

    def get_filler_item_name(self) -> str:
        return "100 Ducats"

    def create_items(self) -> None:
        required = self.options.goal_difficulty.value
        pool = [self.create_item("Royal Charter") for _ in range(required)]
        rewards = [name for name in ITEMS if name != "Royal Charter"]
        pool.extend(self.create_item(name) for name in rewards)
        while len(pool) < self.options.location_count.value:
            pool.append(self.create_item(self.random.choice(rewards)))
        self.multiworld.itempool.extend(pool)

    def set_rules(self) -> None:
        rules.set_rules(self)

    def fill_slot_data(self) -> dict:
        return {"manifest": asdict(self.manifest())}

    def generate_output(self, output_directory: str) -> None:
        manifest = self.manifest()
        manifest.write(Path(output_directory) / f"AP_{manifest.token}_P{self.player}.apeu4.json")
