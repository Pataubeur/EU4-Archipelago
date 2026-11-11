"""Schema 2: catalogue, planning matrix, AP-logic consistency and mod rendering."""
import itertools
import json
import random
import re
import tempfile
import unittest
from pathlib import Path

from tests.helpers import lint_script, manifest, manifest_v2
from runtime import catalog
from runtime.catalog import (AMBITIONS, AMBITIONS_LIST, ALL_ITEMS, ALL_LOCATIONS, FETTERS, ITEM_DEFS,
                             KNOWN_DLCS, LOCATION_DEFS, REGION_KEYS, family_item, goal_guards,
                             location_guards, resolve_ambition)
from runtime.countries import COUNTRY_NAMES
from runtime.data import BASE_ID
from runtime.manifest import Manifest
from runtime.missions_1375 import MISSIONS
from runtime.planner import SlotOptions, check_plan, plan_slot
from runtime.render import install_mod, sync_script
from runtime.render_v2 import console_script, inbox_text, mod_files

COUNTRIES = ("FRA", "BYZ", "POR", "MNG", "K00", "SWE", "ARA", "TUN", "AZT", "MAL", "ETH", "BRA",
             "HAB", "ENG", "CAS", "POL", "SER", "HUN", "BUR", "WAL", "DAN", "TUR")


