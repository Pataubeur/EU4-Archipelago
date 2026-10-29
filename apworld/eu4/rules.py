def set_rules(world) -> None:
    # No resource or geography assumptions in reachability. Campaign survival and
    # the earliest available dates are gameplay constraints documented separately.
    required = world.options.goal_difficulty.value
    player = world.player
    world.multiworld.completion_condition[player] = lambda state: state.has("Royal Charter", player, required)
