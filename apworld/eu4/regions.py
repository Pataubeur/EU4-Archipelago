from BaseClasses import LocationProgressType, Region

from .locations import EU4Location
from .runtime.catalog import LOCATION_DEFS, REGION_KEYS, location_guards
from .runtime.data import BY_ID


def create_regions(world) -> None:
    """Classic royal_charters mode: one region, no access rule."""
    region = Region("Menu", world.player, world.multiworld)
    for code in world.manifest().locations:
        region.locations.append(EU4Location(world.player, BY_ID[code].name, code, region))
    world.multiworld.regions.append(region)


def create_regions_v2(world, plan) -> None:
    """Ages organise locations (time is not an item); region keys gate their regions.

    Every guard is also a location access rule (rules.py), taken from the same
    catalogue table as the rendered mod, so logic and game agree exactly.
    """
    player, multiworld, m = world.player, world.multiworld, plan.manifest
    menu = Region("Menu", player, multiworld)
    ages = {n: Region(f"Age {n}", player, multiworld) for n in range(1, 5)}
    menu.connect(ages[1])
    for n in range(1, 4):
        ages[n].connect(ages[n + 1])
    keyed = {}
    for key in m.region_keys:
        item = REGION_KEYS[key].item
        keyed[key] = Region(f"Region: {item[5:]}", player, multiworld)
        ages[1].connect(keyed[key], rule=lambda state, item=item: state.has(item, player))
    for code in m.locations:
        definition = LOCATION_DEFS[code]
        keys = [family[4:] for family, _level in location_guards(code, m) if family.startswith("key:")]
        region = keyed[keys[0]] if keys else ages[definition.age]
        location = EU4Location(player, definition.name, code, region)
        if code in plan.excluded:
            location.progress_type = LocationProgressType.EXCLUDED
        elif code in plan.priority:
            location.progress_type = LocationProgressType.PRIORITY
        region.locations.append(location)
    multiworld.regions += [menu, *ages.values(), *keyed.values()]
