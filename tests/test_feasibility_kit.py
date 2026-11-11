import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("feasibility_kit", ROOT / "scripts" / "feasibility_kit.py")
kit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = kit  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(kit)


def balanced(text: str) -> bool:
    depth = 0
    for char in text:
        depth += char == "{"
        depth -= char == "}"
        if depth < 0:
            return False
    return depth == 0


class RenderTests(unittest.TestCase):
    def test_inbox_generation_contains_every_guarded_item(self):
        text = kit.inbox_effect("R1", 3)
        self.assertTrue(balanced(text))
        for n in (1, 2, 3):
            self.assertIn(f"has_country_flag = eu4apx_item_{n} }}", text)
            self.assertIn(f'log = "EU4APX R1 ITEM {n} GEN 3"', text)
        self.assertNotIn("eu4apx_item_4", text)
        self.assertEqual(text.count(f"add_treasury = {kit.ITEM_DUCATS}"), 3)
        with self.assertRaises(ValueError):
            kit.inbox_effect("R1", 0)

    def test_mod_only_adds_namespaced_files(self):
        files = kit.render("R1", "ROM", ["BYZ_example_mission"])
        for relative, (content, _encoding) in files.items():
            self.assertTrue(balanced(content), relative)
            if relative != "descriptor.mod":
                self.assertTrue(Path(relative).name.startswith("eu4apx_"), relative)
        self.assertIn("change_tag = ROM", files["decisions/eu4apx_decisions.txt"][0])
        self.assertIn("mission_completed = BYZ_example_mission",
                      files["common/scripted_effects/eu4apx_missions.txt"][0])
        self.assertEqual(files["localisation/eu4apx_l_french.yml"][1], "utf-8-sig")


class LogTests(unittest.TestCase):
    def test_parse_complete_lines_for_one_run(self):
        text = ("Time:2026-11-11 10:00\n"
                "[effectimplementation.cpp:1]: EU4APX R1 MODE ironman\n"
                "[effectimplementation.cpp:1]: EU4APX R1 ITEM 1 GEN 2\n"
                "[effectimplementation.cpp:1]: EU4APX R2 ITEM 2 GEN 2\n"
                "[effectimplementation.cpp:1]: EU4APX R1 ITEM 1 GEN 2\r\n"
                "[effectimplementation.cpp:1]: EU4APX R1 ONACTION A\n"
                "[effectimplementation.cpp:1]: EU4APX R1 ITEM 3 GE")
        report = kit.parse_log(text, "R1")
        self.assertEqual(report.modes, ["ironman"])
        self.assertEqual(dict(report.items), {1: 2})  # duplicate counted, partial line ignored
        self.assertEqual(dict(report.on_actions), {"A": 1})
        self.assertIn("items never logged: [2]", kit.format_report(report, 2))

    def test_copies_of_one_session_are_not_counted_twice(self):
        early = "Time:2026-11-11 10:00\nx EU4APX R1 ITEM 1 GEN 1\n"
        later = early + "x EU4APX R1 ITEM 2 GEN 1\n"
        relaunch = "Time:2026-11-11 11:00\nx EU4APX R1 ITEM 2 GEN 2\n"
        merged = kit.merge_sessions([early, later, relaunch])
        self.assertEqual(dict(kit.parse_log(merged, "R1").items), {1: 1, 2: 2})

    def test_mission_inventory_reads_ids_only_for_requested_tags(self):
        with tempfile.TemporaryDirectory() as temp:
            missions = Path(temp) / "missions"
            missions.mkdir()
            (missions / "test.txt").write_text(
                "byz_series = {\n\tslot = 1\n\tpotential = {\n\t\ttag = BYZ\n\t}\n"
                "\tbyz_first = {\n\t\ticon = x\n\t\ttrigger = { always = yes }\n\t}\n}\n"
                "fra_series = {\n\tpotential = {\n\t\ttag = FRA\n\t}\n"
                "\tfra_first = {\n\t\ticon = x\n\t}\n}\n", encoding="cp1252")
            self.assertEqual(kit.mission_ids(Path(temp), {"BYZ"}), ["byz_first"])


if __name__ == "__main__":
    unittest.main()
