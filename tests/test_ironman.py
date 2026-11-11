"""Schema-2 channels: game.log reader, inbox staging, formation, save/log interplay.
These are synthetic tests; none of them proves EU4 behaviour (experiments E1-E8)."""
import asyncio
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import manifest_v2, multi_save_bytes
from runtime.catalog import ITEM_DEFS
from runtime.client import Profile
from runtime.game_bridge import SaveError, parse_save
from runtime.game_log import GameLog
from runtime.json_state import JsonState
from runtime.manifest import Manifest
from runtime.persistence import State
from runtime.render import INBOX, install_mod, mod_root
from runtime.synchronization import Synchronizer

TREASURY = ITEM_DEFS["Royal Treasury"].id
KEY = ITEM_DEFS["Key: Balkans"].id


def line(m, text, source="[effectimplementation.cpp:42]: "):
    return f"{source}EU4AP {m.token} {text}\n"


class GameLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "game.log"
        self.m = manifest_v2()
        self.log = GameLog(self.path, self.m.token)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, text, mode="w"):
        with self.path.open(mode, encoding="cp1252", newline="") as stream:
            stream.write(text)

    def test_missing_partial_crlf_foreign_and_incremental(self):
        self.assertEqual(self.log.poll(), [])
        self.write("[main.cpp:1]: \nTime:2026-11-11 10:00\n" + line(self.m, "CHECK 1").replace("\n", "\r\n")
                   + line(manifest_v2(seed="OTHER"), "CHECK 2")
                   + f"EU4AP {self.m.token} ITEM 3")
        events = self.log.poll()
        self.assertEqual([(e.kind, e.args) for e in events], [("CHECK", ("1",))])
        self.assertEqual(self.log.foreign, 1)
        self.write("\n", "a")
        self.assertEqual([(e.kind, e.args) for e in self.log.poll()], [("ITEM", ("3",))])
        self.assertEqual(self.log.poll(), [])

    def test_new_launch_restarts_session(self):
        self.write("Time:2026-11-11 10:00\n" + line(self.m, "CHECK 1") + line(self.m, "TICK 1460"))
        first = self.log.poll()
        self.write("Time:2026-11-11 11:00\n" + line(self.m, "CHECK 1"))
        second = self.log.poll()
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0].session, second[0].session)
        self.write("Time:2026-11-11 11:00\n")  # Same header, shorter file: also a new launch.
        self.assertEqual(self.log.poll(), [])
        self.assertEqual(self.log.offset, len("Time:2026-11-11 11:00\n"))


