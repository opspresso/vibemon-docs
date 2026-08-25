#!/usr/bin/env python3
"""
Regenerate docs/manifest.json — the sha256 manifest of every file install.py
copies verbatim into the user's home directory, plus the sha256 of install.py
itself (the "installer" key). The VibeMon Desktop app fetches this manifest
periodically and compares the hashes against the installed local files to
detect out-of-date scripts, and verifies the downloaded install.py against
the installer hash before running it.

Merged config files (claude/settings.json, codex/hooks.json, codex/config.toml)
are excluded: their installed form is merged with user content and can never
match the source hash.

Usage:
  python3 scripts/generate_manifest.py
"""

import hashlib
import json
from pathlib import Path

DOCS_DIR = Path(__file__).parents[1] / "docs"
MANIFEST_PATH = DOCS_DIR / "manifest.json"

# Keep in sync with the write_file_with_diff() calls in docs/install.py.
MANIFEST_FILES = [
    "vibemon/usage.py",
    "vibemon/usage_cache.py",
    "vibemon/vibemon_core.py",
    "claude/statusline.py",
    "claude/hooks/vibemon.py",
    "codex/hooks/vibemon.py",
    "kiro/hooks/vibemon.py",
    "kiro/hooks/vibemon.json",
    "openclaw/extensions/index.mjs",
    "openclaw/extensions/openclaw.plugin.json",
]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict:
    return {
        "installer": file_sha256(DOCS_DIR / "install.py"),
        "files": {rel: file_sha256(DOCS_DIR / rel) for rel in MANIFEST_FILES},
    }


def main():
    manifest = build_manifest()
    # newline="": a CRLF manifest would not match the LF one CI publishes, so
    # regenerating on Windows must produce the same bytes as on Linux.
    with open(MANIFEST_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST_PATH} ({len(manifest['files'])} files)")


if __name__ == "__main__":
    main()
