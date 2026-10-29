import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.helpers import ROOT


class PackagingTests(unittest.TestCase):
    def test_reproducible_archives_and_portable_client(self):
        spec = importlib.util.spec_from_file_location("build_eu4", ROOT / "scripts/build_apworld.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = builder.build(root / "first")
            second = builder.build(root / "second")
            self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest() for p in first],
                             [hashlib.sha256(p.read_bytes()).hexdigest() for p in second])
            with zipfile.ZipFile(first[0]) as world:
                self.assertIn("eu4/__init__.py", world.namelist())
                self.assertIn("eu4/archipelago.json", world.namelist())
                self.assertIn("eu4/runtime/connection.py", world.namelist())
                self.assertIn("eu4/launcher.py", world.namelist())
                self.assertIn("eu4/runtime/gui.py", world.namelist())
                metadata = json.loads(world.read("archipelago.json"))
                self.assertEqual(metadata["compatible_version"], 7)
                self.assertEqual(metadata["version"], 7)
                self.assertEqual(metadata["game"], "Europa Universalis IV")
                self.assertFalse(any("__pycache__" in n for n in world.namelist()))
            tools = builder.build_tools(root / "tools")
            with zipfile.ZipFile(tools[0]) as client:
                client.extractall(root / "client")
            result = subprocess.run([sys.executable, "-m", "eu4_client", "--help"],
                                    cwd=root / "client", capture_output=True, text=True, check=True)
            self.assertIn("install-mod", result.stdout)
            with zipfile.ZipFile(first[3]) as kit:
                self.assertIn("eu4.apworld", kit.namelist())
                self.assertIn("example.yaml", kit.namelist())
                self.assertIn("docs/installation.md", kit.namelist())
                self.assertFalse(any("poc" in n.lower() for n in kit.namelist()))
            metadata = json.loads(first[2].read_text())
            self.assertEqual(metadata["version"], "0.3.1")
            for artifact in first:
                sums = (artifact.parent / "SHA256SUMS").read_text()
                self.assertIn(f"{hashlib.sha256(artifact.read_bytes()).hexdigest()}  {artifact.name}", sums)
            demos = builder.build_demo(root / "demos")
            with zipfile.ZipFile(demos[0]) as mod:
                self.assertIn("eu4_archipelago.mod", mod.namelist())
                self.assertIn("eu4_archipelago/descriptor.mod", mod.namelist())
                self.assertEqual(json.loads(mod.read("eu4_archipelago/eu4ap_manifest.json"))["seed"], "OFFLINE-POC")

    def test_process_lock_prevents_competing_writers_and_releases(self):
        from runtime.locking import ProcessLock
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lock"
            first = ProcessLock(path)
            try:
                with self.assertRaises(ValueError):
                    ProcessLock(path)
            finally:
                first.close()
            second = ProcessLock(path)
            second.close()
