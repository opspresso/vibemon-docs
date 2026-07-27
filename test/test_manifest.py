import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parents[1] / "docs"))

from generate_manifest import (  # noqa: E402
    DOCS_DIR,
    MANIFEST_FILES,
    MANIFEST_PATH,
    build_manifest,
)
import install  # noqa: E402

# Paths install.py downloads but that must NOT be in the manifest: the merged
# configs (their installed form is user content + ours, so they can never match
# a source hash) and the config examples (copied into ~/.vibemon only as
# defaults for a file the user then edits).
UNMANIFESTED = {
    "claude/settings.json",
    "codex/hooks.json",
    "codex/config.toml",
    "kiro/agents/default.json",
    install.CONFIG_EXAMPLE_FILE,
    install.STATUSLINE_EXAMPLE_FILE,
}


def downloaded_paths() -> set:
    """Every source path install.py fetches, read back out of its own code."""
    source = (Path(install.__file__)).read_text(encoding="utf-8")
    paths = set(re.findall(r'get_file\(f?"([^"{]+)"', source))
    # Some fetches pass a module constant instead of a literal.
    for name in set(re.findall(r"get_file\(([A-Z][A-Z0-9_]*)\)", source)):
        paths.add(getattr(install, name))
    # The Kiro hook files are fetched through an f-string over KIRO_HOOK_FILES.
    paths.update(f"kiro/hooks/{name}" for name in install.KIRO_HOOK_FILES)
    return paths


class ManifestTest(unittest.TestCase):
    def test_manifest_files_exist(self):
        for rel in MANIFEST_FILES:
            self.assertTrue((DOCS_DIR / rel).is_file(), f"missing manifest source file: {rel}")

    def test_manifest_matches_files(self):
        """docs/manifest.json must be regenerated whenever a listed file changes.

        Run `python3 scripts/generate_manifest.py` to fix a failure here.
        """
        self.assertTrue(MANIFEST_PATH.is_file(), "docs/manifest.json is missing")
        on_disk = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(build_manifest(), on_disk)

    def test_manifest_hashes_are_sha256_hex(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest.get("files"), dict)
        for rel, digest in manifest["files"].items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", f"bad digest for {rel}")

    def test_manifest_list_matches_installer(self):
        """MANIFEST_FILES must list exactly what install.py copies verbatim.

        generate_manifest.py asks for this to be kept in sync by hand. A file
        added to install.py but missed here silently drops out of the integrity
        check, so assert it instead of trusting the comment.
        """
        expected = downloaded_paths() - UNMANIFESTED
        self.assertEqual(
            expected,
            set(MANIFEST_FILES),
            "MANIFEST_FILES is out of sync with install.py's downloads — "
            "update scripts/generate_manifest.py (or UNMANIFESTED here if the "
            "new file is a merged config)",
        )

    def test_unmanifested_paths_are_really_downloaded(self):
        """Guard the exclusion list itself against going stale."""
        self.assertLessEqual(UNMANIFESTED, downloaded_paths())


if __name__ == "__main__":
    unittest.main()
