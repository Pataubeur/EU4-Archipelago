from BaseClasses import Region

from .locations import EU4Location
from .runtime.data import BY_ID


def create_regions(world) -> None:
    region = Region("Menu", world.player, world.multiworld)
    for code in world.manifest().locations:
        region.locations.append(EU4Location(world.player, BY_ID[code].name, code, region))
    world.multiworld.regions.append(region)
