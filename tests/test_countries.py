import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import ROOT, manifest, save_bytes
from runtime.data import COUNTRY_PRESETS, ITEMS, country_tag
from runtime.game_bridge import SaveError, parse_save
from runtime.json_state import JsonState
from runtime.manifest import Manifest
from runtime.render import install_mod
from runtime.synchronization import Synchronizer
from runtime.countries import (COUNTRY_NAMES, OTHER_COUNTRY, country_choice_id,
                               country_choice_tag, country_label, named_country_tag)


class AnyCountryTests(unittest.TestCase):
    def test_named_catalogue_and_legacy_ids(self):
        identifiers = [country_choice_id(tag) for tag in COUNTRY_NAMES]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertNotIn(OTHER_COUNTRY, identifiers)
        self.assertEqual([country_choice_id(tag) for tag in COUNTRY_PRESETS], list(range(8)))
        self.assertEqual(country_label("FRA"), "France (FRA)")
        for tag, name in COUNTRY_NAMES.items():
            with self.subTest(tag=tag):
                self.assertEqual(country_choice_tag(country_choice_id(tag)), tag)
                self.assertEqual(named_country_tag(name.lower()), tag)
                self.assertEqual(named_country_tag(country_label(tag)), tag)

    def test_unlisted_tags_are_stable_and_do_not_require_a_named_entry(self):
        for tag in ("K00", "AAA", "ZZZ", "Z99"):
            self.assertEqual(country_choice_tag(country_choice_id(tag)), tag)
            self.assertEqual(named_country_tag(tag.lower()), tag)
        for value in (True, -1, 999, OTHER_COUNTRY, 9999999):
            with self.subTest(value=value), self.assertRaises(ValueError):
                country_choice_tag(value)

    def test_tag_validation_and_normalization(self):
        for value, expected in (("byz", "BYZ"), (" Mng ", "MNG"), ("K00", "K00")):
            self.assertEqual(country_tag(value), expected)
        for value in (None, 1, "", "FR", "France", "1AB", "F_R", "FRÄ", "ſra", "FRA }", "FRA\n}"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                country_tag(value)

    def test_manifest_requires_canonical_tag_but_not_a_country_whitelist(self):
        for tag in (*COUNTRY_PRESETS, "BYZ", "MNG", "AZT", "K00"):
            self.assertEqual(manifest(country=tag).country, tag)
        for tag in ("byz", " MNG", "BAD-TAG"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                manifest(country=tag)

    def test_old_manifest_keeps_its_seed_token(self):
        # Identity recorded for the shipped 0.3.1 PoC; upgrades must not rebind it.
        self.assertEqual(Manifest.read(ROOT / "config/poc.apeu4.json").token, "07502effa99c7120fb38d675")

    def test_offline_cli_accepts_new_tags_and_rejects_script_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.json"
            command = [sys.executable, str(ROOT / "scripts/eu4_client.py"),
                       "poc-manifest", "--output", str(path), "--country"]
            subprocess.run([*command, "byz"], capture_output=True, check=True)
            self.assertEqual(Manifest.read(path).country, "BYZ")
            original = path.read_bytes()
            result = subprocess.run([*command, "BYZ }"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), original)

    def test_nonpreset_campaign_from_mod_binding_to_reward_acknowledgment(self):
        # Synthetic save flags exercise the full bridge without claiming EU4 execution.
        for tag in ("BYZ", "MNG", "AZT", "K00"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                m = manifest(country=tag)
                mod = install_mod(m, root)
                self.assertEqual(Manifest.read(mod / "eu4ap_manifest.json"), m)
                decisions = (mod / "decisions/eu4ap_decisions.txt").read_text()
                self.assertIn(f"tag = {tag}", decisions)
                self.assertIn("started_in = 1444.11.11", decisions)
                path = root / "campaign.eu4"
                flags = [m.binding_flag, m.check_flag(m.locations[0])]
                path.write_bytes(save_bytes(flags, country=tag))
                state = JsonState(root / "state.json", m.token)
                try:
                    sync = Synchronizer(m, state, root / "eu4ap_sync.txt")
                    state.receive(0, [(ITEMS["100 Ducats"][0], 1, 1, 0)])
                    sync.poll(path)
                    self.assertEqual(state.checks(), {m.locations[0]})
                    self.assertEqual(state.items()[0][-1], "pending")
                    self.assertIn("add_treasury = 100", sync.output.read_text())
                    path.write_bytes(save_bytes(flags + [m.item_flag(0)], country=tag))
                    sync.poll(path)
                    self.assertEqual(state.items()[0][-1], "confirmed")
                    with self.assertRaises(SaveError):
                        parse_save(path.read_bytes(), "FRA")
                finally:
                    state.close()
