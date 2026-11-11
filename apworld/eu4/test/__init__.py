"""Run with the REAL AP test runner; no AP stubs or mocked world APIs."""
from test.bases import WorldTestBase
import unittest

from ..options import StartingCountry
from ..runtime.catalog import LOCATION_DEFS, REGION_KEYS, goal_guards, location_guards
from ..runtime.data import COUNTRY_PRESETS
from ..runtime.countries import COUNTRY_NAMES, OTHER_COUNTRY


class EU4TestBase(WorldTestBase):
    game = "Europa Universalis IV"


class TestClassicCharters(EU4TestBase):
    options = {"goal": "royal_charters"}

    def test_counts_and_goal(self):
        world = self.multiworld.worlds[self.player]
        self.assertEqual(world.manifest().schema, 1)
        self.assertEqual(len(self.multiworld.get_locations(self.player)), 16)
        self.assertEqual(len(self.multiworld.itempool), 16)
        state = self.multiworld.state.copy()
        self.assertFalse(self.multiworld.completion_condition[self.player](state))
        for _ in range(3):
            state.collect(world.create_item("Royal Charter"), prevent_sweep=True)
        self.assertTrue(self.multiworld.completion_condition[self.player](state))


class TestLandlockedCalendarOnly(EU4TestBase):
    options = {"goal": "royal_charters", "starting_country": "bra", "enable_economic_checks": False,
               "enable_technology_checks": False, "location_count": 10}

    def test_every_location_reachable_without_items(self):
        for location in self.multiworld.get_locations(self.player):
            self.assertTrue(location.can_reach(self.multiworld.state))


class TestMaximumHardGoal(EU4TestBase):
    options = {"goal": "royal_charters", "location_count": 20, "goal_difficulty": "hard", "starting_country": "hab"}


class TestDefaultMixedBasileus(EU4TestBase):
    options = {"starting_country": "byz"}

    def test_schema_2_ambition_keys_and_guards(self):
        world = self.multiworld.worlds[self.player]
        m = world.manifest()
        self.assertEqual((m.schema, m.ambition, m.goal), (2, "byz_basileus", "mixed"))
        self.assertEqual(len(self.multiworld.get_locations(self.player)), len(m.locations))
        self.assertEqual(world.fill_slot_data()["manifest"], m.to_dict())
        state = self.multiworld.state.copy()
        for location in self.multiworld.get_locations(self.player):
            guarded = bool(location_guards(location.address, m))
            self.assertEqual(location.can_reach(state), not guarded, location.name)
        self.assertFalse(self.multiworld.completion_condition[self.player](state))

    def test_goal_needs_exactly_the_mod_requirements(self):
        world = self.multiworld.worlds[self.player]
        m = world.manifest()
        state = self.multiworld.state.copy()
        from ..runtime.catalog import family_item
        for family, level in goal_guards(m):
            for _ in range(level):
                state.collect(world.create_item(family_item(family)), prevent_sweep=True)
        self.assertTrue(self.multiworld.completion_condition[self.player](state))


class TestIronmanLongPentarchyEverything(EU4TestBase):
    options = {"starting_country": "byz", "campaign_length": "long", "save_mode": "ironman",
               "fetters": ["academy", "admiralty", "arsenal", "chancery", "colonial", "guilds", "imperial_court"],
               "trap_percentage": 30, "death_link": True}

    def test_no_traps_without_ironman_traps(self):
        self.assertFalse(any(item.trap for item in self.multiworld.itempool))
        m = self.multiworld.worlds[self.player].manifest()
        self.assertEqual(m.ambition, "byz_pentarchy")
        self.assertEqual(set(m.region_keys), {"anatolia", "egypt", "italy", "mashriq"})
        self.assertTrue(self.multiworld.worlds[self.player].fill_slot_data()["death_link"])


class TestDatedNavigator(EU4TestBase):
    options = {"starting_country": "por", "campaign_length": "short"}

    def test_keys_early_and_bonus_excluded(self):
        self.assertEqual(self.multiworld.early_items[self.player],
                         {REGION_KEYS["india"].item: 1, REGION_KEYS["east_indies"].item: 1})
        bonus = self.multiworld.get_location("The Navigator: Before 1500", self.player)
        from BaseClasses import LocationProgressType
        self.assertEqual(bonus.progress_type, LocationProgressType.EXCLUDED)


class TestOtherCountryBare(EU4TestBase):
    options = {"starting_country": "other_country", "custom_starting_country": "k00", "campaign_length": "short",
               "fetters": [], "region_keys": False, "mission_checks": False}

    def test_generic_ambition(self):
        m = self.multiworld.worlds[self.player].manifest()
        self.assertEqual((m.country, m.ambition, m.fetters), ("K00", "gen_regional_power", ()))
        self.assertTrue(all(LOCATION_DEFS[i].category != "mission" for i in m.locations))


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
