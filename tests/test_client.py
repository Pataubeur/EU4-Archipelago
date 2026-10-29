import asyncio
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tests.helpers import ROOT, manifest, save_bytes
from tests import test_bridge
from runtime.client import Profile, Session
from runtime.json_state import JsonState
from runtime.manifest import Manifest
from runtime.locking import ProcessLock


class JsonSyncTests(test_bridge.SyncTests):
    """Run the bridge's replay, rollback and recovery contract on frozen storage."""
    state_class = JsonState


class ProfileTests(unittest.TestCase):
    def test_install_requires_user_folder_and_online_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = Profile(user_dir=str(root))
            with self.assertRaisesRegex(ValueError, "Documents"):
                profile.install()
            (root / "save games").mkdir()
            profile.manifest = str(root / "poc.apeu4.json")
            manifest(seed="OFFLINE-POC").write(Path(profile.manifest))
            with self.assertRaisesRegex(ValueError, "démonstration"):
                profile.install()
            self.assertFalse((root / "mod").exists())

    def test_reinstall_and_seed_switch_preserve_save_state_and_previous_mod(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "save games").mkdir()
            save = root / "save games/campaign.eu4"
            save.write_bytes(b"precious user save")
            profile = Profile(manifest=str(root / "seed.apeu4.json"), user_dir=str(root))
            first = manifest()
            first.write(Path(profile.manifest))
            state = profile.state_path(first)
            state.parent.mkdir(parents=True)
            state.write_bytes(b"preserved campaign history")
            mod = profile.install()
            (mod / "user-notes.txt").write_bytes(b"keep this too")
            profile.install()
            self.assertFalse((root / "eu4ap/mod-backups").exists())
            manifest(seed="SECOND").write(Path(profile.manifest))
            profile.install()
            backup = list((root / "eu4ap/mod-backups").iterdir())
            self.assertEqual(len(backup), 1)
            self.assertEqual(Manifest.read(backup[0] / "eu4ap_manifest.json"), first)
            self.assertEqual((backup[0] / "user-notes.txt").read_bytes(), b"keep this too")
            self.assertEqual(state.read_bytes(), b"preserved campaign history")
            self.assertEqual(save.read_bytes(), b"precious user save")

    def test_settings_roundtrip_drops_password_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps({"name": "Alice", "server": "example.org:1234", "password": "secret"}))
            profile = Profile.load(path)
            profile.write(path)
            self.assertEqual(Profile.load(path), profile)
            self.assertNotIn("secret", path.read_text())

    def test_campaign_state_is_stable_on_save_rename_and_isolated_per_seed(self):
        profile = Profile(user_dir="user", save="first.eu4")
        path = profile.state_path(manifest())
        profile.save = "renamed.eu4"
        self.assertEqual(path, profile.state_path(manifest()))
        self.assertNotEqual(path, profile.state_path(manifest(seed="OTHER")))

    def test_atomic_failure_does_not_advance_in_memory_or_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = JsonState(path, "token")
            with patch("runtime.json_state.atomic_text", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    state.receive(0, [(1, 2, 3, 4)])
            self.assertEqual(state.items(), [])
            self.assertEqual(JsonState(path, "token").items(), [])

    def test_corrupt_existing_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text('{"schema": 1, "meta": {}, "items": [], "checks": {}}')
            with self.assertRaises(ValueError):
                JsonState(path, "token")

    def test_launcher_registers_without_importing_gui(self):
        launcher = types.ModuleType("worlds.LauncherComponents")
        launcher.components = []
        launcher.Component = lambda *a, **kw: (a, kw)
        launcher.Type = types.SimpleNamespace(CLIENT="client")
        launcher.SuffixIdentifier = lambda suffix: suffix
        launcher.launch_subprocess = lambda *a, **kw: None
        package = types.ModuleType("eu4_registration_test")
        package.__path__ = [str(ROOT / "apworld/eu4")]
        # Use a synthetic package, avoiding imports of AP's World/Options.
        with patch.dict(sys.modules, {"eu4_registration_test": package,
                                      "worlds.LauncherComponents": launcher}):
            importlib.import_module("eu4_registration_test.launcher")
            self.assertEqual(launcher.components[0][0], ("EU4 Client",))
            self.assertEqual(launcher.components[0][1]["file_identifier"], ".apeu4.json")
            self.assertNotIn("eu4_registration_test.runtime.gui", sys.modules)
        for key in list(sys.modules):
            if key.startswith("eu4_registration_test."):
                del sys.modules[key]


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_closes_context_and_releases_directory_lock(self):
        class Context:
            def __init__(self, sync, *args):
                self.sync = sync
                self.exit_event = asyncio.Event()
                self.validated = True
                self.slot = 1
                self.sync_error = ""
                self.blocked = False
                self.closed = False

            async def tick(self, save):
                self.sync.poll(save)

            def status(self):
                return "connected"

            async def shutdown(self):
                self.closed = True
                await self.server_task

        async def server_loop(ctx):
            await ctx.exit_event.wait()

        common = types.ModuleType("CommonClient")
        common.server_loop = server_loop
        connection = types.ModuleType("runtime.connection")
        connection.EU4Context = Context
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            m = manifest()
            (root / "save games").mkdir()
            m.write(root / "manifest.json")
            (root / "save.eu4").write_bytes(save_bytes([m.binding_flag]))
            profile = Profile(str(root / "manifest.json"), str(root / "save.eu4"), str(root), "localhost:1", "Player")
            session = Session(profile)
            contexts = []

            def report(_):
                contexts.append(session.context)
                session.stop()

            with patch.dict(sys.modules, {"CommonClient": common, "runtime.connection": connection}):
                await session.run(report)
            self.assertTrue(contexts[0].closed)
            self.assertIsNone(session.context)
            lock = ProcessLock(root / "eu4ap_client.lock")
            lock.close()
