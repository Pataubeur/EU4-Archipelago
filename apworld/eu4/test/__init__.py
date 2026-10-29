"""Run with the REAL AP test runner; no AP stubs or mocked world APIs."""
from test.bases import WorldTestBase


class EU4TestBase(WorldTestBase):
    game = "Europa Universalis IV"


class TestDefault(EU4TestBase):
    def test_counts_and_goal(self):
        world = self.multiworld.worlds[self.player]
        self.assertEqual(len(self.multiworld.get_locations(self.player)), 16)
        self.assertEqual(len(self.multiworld.itempool), 16)
        state = self.multiworld.state.copy()
        self.assertFalse(self.multiworld.completion_condition[self.player](state))
        for _ in range(3):
            state.collect(world.create_item("Royal Charter"), prevent_sweep=True)
        self.assertTrue(self.multiworld.completion_condition[self.player](state))


class TestLandlockedCalendarOnly(EU4TestBase):
    options = {"starting_country": "bra", "enable_economic_checks": False,
               "enable_technology_checks": False, "location_count": 10}

    def test_every_location_reachable_without_items(self):
        for location in self.multiworld.get_locations(self.player):
            self.assertTrue(location.can_reach(self.multiworld.state))


class TestMaximumHardGoal(EU4TestBase):
    options = {"location_count": 20, "goal_difficulty": "hard", "starting_country": "hab"}
