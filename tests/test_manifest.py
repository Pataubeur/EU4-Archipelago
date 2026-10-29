import json
from pathlib import Path
import tempfile
import unittest

from tests.helpers import manifest
from runtime.manifest import Manifest


class ManifestInputTests(unittest.TestCase):
    def test_bad_files_raise_actionable_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.apeu4.json"
            for data in ("not JSON", "[]", "{}", '{"locations": "oops"}',
                         '{"locations": [], "slot": "one"}'):
                with self.subTest(data=data):
                    path.write_text(data, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "supplied by the multiworld host"):
                        Manifest.read(path)

    def test_bom_and_invalid_identity_types(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.apeu4.json"
            original = manifest()
            original.write(path)
            path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8-sig")
            self.assertEqual(Manifest.read(path), original)
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for key, bad in (("slot", True), ("seed", 123), ("locations", ["id"] * 10)):
                with self.subTest(key=key):
                    changed = dict(data, **{key: bad})
                    path.write_text(json.dumps(changed), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "field types"):
                        Manifest.read(path)
