import itertools
import unittest

from tests.helpers import manifest
from runtime.data import COUNTRY_PRESETS, ITEMS, OBJECTIVES, select_objectives


class CatalogTests(unittest.TestCase):
    def test_ids_unique_and_disjoint(self):
        locations = [o.id for o in OBJECTIVES]
        items = [v[0] for v in ITEMS.values()]
        self.assertEqual(len(locations), len(set(locations)))
        self.assertEqual(len(items), len(set(items)))
        self.assertFalse(set(items) & set(locations))
        self.assertEqual(len({o.name for o in OBJECTIVES}), len(locations))

    def test_entire_option_matrix(self):
        for count, econ, tech, country in itertools.product(
                range(10, 21), (False, True), (False, True), (*COUNTRY_PRESETS, "BYZ", "MNG", "AZT", "K00")):
            with self.subTest(count=count, econ=econ, tech=tech, country=country):
                pool = select_objectives(count, econ, tech)
                self.assertEqual(len(pool), count)
                self.assertGreaterEqual(sum(o.category == "calendar" for o in pool), count // 2)
                self.assertTrue(econ or all(o.category != "economic" for o in pool))
                self.assertTrue(tech or all(o.category != "technology" for o in pool))
                manifest(country=country, locations=tuple(o.id for o in pool))

    def test_identity_changes_with_slot_seed_and_options(self):
        baseline = manifest().token
        for kwargs in ({"slot": 2}, {"team": 1}, {"seed": "OTHER"}, {"reward_strength": 2}, {"country": "BRA"}):
            self.assertNotEqual(manifest(**kwargs).token, baseline)

    def test_reject_unsupported_configuration(self):
        for kwargs in ({"schema": 2}, {"country": "BAD-TAG"}, {"locations": (1,)}, {"reward_strength": 9}):
            with self.assertRaises(ValueError):
                manifest(**kwargs)
