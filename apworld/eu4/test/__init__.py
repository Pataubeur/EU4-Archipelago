"""Run with the REAL AP test runner; no AP stubs or mocked world APIs."""
from test.bases import WorldTestBase
import unittest

from ..options import StartingCountry
from ..runtime.data import COUNTRY_PRESETS
from ..runtime.countries import COUNTRY_NAMES, OTHER_COUNTRY


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


class TestAnyStartingCountry(EU4TestBase):
    options = {"starting_country": "mNg"}

    def test_manifest_and_slot_data_keep_selected_tag(self):
        world = self.multiworld.worlds[self.player]
        self.assertEqual(world.manifest().country, "MNG")
        self.assertEqual(world.fill_slot_data()["manifest"]["country"], "MNG")


class StartingCountryTests(unittest.TestCase):
    def test_old_presets_names_and_numeric_ids_still_resolve(self):
        for index, tag in enumerate(COUNTRY_PRESETS):
            for value in (index, tag, tag.lower()):
                with self.subTest(value=value):
                    self.assertEqual(StartingCountry.from_any(value).tag, tag)

    def test_free_tags_normalization_and_random_scope(self):
        for tag in ("byz", "mNg", "AZT", "K00"):
            self.assertEqual(StartingCountry.from_any(tag).tag, tag.upper())
        self.assertIn(StartingCountry.from_any("random").tag, COUNTRY_NAMES)

    def test_named_choices_labels_and_default(self):
        for value in ("France", "france (FRA)", "Ming", "Byzantium (BYZ)"):
            option = StartingCountry.from_any(value)
            self.assertIn(option.tag, COUNTRY_NAMES)
        self.assertEqual(StartingCountry.get_option_name(StartingCountry.default), "France (FRA)")
        self.assertEqual(StartingCountry.from_any("other_country").value, OTHER_COUNTRY)

    def test_invalid_input_rejected_before_native_script_generation(self):
        for value in ("Not a country", "FR", "FRA }", "1AB", "F_R", "FRÄ", "---", -1, 999, None, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                StartingCountry.from_any(value)


class TestOtherCountryField(EU4TestBase):
    options = {"starting_country": "other_country", "custom_starting_country": " k00 "}

    def test_manifest_uses_custom_tag(self):
        self.assertEqual(self.multiworld.worlds[self.player].manifest().country, "K00")


class TestUnusedCustomCountry(EU4TestBase):
    options = {"starting_country": "Ming", "custom_starting_country": "ignored invalid text"}

    def test_custom_field_does_not_override_named_choice(self):
        self.assertEqual(self.multiworld.worlds[self.player].manifest().country, "MNG")