class SyncV2Tests(unittest.TestCase):
    state_class = State

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.running = False
        self.make(manifest_v2())

    def make(self, m):
        self.m = m
        self.log_path = self.root / "logs" / "game.log"
        self.log_path.parent.mkdir(exist_ok=True)
        self.log_path.write_text("Time:2026-11-11 10:00\n", encoding="cp1252")
        install_mod(m, self.root)
        self.state = self.state_class(self.root / f"state-{m.token}", m.token)
        self.sync = Synchronizer(m, self.state, self.root / "eu4ap_sync.txt", log_path=self.log_path,
                                 user_dir=self.root, eu4_running=lambda: self.running)

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def log(self, *texts):
        with self.log_path.open("a", encoding="cp1252") as stream:
            stream.write("".join(line(self.m, t) for t in texts))

    def poll(self, save=None):
        self.sync._last_stage = float("-inf")
        return asyncio.run(self.sync.poll_async(save))

    def test_checks_items_goal_from_log(self):
        self.state.receive(0, [(TREASURY, 1, 2, 0), (KEY, 1, 2, 0)])
        first = self.m.locations[0]
        self.log("HELLO 2 normal", f"CHECK {first}", "CHECK 999", "ITEM 1", "ITEM 7", "GOAL")
        self.poll()
        self.assertEqual(self.state.checks(), {first})
        self.assertEqual([r[-1] for r in self.state.items()], ["staged", "applied"])
        messages = self.sync.messages(set())
        self.assertIn({"cmd": "LocationChecks", "locations": [first]}, messages)
        self.assertIn({"cmd": "StatusUpdate", "status": 30}, messages)
        self.assertEqual(self.sync.warning, "")

    def test_inbox_staged_only_while_eu4_is_closed(self):
        self.state.receive(0, [(TREASURY, 1, 2, 0)])
        inbox = mod_root(self.root) / INBOX
        self.running = True
        self.poll()
        self.assertNotIn(self.m.item_flag(0), inbox.read_text())
        self.assertEqual(self.state.items()[0][-1], "pending")  # In the console file only.
        self.running = False
        self.poll()
        self.assertIn(self.m.item_flag(0), inbox.read_text())
        self.assertEqual(self.state.items()[0][-1], "staged")
        self.log("ITEM 0")
        self.poll()
        self.assertEqual(self.state.items()[0][-1], "applied")

    def test_ironman_skips_console_marks_and_warns_on_mode_or_date(self):
        self.state.close()
        self.make(manifest_v2(save_mode="ironman"))
        self.state.receive(0, [(TREASURY, 1, 2, 0)])
        self.running = True
        self.poll()
        self.assertEqual(self.state.items()[0][-1], "received")
        self.assertIn("Ironman", self.sync.output.read_text())
        self.log("HELLO 2 normal", "TICK 1470")
        self.poll()
        self.assertIn("mode normal", self.sync.warning)
        self.sync.warning = ""
        self.log_path.write_text("Time:2026-11-11 12:00\n" + line(self.m, "TICK 1468"), encoding="cp1252")
        self.poll()
        self.assertIn("1470", self.sync.warning)
        self.assertEqual(self.state.get("log_year"), "1470")

    def test_tick_within_tolerance_is_silent(self):
        self.log("TICK 1470")
        self.poll()
        self.log_path.write_text("Time:2026-11-11 12:00\n" + line(self.m, "TICK 1469"), encoding="cp1252")
        self.poll()
        self.assertEqual(self.sync.warning, "")

    def test_deaths_deduplicated_across_restart(self):
        self.log("DEATH 1460")
        self.poll()
        self.assertEqual(self.sync.take_deaths(), ["1460"])
        restarted = Synchronizer(self.m, self.state, self.sync.output, log_path=self.log_path,
                                 user_dir=self.root, eu4_running=lambda: True)
        asyncio.run(restarted.poll_async(None))
        self.assertEqual(restarted.take_deaths(), [])

    def test_deathlinks_received_enter_inbox(self):
        self.sync.receive_deathlink()
        self.sync.receive_deathlink()
        self.poll()
        text = (mod_root(self.root) / INBOX).read_text()
        self.assertIn(self.m.deathlink_flag(1), text)

    def test_save_formation_and_log_checks_do_not_fake_rollback(self):
        save = self.root / "campaign.eu4"
        first, second = self.m.locations[:2]
        self.log(f"CHECK {first}")
        save.write_bytes(multi_save_bytes({"BYZ": [], "ROM": [self.m.binding_flag]}, "ROM"))
        self.poll(save)  # Older save without the logged check: accepted.
        self.assertEqual(self.state.checks(), {first})
        save.write_bytes(multi_save_bytes({"ROM": [self.m.binding_flag, self.m.check_flag(second)]},
                                          "ROM", date="1461.1.1"))
        self.poll(save)
        save.write_bytes(multi_save_bytes({"ROM": [self.m.binding_flag]}, "ROM", date="1462.1.1"))
        with self.assertRaisesRegex(SaveError, "checks disappeared"):
            self.poll(save)

    def test_save_goal_requires_ambition_flag(self):
        save = self.root / "campaign.eu4"
        save.write_bytes(multi_save_bytes({"BYZ": [self.m.binding_flag, self.m.goal_flag]}, "BYZ"))
        with self.assertRaisesRegex(SaveError, "Goal flag"):
            self.poll(save)
        save.write_bytes(multi_save_bytes(
            {"BYZ": [self.m.binding_flag, self.m.goal_flag, self.m.ambition_flag]}, "BYZ"))
        self.poll(save)
        self.assertEqual(self.state.get("save_goal"), "1")

    def test_mod_of_another_seed_blocks_staging(self):
        install_mod(manifest_v2(seed="OTHER"), self.root)
        self.state.receive(0, [(TREASURY, 1, 2, 0)])
        with self.assertRaisesRegex(ValueError, "ne correspond pas"):
            self.poll()


class JsonSyncV2Tests(SyncV2Tests):
    state_class = JsonState


class FormationBridgeTests(unittest.TestCase):
    def test_binding_follows_the_formed_tag(self):
        raw = multi_save_bytes({"BYZ": ["byz_flag"], "ROM": ["eu4ap_seed_x", "eu4ap_other", "foreign"]}, "ROM")
        snapshot = parse_save(raw, "BYZ", "eu4ap_seed_x")
        self.assertEqual(snapshot.country, "ROM")
        self.assertEqual(snapshot.flags, {"eu4ap_seed_x", "eu4ap_other"})
        with self.assertRaises(SaveError):
            parse_save(raw, "BYZ")  # Schema 1 keeps rejecting tag changes.
        twice = multi_save_bytes({"BYZ": ["eu4ap_seed_x"], "ROM": ["eu4ap_seed_x"]}, "ROM")
        with self.assertRaisesRegex(SaveError, "Several countries"):
            parse_save(twice, "BYZ", "eu4ap_seed_x")


