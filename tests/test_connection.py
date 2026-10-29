"""AP ADAPTER TESTS WITH A FAKE CommonContext, not live WebSocket tests."""
import asyncio
import importlib
import sys
import tempfile
import types
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from tests.helpers import manifest, save_bytes
from runtime.data import ITEMS
from runtime.persistence import State
from runtime.game_bridge import read_snapshot
from runtime.synchronization import Synchronizer


class FakeContext:
    def __init__(self, server, password):
        self.server = None
        self.slot = None
        self.password = password
        self.checked_locations = set()
        self.exit_event = asyncio.Event()
        self.sent = []

    async def server_auth(self, requested=False):
        pass

    async def get_username(self):
        pass

    async def send_connect(self):
        self.sent.append({"cmd": "Connect", "game": self.game, "name": self.auth, "items_handling": self.items_handling})

    async def send_msgs(self, messages):
        self.sent.extend(messages)

    async def connection_closed(self):
        self.slot = None


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        fake = types.ModuleType("CommonClient")
        fake.CommonContext = FakeContext
        fake.ClientCommandProcessor = object
        with patch.dict(sys.modules, {"CommonClient": fake}):
            sys.modules.pop("runtime.connection", None)
            self.context_class = importlib.import_module("runtime.connection").EU4Context
        sys.modules.pop("runtime.connection", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.m = manifest()
        self.state = State(self.root / "state.db", self.m.token)
        self.sync = Synchronizer(self.m, self.state, self.root / "eu4ap_sync.txt")
        self.ctx = self.context_class(self.sync, "localhost:38281", "EU4Player")
        self.save = self.root / "campaign.eu4"
        self.save.write_bytes(save_bytes([self.m.binding_flag, self.m.check_flag(self.m.locations[0])]))

    async def asyncTearDown(self):
        self.state.close()
        self.tmp.cleanup()

    def connected(self, **overrides):
        data = dict(slot=1, team=0, slot_data={"manifest": asdict(self.m)},
                    missing_locations=list(self.m.locations), checked_locations=[])
        data.update(overrides)
        self.ctx.slot = data["slot"]  # CommonClient sets this before invoking on_package.
        self.ctx.on_package("Connected", data)

    async def test_authentication_and_packet_flow(self):
        await self.ctx.server_auth()
        self.assertEqual(self.ctx.sent[-1]["items_handling"], 7)
        self.connected()
        self.ctx.on_package("ReceivedItems", {"index": 0, "items": [(ITEMS["100 Ducats"][0], 123, 2, 0)]})
        await self.ctx.tick(self.save)
        self.assertTrue(self.ctx.validated)
        self.assertEqual(self.state.items()[0][-1], "pending")
        self.assertIn({"cmd": "LocationChecks", "locations": [self.m.locations[0]]}, self.ctx.sent)
        self.assertIn("100 Ducats", self.ctx.status())

    async def test_reconnect_resends_without_duplicate_items(self):
        self.connected()
        value = [(ITEMS["100 Ducats"][0], 123, 2, 0)]
        self.ctx.on_package("ReceivedItems", {"index": 0, "items": value})
        await self.ctx.tick(self.save)
        await self.ctx.connection_closed()
        self.assertFalse(self.ctx.validated)
        before = len(self.ctx.sent)
        await self.ctx.tick(self.save)
        self.assertEqual(len(self.ctx.sent), before)
        self.connected()
        self.ctx.on_package("ReceivedItems", {"index": 0, "items": value})
        await self.ctx.tick(self.save)
        self.assertEqual(len(self.state.items()), 1)
        self.assertEqual(len(self.ctx.sent), before + 1)

    async def test_wrong_slot_and_unknown_item_stop_exports(self):
        self.connected(slot=2)
        self.assertTrue(self.ctx.blocked)
        self.assertTrue(self.ctx.exit_event.is_set())
        self.assertEqual(self.state.items(), [])

    async def test_gap_waits_for_replay(self):
        self.connected()
        value = [(ITEMS["100 Ducats"][0], 123, 2, 0)]
        self.ctx.on_package("ReceivedItems", {"index": 2, "items": value})
        self.assertFalse(self.ctx.stream_ready)
        await self.ctx.tick(self.save)
        self.assertEqual(self.ctx.sent, [])
        self.ctx.on_package("ReceivedItems", {"index": 0, "items": value})
        self.assertTrue(self.ctx.stream_ready)
        await self.ctx.tick(self.save)
        self.assertEqual(len(self.state.items()), 1)

    async def test_unknown_item_is_not_silently_consumed(self):
        self.connected()
        self.ctx.on_package("ReceivedItems", {"index": 0, "items": [(-999, 123, 2, 0)]})
        self.assertTrue(self.ctx.blocked)
        self.assertEqual(self.state.items(), [])

    async def test_unchanged_save_is_parsed_once_but_new_items_are_exported(self):
        self.connected()
        with patch("runtime.synchronization.read_snapshot", wraps=read_snapshot) as reader:
            await self.ctx.tick(self.save)
            before = self.sync.output.stat().st_mtime_ns
            await self.ctx.tick(self.save)
            self.assertEqual(self.sync.output.stat().st_mtime_ns, before)
            self.ctx.on_package("ReceivedItems", {
                "index": 0, "items": [(ITEMS["100 Ducats"][0], 123, 2, 0)]})
            await self.ctx.tick(self.save)
            self.assertEqual(reader.call_count, 1)
            self.assertIn("add_treasury = 100", self.sync.output.read_text())
            self.assertEqual(self.state.items()[0][-1], "pending")

    async def test_changed_save_is_read_and_new_checks_are_sent(self):
        self.connected()
        with patch("runtime.synchronization.read_snapshot", wraps=read_snapshot) as reader:
            await self.ctx.tick(self.save)
            self.save.write_bytes(save_bytes([
                self.m.binding_flag, *[self.m.check_flag(i) for i in self.m.locations[:2]]]))
            await self.ctx.tick(self.save)
            self.assertEqual(reader.call_count, 2)
        self.assertEqual(self.state.checks(), set(self.m.locations[:2]))
        self.assertIn({"cmd": "LocationChecks", "locations": list(self.m.locations[:2])}, self.ctx.sent)

    async def test_deleted_or_rolled_back_save_cannot_reuse_cached_success(self):
        self.connected()
        await self.ctx.tick(self.save)
        self.save.unlink()
        with self.assertRaises(OSError):
            await self.ctx.tick(self.save)
        self.assertNotIn("eu4ap_scan = yes", self.sync.output.read_text())
        self.save.write_bytes(save_bytes([self.m.binding_flag]))
        with self.assertRaisesRegex(ValueError, "checks disappeared"):
            await self.ctx.tick(self.save)
        self.assertNotIn("eu4ap_scan = yes", self.sync.output.read_text())

    async def test_save_changed_during_parse_is_not_cached_or_reported(self):
        self.connected()

        def changing_reader(path, country):
            snapshot = read_snapshot(path, country)
            path.write_bytes(save_bytes([self.m.binding_flag], date="1446.1.1"))
            return snapshot

        with patch("runtime.synchronization.read_snapshot", side_effect=changing_reader):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                await self.ctx.tick(self.save)
        self.assertEqual(self.state.checks(), set())
        self.assertEqual(self.ctx.sent, [])
        await self.ctx.tick(self.save)
        self.assertEqual(self.state.get("save_date"), "1446.1.1")

    async def test_external_script_change_is_repaired_without_reparsing_save(self):
        self.connected()
        with patch("runtime.synchronization.read_snapshot", wraps=read_snapshot) as reader:
            await self.ctx.tick(self.save)
            self.sync.output.write_text("# replaced externally\n")
            await self.ctx.tick(self.save)
            self.assertEqual(reader.call_count, 1)
        self.assertIn("eu4ap_scan = yes", self.sync.output.read_text())
