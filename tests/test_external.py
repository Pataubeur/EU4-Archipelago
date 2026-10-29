"""Explicitly skipped environment-dependent validations. No green fake integration."""
import importlib.util
import os
import subprocess
import sys
import unittest

from tests.helpers import ROOT


class ExternalTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML unavailable; use the AP runtime or test extra")
    def test_example_yaml(self):
        import yaml
        data = yaml.safe_load((ROOT / "config/example.yaml").read_text())
        self.assertEqual(data["game"], "Europa Universalis IV")
        self.assertEqual(data[data["game"]]["starting_country"], "fra")

    @unittest.skipUnless(os.environ.get("AP_ROOT"), "AP_ROOT not configured; real Archipelago tests not executed")
    def test_actual_archipelago_world_suite(self):
        subprocess.run([sys.executable, "-m", "unittest", "worlds.eu4.test", "-v"],
                       cwd=os.environ["AP_ROOT"], check=True)
