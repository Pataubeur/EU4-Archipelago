from .runtime.catalog import family_item, goal_guards, location_guards


def set_rules(world) -> None:
    # Classic mode: no resource or geography assumptions in reachability. Campaign
    # survival and the earliest available dates are gameplay constraints documented separately.
    required = world.options.goal_difficulty.value
    player = world.player
    world.multiworld.completion_condition[player] = lambda state: state.has("Royal Charter", player, required)


def requirement(guards, player):
    needed = tuple((family_item(family), level) for family, level in guards)
    return lambda state: all(state.has(item, player, level) for item, level in needed)


def set_rules_v2(world, manifest) -> None:
    """Mirror the mod exactly: a location's check flag requires the same item flags.

    AP does not model the survival or military strength of the EU4 country.
    """
    player = world.player
    for code in manifest.locations:
        guards = location_guards(code, manifest)
        if guards:
            location = world.multiworld.get_location(world.location_id_to_name[code], player)
            location.access_rule = requirement(guards, player)
    world.multiworld.completion_condition[player] = requirement(goal_guards(manifest), player)