class CatalogTests(unittest.TestCase):
    def test_ids_and_names_unique_disjoint_and_legacy_stable(self):
        location_ids = [loc.id for loc in ALL_LOCATIONS]
        item_ids = [item.id for item in ALL_ITEMS]
        self.assertEqual(len(location_ids), len(set(location_ids)))
        self.assertEqual(len(item_ids), len(set(item_ids)))
        self.assertEqual(len({loc.name for loc in ALL_LOCATIONS}), len(location_ids))
        self.assertEqual(len({item.name for item in ALL_ITEMS}), len(item_ids))
        self.assertFalse(set(location_ids) & set(item_ids))
        # Existing campaigns depend on these exact values.
        self.assertEqual(LOCATION_DEFS[BASE_ID + 1].name, "Reach 1445")
        self.assertEqual(ITEM_DEFS["Royal Charter"].id, BASE_ID + 1000)
        self.assertEqual(ITEM_DEFS["100 Ducats"].id, BASE_ID + 1001)

    def test_id_ranges(self):
        for loc in catalog.NEW_LOCATIONS:
            offset = loc.id - BASE_ID
            expected = {"calendar": (2000, 2100), "ambition": (10_000, 20_000), "mission": (20_000, 30_000)}
            if loc.category in expected:
                low, high = expected[loc.category]
                self.assertTrue(low <= offset < high, loc)
        for ambition in AMBITIONS_LIST:
            for milestone in ambition.milestone_defs():
                self.assertEqual((milestone.id - BASE_ID - 10_000) // 100, ambition.index)

    def test_missions_are_identifiers_with_known_dlcs(self):
        seen = {}
        for tag, rows in MISSIONS.items():
            self.assertIn(tag, COUNTRY_NAMES)
            for code, mission, depth, required, excluded in rows:
                self.assertRegex(mission, r"^[A-Za-z0-9_]+$")
                self.assertEqual(seen.setdefault(mission, code), code)
                self.assertLessEqual(depth, 2)
                for dlc in (required, excluded):
                    self.assertTrue(dlc is None or dlc in KNOWN_DLCS, dlc)

    def test_guards_reference_existing_families(self):
        families = set(FETTERS) | {f"key:{k}" for k in REGION_KEYS} | {"seal"}
        for loc in ALL_LOCATIONS:
            for family, level in loc.guards:
                self.assertIn(family, families)
                if family in FETTERS:
                    self.assertLessEqual(level, len(FETTERS[family].levels))
        for ambition in AMBITIONS_LIST:
            for family, _level in ambition.all_goal_guards():
                self.assertIn(family, families)
            for milestone in ambition.milestone_defs():
                keys = {f[4:] for f, _ in milestone.guards if f.startswith("key:")}
                self.assertLessEqual(keys, set(ambition.keys), milestone.name)

    def test_every_trigger_and_effect_is_well_formed(self):
        for loc in ALL_LOCATIONS:
            self.assertEqual(lint_script(f"limit = {{ {loc.trigger} }}"), [], loc.name)
        for ambition in AMBITIONS_LIST:
            self.assertEqual(lint_script(f"limit = {{ {ambition.goal} }}"), [], ambition.key)
            if ambition.claims:
                self.assertEqual(lint_script(f"limit = {{ {ambition.claims} }}"), [], ambition.key)
        for item in ALL_ITEMS:
            effect = item.effect.replace("{amount}", "1")
            self.assertEqual(lint_script(f"effect = {{ {effect} }}"), [], item.name)

    def test_automatic_ambitions(self):
        cases = {("BYZ", "standard"): "byz_basileus", ("BYZ", "long"): "byz_pentarchy",
                 ("BYZ", "short"): "gen_regional_power", ("FRA", "long"): "fra_better_than_napoleon",
                 ("POR", "short"): "por_navigator", ("K00", "long"): "gen_every_continent",
                 ("AZT", "standard"): "gen_great_power", ("ENG", "standard"): "eng_one_night_in_paris"}
        for (tag, length), expected in cases.items():
            self.assertEqual(resolve_ambition("auto", tag, length, "mixed", set()), expected)
        self.assertEqual(resolve_ambition("auto", "AZT", "standard", "mixed", {"El Dorado"}),
                         "azt_edge_of_madness")
        self.assertEqual(resolve_ambition("auto", "FRA", "short", "domination", set()), "gen_domination_short")
        for bad in (("byz_pentarchy", "FRA", "long"), ("byz_pentarchy", "BYZ", "standard"),
                    ("azt_edge_of_madness", "AZT", "standard")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                resolve_ambition(bad[0], bad[1], bad[2], "mixed", set())

    def test_dated_bonus_is_optional_and_goal_has_no_deadline(self):
        navigator = AMBITIONS["por_navigator"]
        self.assertNotIn("is_year", navigator.goal)
        optional = [m for m in navigator.milestone_defs() if m.optional]
        self.assertEqual(len(optional), 1)
        self.assertIn("NOT = { is_year = 1500 }", optional[0].trigger)
        self.assertFalse(optional[0].priority)


class PlannerTests(unittest.TestCase):
    def test_matrix_countries_lengths_modes_goals(self):
        for tag, length, mode, goal in itertools.product(
                COUNTRIES, ("short", "standard", "long"), ("normal", "ironman"),
                ("mixed", "national_ambition", "great_power", "domination")):
            with self.subTest(tag=tag, length=length, mode=mode, goal=goal):
                plan = plan_slot(SlotOptions("SEED", 1, tag, save_mode=mode, campaign_length=length,
                                             goal=goal, trap_percentage=20), random.Random(1))
                m = plan.manifest
                self.assertEqual(m.schema, 2)
                self.assertEqual(len(plan.items), len(m.locations))
                self.assertEqual(Manifest.from_dict(json.loads(json.dumps(m.to_dict()))), m)
                traps = [n for n in plan.items if ITEM_DEFS[n].classification == "trap"]
                self.assertEqual(bool(traps), mode == "normal")  # Ironman: traps off by default.
                self.assertEqual(m.goal == "mixed", ("seal", m.charters_required) in goal_guards(m))

    def test_option_variants(self):
        variants = [dict(fetters=()), dict(fetters=tuple(FETTERS)), dict(region_keys=False),
                    dict(missions=False), dict(exclude_long=False), dict(difficulty=4),
                    dict(dlcs=tuple(KNOWN_DLCS)), dict(trap_percentage=30, save_mode="ironman",
                                                       ironman_traps=True), dict(death_link=True)]
        for tag, variant in itertools.product(("BYZ", "POR", "K00", "SWE"), variants):
            with self.subTest(tag=tag, variant=variant):
                plan = plan_slot(SlotOptions("SEED", 2, tag, **variant), random.Random(2))
                if variant.get("region_keys") is False or not plan.manifest.region_keys:
                    self.assertFalse(any(f.startswith("key:") for loc in plan.manifest.locations
                                         for f, _ in location_guards(loc, plan.manifest)))
                if variant.get("fetters") == ():
                    self.assertFalse(any(ITEM_DEFS[n].family in FETTERS for n in plan.items))

    def test_logic_beatable_and_consistent(self):
        """With every pooled item the goal and all locations are reachable; with
        none, only unguarded locations are; AP's fill then avoids any cycle."""
        for tag, length in itertools.product(COUNTRIES, ("short", "standard", "long")):
            plan = plan_slot(SlotOptions("SEED", 1, tag, campaign_length=length,
                                         fetters=tuple(FETTERS)), random.Random(3))
            m = plan.manifest
            owned = {}
            for name in plan.items:
                owned[name] = owned.get(name, 0) + 1
            has = lambda guards: all(owned.get(family_item(f), 0) >= lvl for f, lvl in guards)  # noqa: E731
            with self.subTest(tag=tag, length=length):
                self.assertTrue(has(goal_guards(m)))
                self.assertTrue(all(has(location_guards(i, m)) for i in m.locations))
                free = [i for i in m.locations if not location_guards(i, m) and i not in plan.excluded]
                self.assertGreaterEqual(len(free), len(plan.progression))
                self.assertGreaterEqual(len([i for i in free if LOCATION_DEFS[i].age == 1]), 10)

    def test_deterministic_and_seed_dependent(self):
        options = SlotOptions("SEED", 1, "FRA", trap_percentage=30)
        self.assertEqual(plan_slot(options, random.Random(9)).items, plan_slot(options, random.Random(9)).items)
        self.assertEqual(plan_slot(options, random.Random(9)).manifest, plan_slot(options, random.Random(8)).manifest)

    def test_dated_ambition_keys_early_and_long_checks_excluded(self):
        plan = plan_slot(SlotOptions("SEED", 1, "POR", campaign_length="short"))
        self.assertEqual(sorted(plan.early_items), ["Key: East Indies", "Key: India"])
        names = {LOCATION_DEFS[i].name for i in plan.excluded}
        self.assertIn("The Navigator: Before 1500", names)
        self.assertIn("Calendar: 1500", names)  # Last third of the short horizon.
        self.assertNotIn("Calendar: 1450", names)

    def test_check_plan_rejects_unsatisfiable_guards(self):
        plan = plan_slot(SlotOptions("SEED", 1, "BYZ"))
        plan.items = [n if n != "Key: Balkans" else "Royal Treasury" for n in plan.items]
        with self.assertRaisesRegex(ValueError, "cannot be satisfied"):
            check_plan(plan)


class ManifestV2Tests(unittest.TestCase):
    def test_round_trip_and_token_scope(self):
        m = manifest_v2()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.apeu4.json"
            m.write(path)
            self.assertEqual(Manifest.read(path), m)
        self.assertNotEqual(manifest_v2(save_mode="ironman").token, m.token)
        self.assertNotEqual(manifest_v2(campaign_length="long").token, m.token)

    def test_schema_1_unchanged_and_isolated(self):
        legacy = manifest()
        self.assertEqual(set(legacy.to_dict()), {"seed", "slot", "team", "country", "locations",
                                                 "charters_required", "reward_strength", "schema"})
        with self.assertRaisesRegex(ValueError, "schema 2 settings"):
            manifest(save_mode="ironman")

    def test_invalid_schema_2_values(self):
        data = manifest_v2().to_dict()
        for key, bad in (("schema", 3), ("save_mode", "hardcore"), ("goal", "royal_charters"),
                         ("ambition", "nope"), ("fetters", ["guilds", "admiralty"]),
                         ("region_keys", ["atlantis"]), ("dlcs", ["Fake DLC"]), ("death_link", 1),
                         ("locations", data["locations"][:5]), ("locations", data["locations"] + [BASE_ID + 1])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Manifest.from_dict(dict(data, **{key: bad}))


class RenderV2Tests(unittest.TestCase):
    def manifests(self):
        for tag, length, mode in itertools.product(("BYZ", "POR", "MAL", "K00", "SWE", "FRA"),
                                                   ("short", "long"), ("normal", "ironman")):
            yield plan_slot(SlotOptions("SEED", 1, tag, campaign_length=length, save_mode=mode,
                                        fetters=tuple(FETTERS), death_link=True, trap_percentage=30,
                                        ironman_traps=True))

    def items_for(self, plan):
        return [(i, ITEM_DEFS[name].id, 0, 0, 0, "received") for i, name in enumerate(plan.items)]

    def test_all_generated_scripts_lint_clean(self):
        for plan in self.manifests():
            m = plan.manifest
            files = mod_files(m, self.items_for(plan), deathlinks=2)
            with self.subTest(country=m.country, length=m.campaign_length, mode=m.save_mode):
                for relative, (content, encoding) in files.items():
                    self.assertTrue(Path(relative).name.startswith("eu4ap_"), relative)
                    if relative.endswith(".txt"):
                        self.assertEqual(lint_script(content), [], relative)
                    else:
                        self.assertEqual(encoding, "utf-8-sig")
                if m.save_mode == "normal":
                    self.assertEqual(lint_script(console_script(m, self.items_for(plan), 2)), [])

    def test_mod_guards_match_ap_logic(self):
        plan = plan_slot(SlotOptions("SEED", 1, "BYZ", campaign_length="long", fetters=tuple(FETTERS)))
        m = plan.manifest
        effects = mod_files(m)["common/scripted_effects/eu4ap_effects.txt"][0]
        promote = effects[effects.index("eu4ap_promote = {"):effects.index("eu4ap_recompute = {")]
        for location in m.locations:
            line = next(l for l in promote.splitlines() if f"set_country_flag = {m.check_flag(location)}" in l)
            expected = {m.level_flag(f, lvl) for f, lvl in location_guards(location, m)}
            found = set(re.findall(r"has_country_flag = (eu4ap_\w+_lvl_\w+)", line))
            self.assertEqual(found, expected, LOCATION_DEFS[location].name)
            self.assertIn(f"has_country_flag = {m.done_flag(location)}", line)
        decisions = mod_files(m)["decisions/eu4ap_decisions.txt"][0]
        allow = re.search(r"eu4ap_ratify = \{.*?allow = \{(.*?)\}\n", decisions, re.S).group(1)
        self.assertEqual(set(re.findall(r"has_country_flag = (\S+)", allow)),
                         {m.ambition_flag, *(m.level_flag(f, lvl) for f, lvl in goal_guards(m))})

    def test_scan_separates_done_from_check(self):
        m = manifest_v2()
        effects = mod_files(m)["common/scripted_effects/eu4ap_effects.txt"][0]
        scan = effects[effects.index("eu4ap_scan = {"):effects.index("eu4ap_promote = {")]
        self.assertNotIn("_check_", scan)
        self.assertEqual(scan.count("set_country_flag = eu4ap_"), len(m.locations) + 1)
        self.assertIn("eu4ap_heartland", scan)  # Starting provinces are never penalised.
        self.assertIn("NOT = { num_of_loans = 1 }", effects)  # Loans no longer validate treasuries.

    def test_inbox_items_guarded_logged_and_levelled(self):
        plan = plan_slot(SlotOptions("SEED", 1, "BYZ", fetters=tuple(FETTERS), trap_percentage=30))
        m = plan.manifest
        items = self.items_for(plan)
        text = inbox_text(m, items, deathlinks=1)
        for index, *_ in items:
            self.assertIn(f"limit = {{ NOT = {{ has_country_flag = {m.item_flag(index)} }}", text)
            self.assertIn(f'log = "EU4AP {m.token} ITEM {index}"', text)
        self.assertIn(m.level_flag("academy", 3), text)
        self.assertIn(m.level_flag("key:balkans", 1), text)
        self.assertIn(m.deathlink_flag(0), text)
        self.assertNotIn(m.deathlink_flag(1), text)
        for block in text.split("# Item index")[1:]:
            name = block.split("\n")[0].split(": ", 1)[1]
            if ITEM_DEFS[name].classification == "trap":
                self.assertIn("is_year = 1450", block)  # Traps wait for 1450.

    def test_resource_strength_and_claims(self):
        m = manifest_v2(reward_strength=2)
        text = inbox_text(m, [(0, ITEM_DEFS["Royal Treasury"].id, 0, 0, 0, "received"),
                              (1, ITEM_DEFS["Ambition Claims"].id, 0, 0, 0, "received")])
        self.assertIn("add_years_of_income = 0.5", text)
        self.assertIn("add_permanent_claim = ROOT", text)
        self.assertIn("area = thrace_area", text)

    def test_ironman_console_file_is_explanatory_only(self):
        m = manifest_v2(save_mode="ironman")
        script = sync_script(m, [(0, ITEM_DEFS["Royal Treasury"].id, 0, 0, 0, "received")])
        self.assertNotIn("add_years_of_income", script)
        self.assertTrue(all(line.startswith("#") for line in script.splitlines()))

    def test_localisation_covers_every_key(self):
        m = manifest_v2(fetters=tuple(FETTERS))
        files = mod_files(m)
        keys = set(re.findall(r"name = (eu4ap_[a-z_0-9]+)", files["common/event_modifiers/eu4ap_modifiers.txt"][0]))
        keys |= set(re.findall(r"^(eu4ap_[a-z_0-9]+) = \{", files["common/event_modifiers/eu4ap_modifiers.txt"][0], re.M))
        keys |= {f"{d}_{part}" for d in re.findall(r"^    (eu4ap_\w+) = \{",
                                                    files["decisions/eu4ap_decisions.txt"][0], re.M)
                 for part in ("title", "desc")}
        keys |= {"eu4ap.3.t", "eu4ap.3.d", "eu4ap.3.a"}
        for language in ("english", "french"):
            text = files[f"localisation/eu4ap_l_{language}.yml"][0]
            self.assertTrue(text.startswith(f"l_{language}:"))
            defined = set(re.findall(r"^ (\S+):0 ", text, re.M))
            self.assertLessEqual(keys, defined, language)

    def test_install_replaces_other_schema_files_but_keeps_user_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = install_mod(manifest_v2(), Path(directory))
            (root / "notes.txt").write_text("mine")
            install_mod(manifest(), Path(directory))
            self.assertFalse((root / "common/scripted_effects/eu4ap_inbox.txt").exists())
            self.assertTrue((root / "notes.txt").exists())
            root = install_mod(manifest_v2(), Path(directory))
            self.assertTrue((root / "common/scripted_effects/eu4ap_inbox.txt").exists())


if __name__ == "__main__":
    unittest.main()