class ClientV2Tests(unittest.TestCase):
    def test_install_keeps_received_items_and_refuses_running_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "save games").mkdir()
            m = manifest_v2()
            profile = Profile(manifest=str(root / "seed.apeu4.json"), user_dir=str(root))
            m.write(Path(profile.manifest))
            with self.assertRaisesRegex(ValueError, "Fermez EU4"):
                profile.install(eu4_running=lambda: True)
            path = profile.state_path(m)
            path.parent.mkdir(parents=True)
            state = JsonState(path, m.token)
            state.receive(0, [(TREASURY, 1, 2, 0)])
            mod = profile.install(eu4_running=lambda: False)
            self.assertIn(m.item_flag(0), (mod / INBOX).read_text())
            self.assertEqual(JsonState(path, m.token).items()[0][-1], "staged")
            profile.check_installed(m)
            with self.assertRaisesRegex(ValueError, "Installer le mod"):
                profile.check_installed(manifest_v2(seed="OTHER"))


class SessionV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_ironman_session_runs_without_save_and_reports_waiting_items(self):
        from runtime.client import Session

        class Context:
            def __init__(self, sync, *args):
                self.sync = sync
                self.exit_event = asyncio.Event()
                self.validated, self.slot, self.sync_error, self.blocked = True, 1, "", False

            async def tick(self, save):
                assert save is None  # Ironman never reads a save.
                await self.sync.poll_async(save)

            def status(self):
                return "connected"

            async def shutdown(self):
                await self.server_task

        async def server_loop(ctx):
            await ctx.exit_event.wait()

        common = types.ModuleType("CommonClient")
        common.server_loop = server_loop
        connection = types.ModuleType("runtime.connection")
        connection.EU4Context = Context
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "save games").mkdir()
            m = manifest_v2(save_mode="ironman")
            m.write(root / "m.apeu4.json")
            profile = Profile(str(root / "m.apeu4.json"), "", str(root), "localhost:1", "Player")
            session = Session(profile)
            with self.assertRaisesRegex(ValueError, "Installer le mod"):
                with patch.dict(sys.modules, {"CommonClient": common, "runtime.connection": connection}):
                    await session.run(lambda _: None)
            install_mod(m, root)
            state = JsonState(profile.state_path(m), m.token)
            state.receive(0, [(TREASURY, 1, 2, 0)])
            reports = []

            def report(text):
                reports.append(text)
                session.stop()

            with patch.dict(sys.modules, {"CommonClient": common, "runtime.connection": connection}), \
                    patch("runtime.process.eu4_running", return_value=True):
                await session.run(report)
            self.assertIn("mode Ironman", reports[0])
            self.assertIn("sans code, au prochain relancement : 1 — relancez EU4", reports[0])


class ConnectionV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_slot_data_validation_and_deathlink(self):
        from tests.test_connection import FakeContext
        fake = types.ModuleType("CommonClient")

        class DeathContext(FakeContext):
            deaths = []

            async def update_death_link(self, enabled):
                self.death_link_enabled = enabled

            async def send_death(self, text=""):
                self.deaths.append(text)

        fake.CommonContext = DeathContext
        fake.ClientCommandProcessor = object
        with patch.dict(sys.modules, {"CommonClient": fake}):
            sys.modules.pop("runtime.connection", None)
            context_class = importlib.import_module("runtime.connection").EU4Context
        sys.modules.pop("runtime.connection", None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            m = manifest_v2(death_link=True, save_mode="ironman")
            install_mod(m, root)
            log_path = root / "game.log"
            log_path.write_text("Time:x\n" + line(m, "DEATH 1470") + line(m, f"CHECK {m.locations[0]}"))
            state = State(root / "state.db", m.token)
            sync = Synchronizer(m, state, root / "eu4ap_sync.txt", log_path=log_path,
                                user_dir=root, eu4_running=lambda: True)
            ctx = context_class(sync, "localhost:1", "EU4Player")
            ctx.slot = 1
            ctx.on_package("Connected", dict(slot=1, team=0, slot_data={"manifest": json.loads(
                json.dumps(m.to_dict()))}, missing_locations=list(m.locations), checked_locations=[]))
            self.assertTrue(ctx.validated)
            await asyncio.sleep(0)
            self.assertTrue(ctx.death_link_enabled)
            await ctx.tick(None)
            self.assertEqual(len(DeathContext.deaths), 1)
            self.assertIn({"cmd": "LocationChecks", "locations": [m.locations[0]]}, ctx.sent)
            ctx.on_deathlink({"source": "Other"})
            self.assertEqual(sync.deathlinks_received(), 1)
            self.assertIn("schema=2", ctx.status())
            state.close()


if __name__ == "__main__":
    unittest.main()
