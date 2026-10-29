import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.helpers import manifest, save_bytes
from runtime.data import ITEMS
from runtime.game_bridge import SaveError, Snapshot, parse_save
from runtime.persistence import State
from runtime.render import install_mod, reward_script
from runtime.synchronization import Synchronizer


class ParserTests(unittest.TestCase):
    def test_country_scope_quotes_and_comments(self):
        raw = save_bytes(["eu4ap_seed_test", "real_flag"]) + b'\n# countries={evil}\n'
        snapshot = parse_save(raw, "FRA")
        self.assertEqual(snapshot.flags, {"eu4ap_seed_test", "real_flag"})
        self.assertEqual(snapshot.date, (1445, 1, 1))

    def test_zip_plaintext(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("gamestate", save_bytes(["test"]))
        self.assertEqual(parse_save(stream.getvalue(), "FRA").flags, {"test"})

    def test_binary_truncated_and_wrong_country(self):
        for raw in (b"EU4bin...", save_bytes()[:-1], b"PKbad", save_bytes().replace(b"date=1445.1.1", b"date=bad")):
            with self.subTest(raw=raw[:30]), self.assertRaises(SaveError):
                parse_save(raw, "FRA")
        with self.assertRaises(SaveError):
            parse_save(save_bytes(), "ENG")

    def test_missing_gamestate(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("meta", "not a save")
        with self.assertRaises(SaveError):
            parse_save(stream.getvalue(), "FRA")


class SyncTests(unittest.TestCase):
    state_class = State
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.m = manifest()
        self.state = self.state_class(self.root / "state.db", self.m.token)
        self.sync = Synchronizer(self.m, self.state, self.root / "eu4ap_sync.txt")
        self.path = self.root / "campaign.eu4"
        self.flags = [self.m.binding_flag, self.m.check_flag(self.m.locations[0])]
        self.write()

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def write(self, flags=None, date="1445.1.1"):
        self.path.write_bytes(save_bytes(self.flags if flags is None else flags, date=date))

    def test_check_retries_until_ack_and_survives_restart(self):
        self.sync.poll(self.path)
        first = self.sync.messages(set())
        self.assertEqual(first, self.sync.messages(set()))
        self.state.close()
        self.state = self.state_class(self.root / "state.db", self.m.token)
        self.sync.state = self.state
        self.assertEqual(self.sync.messages(set()), first)
        self.assertEqual(self.sync.messages(set(self.m.locations)), [])
        self.assertEqual(self.sync.messages(set()), first)  # Server restored an older apsave.

    def test_received_pending_confirmed_and_idempotent_replay(self):
        value = (ITEMS["100 Ducats"][0], 123, 2, 0)
        self.state.receive(0, [value, value])
        self.assertEqual([r[-1] for r in self.state.items()], ["received"] * 2)
        self.sync.poll(self.path)
        self.assertEqual([r[-1] for r in self.state.items()], ["pending"] * 2)
        self.write(self.flags + [self.m.item_flag(0)])
        self.sync.poll(self.path)
        self.state.receive(0, [value, value])
        self.assertEqual([r[-1] for r in self.state.items()], ["confirmed", "pending"])
        text = self.sync.output.read_text()
        self.assertEqual(text.count("add_treasury = 100"), 2)
        self.assertIn(f"NOT = {{ has_country_flag = {self.m.item_flag(0)} }}", text)

    def test_conflicting_replay_rolls_back_whole_packet(self):
        value = (ITEMS["100 Ducats"][0], 1, 1, 0)
        self.state.receive(0, [value])
        with self.assertRaises(ValueError):
            self.state.receive(0, [(ITEMS["10 Prestige"][0], 1, 1, 0)])
        self.assertEqual(self.state.items()[0][1], value[0])
        with self.assertRaises(ValueError):
            self.state.receive(3, [value])

    def test_wrong_identity_blocks_and_invalidates_script(self):
        self.sync.poll(self.path)
        self.write(["eu4ap_seed_other"])
        with self.assertRaises(SaveError):
            self.sync.poll(self.path)
        self.assertNotIn("eu4ap_scan = yes", self.sync.output.read_text())
        with self.assertRaises(ValueError):
            self.state_class(self.root / "state.db", manifest(slot=2).token)

    def test_rollback_checks_and_confirmed_items(self):
        value = (ITEMS["100 Ducats"][0], 1, 1, 0)
        self.state.receive(0, [value])
        self.write(self.flags + [self.m.item_flag(0)])
        self.sync.poll(self.path)
        self.write()
        with self.assertRaisesRegex(SaveError, "reward disappeared"):
            self.sync.poll(self.path)

    def test_goal_requires_native_charter_flags_and_survives_restart(self):
        self.write(self.flags + [self.m.goal_flag])
        with self.assertRaises(SaveError):
            self.sync.poll(self.path)
        self.assertIsNone(self.state.get("goal"))
        self.write(self.flags + [self.m.goal_flag] + [self.m.charter_flag(i) for i in range(3)])
        self.sync.poll(self.path)
        self.assertIn({"cmd": "StatusUpdate", "status": 30}, self.sync.messages(set()))

    def test_date_rollback_and_multiple_bindings(self):
        self.sync.poll(self.path)
        for flags, date in ((self.flags, "1444.12.1"), (self.flags + ["eu4ap_seed_other"], "1445.1.1")):
            self.write(flags, date)
            with self.assertRaises(SaveError):
                self.sync.poll(self.path)

    def test_same_day_check_rollback(self):
        self.sync.poll(self.path)
        self.write([self.m.binding_flag])
        with self.assertRaisesRegex(SaveError, "checks disappeared"):
            self.sync.poll(self.path)

    def test_atomic_export_failure_does_not_mark_pending(self):
        from unittest.mock import patch
        self.state.receive(0, [(ITEMS["100 Ducats"][0], 1, 1, 0)])
        with patch("runtime.synchronization.atomic_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.sync.poll(self.path)
        self.assertEqual(self.state.items()[0][-1], "received")

    def test_offline_checks_are_local_until_online_adapter_sends(self):
        self.sync.poll(self.path)
        self.assertEqual(self.state.checks(), {self.m.locations[0]})
        self.assertEqual(self.state.pending_checks(), self.state.checks())


class ModGenerationTests(unittest.TestCase):
    def test_installation_native_guards_and_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            m = manifest()
            root = install_mod(m, Path(directory))
            self.assertTrue((root / "descriptor.mod").is_file())
            self.assertEqual(ManifestRead.read(root / "eu4ap_manifest.json").token, m.token)
            self.assertTrue((root / "localisation/eu4ap_l_english.yml").read_bytes().startswith(b"\xef\xbb\xbf"))
            effect = (root / "common/scripted_effects/eu4ap_effects.txt").read_text()
            self.assertEqual(effect.count("set_country_flag"), len(m.locations))
            self.assertNotIn("http", effect)

    def test_all_rewards_have_unique_index_guards(self):
        m = manifest(reward_strength=2)
        values = [(i, data[0], -1, 0, 0, "pending") for i, data in enumerate(ITEMS.values())]
        text = reward_script(m, values)
        self.assertIn("add_treasury = 200", text)
        self.assertIn("add_adm_power = 100", text)
        for i in range(len(values)):
            self.assertIn(f"set_country_flag = {m.item_flag(i)}", text)
        with self.assertRaises(ValueError):
            reward_script(m, [(0, -99, 0, 0, 0, "received")])


from runtime.manifest import Manifest as ManifestRead
