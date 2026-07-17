import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from generate_manifest import (  # noqa: E402
    DOCS_DIR,
    MANIFEST_FILES,
    MANIFEST_PATH,
    build_manifest,
)


class ManifestTest(unittest.TestCase):
    def test_manifest_files_exist(self):
        for rel in MANIFEST_FILES:
            self.assertTrue((DOCS_DIR / rel).is_file(), f"missing manifest source file: {rel}")

    def test_manifest_matches_files(self):
        """docs/manifest.json must be regenerated whenever a listed file changes.

        Run `python3 scripts/generate_manifest.py` to fix a failure here.
        """
        self.assertTrue(MANIFEST_PATH.is_file(), "docs/manifest.json is missing")
        on_disk = json.loads(MANIFEST_PATH.read_text())
        self.assertEqual(build_manifest(), on_disk)

    def test_manifest_hashes_are_sha256_hex(self):
        manifest = json.loads(MANIFEST_PATH.read_text())
        self.assertIsInstance(manifest.get("files"), dict)
        for rel, digest in manifest["files"].items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", f"bad digest for {rel}")


if __name__ == "__main__":
    unittest.main()
