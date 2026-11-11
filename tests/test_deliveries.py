"""Live deliveries: codes fixed at generation, claimed in game, audited by the client.
Synthetic tests only; the in-game digit pad is experiment E9."""
import asyncio
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.helpers import lint_script, manifest_v2
from runtime.catalog import ITEM_DEFS
from runtime.deliveries import DEATHLINK_CODES, attach_deliveries, deathlink_code, match_deliveries
from runtime.main import offline_manifest
from runtime.manifest import Manifest
from runtime.persistence import State
from runtime.render import INBOX, install_mod, mod_root
from runtime.render_v2 import code_test, mod_files
from runtime.synchronization import Synchronizer

KEY = ITEM_DEFS["Key: Balkans"].id
TREASURY = ITEM_DEFS["Royal Treasury"].id
TRAP = ITEM_DEFS["Inflation Spike"].id
# (item, sender, location): from Alice (slot 2), from ourselves (slot 1), start inventory.
ROWS = [(KEY, 2, 777001), (TREASURY, 1, 4839000), (TRAP, 3, 5), (TREASURY, 0, -2)]


def final(**kwargs):
    return attach_deliveries(manifest_v2(**kwargs), ROWS, seed=42)


class DeliveryModelTests(unittest.TestCase):
    def test_codes_unique_deterministic_and_round_trip(self):
        m = final(death_link=True)
        codes = [row[0] for row in m.deliveries] + list(m.deathlink_codes)
        self.assertEqual(len(m.deliveries), 4)
        self.assertEqual(len(m.deathlink_codes), DEATHLINK_CODES)
        self.assertEqual(len(set(codes)), len(codes))
        self.assertTrue(all(1000 <= c <= 9999 for c in codes))
        self.assertEqual(final(death_link=True), m)
        self.assertNotEqual(attach_deliveries(manifest_v2(), ROWS, seed=43).deliveries, final().deliveries)
        self.assertEqual(Manifest.from_dict(json.loads(json.dumps(m.to_dict()))), m)
        self.assertNotEqual(m.token, manifest_v2(death_link=True).token)

    def test_invalid_deliveries_rejected(self):
        data = final().to_dict()
        for bad in ([[999, KEY, 1, 1]], [[1000, KEY, 1, 1], [1000, KEY, 1, 2]], [[1000, -5, 1, 1]],
                    [[2000, KEY, 1, 1], [1000, KEY, 1, 2]], [[1000, KEY, 1]], "x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Manifest.from_dict(dict(data, deliveries=bad))
        with self.assertRaises(ValueError):
            Manifest.from_dict(dict(data, deathlink_codes=[1234]))  # Without death_link.

    def test_matching_by_sender_location_then_item(self):
        m = final()
        code = {(row[2], row[3]): row[0] for row in m.deliveries}
        items = [(0, TREASURY, -2, 0, 0, "received"),       # start inventory: by item
                 (1, KEY, 777001, 2, 0, "received"),
                 (2, KEY, 777001, 9, 0, "received"),        # wrong sender: no code
                 (3, TREASURY, -1, 0, 0, "received")]       # second server item: none left
        self.assertEqual(match_deliveries(m, items), {0: code[(0, -2)], 1: code[(2, 777001)]})
        self.assertEqual(deathlink_code(final(death_link=True), 0), final(death_link=True).deathlink_codes[0])
        self.assertIsNone(deathlink_code(m, 0))

    def test_offline_manifest_has_one_delivery_per_pool_item(self):
        m = offline_manifest("BYZ", 2, "ironman", "short")
        self.assertEqual(len(m.deliveries), len(m.locations))


class DeliveryRenderTests(unittest.TestCase):
    def test_files_lint_and_claim_guards(self):
        m = final(death_link=True)
        files = mod_files(m, [(0, KEY, 777001, 2, 0, "received")], deathlinks=1)
        for relative, (content, _encoding) in files.items():
            if relative.endswith(".txt"):
                self.assertEqual(lint_script(content), [], relative)
        claim = files["common/scripted_effects/eu4ap_deliveries.txt"][0]
        for code, item, _sender, _location in m.deliveries:
            self.assertIn(f"limit = {{ {code_test(code)} }}", claim)
            self.assertIn(f'log = "EU4AP {m.token} CLAIM {code}"', claim)
            self.assertIn(f"has_country_flag = {m.delivery_flag(code)}", claim)
        self.assertIn(m.level_flag("key:balkans", 1), claim)
        self.assertIn(f"CLAIM_EARLY", claim)            # The trap waits for 1450.
        self.assertIn("CLAIM_UNKNOWN", claim)
        self.assertEqual(claim.count("set_country_flag = " + m.delivery_flag(m.deathlink_codes[0])), 1)
        # The inbox shares the claim flag: one application whichever path comes first.
        inbox = files[INBOX][0]
        key_code = next(r[0] for r in m.deliveries if r[1] == KEY)
        self.assertIn(f"NOT = {{ has_country_flag = {m.delivery_flag(key_code)} }}", inbox)
        self.assertIn(f"NOT = {{ has_country_flag = {m.delivery_flag(m.deathlink_codes[0])} }}", inbox)

    def test_digit_pad_decision_and_localisation(self):
        m = final()
        files = mod_files(m)
        events = files["events/eu4ap_events.txt"][0]
        for event_id in (20, 21, 22, 23, 24):
            self.assertIn(f"id = eu4ap.{event_id}\n", events)
        self.assertEqual(events.count("option = { name = eu4ap.digit."), 40)
        self.assertIn("set_variable = { which = eu4ap_code value = 9000 }", events)
        self.assertIn("change_variable = { which = eu4ap_code value = 7 }", events)
        self.assertIn("eu4ap_claim = yes", events)
        self.assertIn("eu4ap_claim_delivery = {", files["decisions/eu4ap_decisions.txt"][0])
        custom = files["customizable_localization/eu4ap_customizable_localization.txt"][0]
        self.assertIn("name = GetEU4APDelivery", custom)
        for language in ("english", "french"):
            text = files[f"localisation/eu4ap_l_{language}.yml"][0]
            for code, item, *_ in m.deliveries:
                self.assertIn(f' eu4ap_dlv_{code}:0 "', text)
            for key in set(re.findall(r"localisation_key = (\S+)", custom)) | {
                    "eu4ap.24.d", "eu4ap.claim.cancel", "eu4ap_claim_delivery_title", "eu4ap.digit.9"}:
                self.assertIn(f" {key}:0 ", text, (language, key))

    def test_no_deliveries_still_renders_valid_files(self):
        files = mod_files(manifest_v2())
        self.assertEqual(lint_script(files["common/scripted_effects/eu4ap_deliveries.txt"][0]), [])
        self.assertEqual(lint_script(files["customizable_localization/eu4ap_customizable_localization.txt"][0]), [])


class DeliverySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.m = final(save_mode="ironman", death_link=True)
        install_mod(self.m, self.root)
        self.log_path = self.root / "game.log"
        self.log_path.write_text("Time:x\n")
        self.state = State(self.root / "state.db", self.m.token)
        self.sync = Synchronizer(self.m, self.state, self.root / "sync.txt", log_path=self.log_path,
                                 user_dir=self.root, eu4_running=lambda: True)
        self.code = {(r[2], r[3]): r[0] for r in self.m.deliveries}

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def log(self, *texts):
        with self.log_path.open("a") as stream:
            stream.write("".join(f"x EU4AP {self.m.token} {t}\n" for t in texts))
        asyncio.run(self.sync.poll_async(None))

    def test_claim_applies_received_item_and_lists_pending_codes(self):
        self.state.receive(0, [(KEY, 777001, 2, 0), (TREASURY, 99, 5, 0)])  # Second: not in the list.
        self.assertEqual(self.sync.pending_codes(), [(self.code[(2, 777001)], "Key: Balkans")])
        self.log(f"CLAIM {self.code[(2, 777001)]}")
        self.assertEqual([r[-1] for r in self.state.items()], ["applied", "received"])
        self.assertEqual(self.sync.pending_codes(), [])
        self.assertEqual(self.sync.status_warning(), "")

    def test_claim_before_reception_is_reported_then_honoured(self):
        early = self.code[(3, 5)]
        self.log(f"CLAIM {early}", "CLAIM 1", "CLAIM_UNKNOWN 1234.000")
        self.assertIn(str(early), self.sync.claim_warning)
        self.assertIn("1234", self.sync.warning)
        self.state.receive(0, [(TRAP, 5, 3, 0)])
        self.log("TICK 1460")
        self.assertEqual(self.state.items()[0][-1], "applied")
        self.assertEqual(self.sync.claim_warning, "")

    def test_deathlink_codes_listed_until_claimed(self):
        self.sync.receive_deathlink()
        first = self.m.deathlink_codes[0]
        self.assertEqual(self.sync.pending_codes(), [(first, "DeathLink")])
        self.log(f"CLAIM {first}")
        self.assertEqual(self.sync.pending_codes(), [])
        self.assertEqual(self.sync.claim_warning, "")

    def test_inbox_after_claim_does_not_reapply(self):
        self.state.receive(0, [(KEY, 777001, 2, 0)])
        self.log(f"CLAIM {self.code[(2, 777001)]}")
        self.sync.eu4_running = lambda: False
        self.sync.stage_inbox()
        inbox = (mod_root(self.root) / INBOX).read_text()
        self.assertIn(f"NOT = {{ has_country_flag = {self.m.delivery_flag(self.code[(2, 777001)])} }}", inbox)
        self.assertEqual(self.state.items()[0][-1], "applied")  # Staging never downgrades.


if __name__ == "__main__":
    unittest.main()
