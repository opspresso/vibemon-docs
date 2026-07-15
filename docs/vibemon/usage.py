#!/usr/bin/env python3
"""
VibeMon Plan-Usage Cache Refresher

Fetches Claude Code plan usage via `claude -p "/usage"` and stores it in the
shared usage cache (~/.vibemon/cache/usage.json) — the same file that
~/.claude/statusline.py and the platform hooks read.

Intended to be run by the VibeMon Desktop app on startup or on a schedule, so
usage data stays fresh even when no Claude Code session is rendering the
statusline. Uses the same lock protocol as statusline.py, so concurrent
refreshes from either side never collide.

Usage:
  python3 ~/.vibemon/usage.py                 # refresh now
  python3 ~/.vibemon/usage.py --max-age 600   # skip when cache is newer than 600s

Prints the resulting usage cache JSON to stdout. Exit code 0 on success
(refreshed, fresh enough, or another refresh already in flight), 1 on failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

CLAUDE_TIMEOUT_SECONDS = 30


# ============================================================================
# Cache Path Resolution
# ============================================================================


def get_usage_cache_path() -> str:
    """Resolve the usage cache path next to the shared projects cache.

    Honors the cache_path setting in ~/.vibemon/config.json so every VibeMon
    component agrees on where the cache directory lives.
    """
    cache_path = "~/.vibemon/cache/projects.json"
    config_file = os.path.expanduser("~/.vibemon/config.json")
    try:
        with open(config_file) as f:
            config = json.load(f)
        if isinstance(config, dict) and config.get("cache_path"):
            cache_path = str(config["cache_path"])
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        pass
    cache_dir = os.path.dirname(os.path.expanduser(cache_path))
    return os.path.join(cache_dir, "usage.json")


# ============================================================================
# Usage Parsing (mirrors ~/.claude/statusline.py)
# ============================================================================


def parse_usage_output(text: str) -> dict[str, Any]:
    """Parse `claude -p "/usage"` output into a usage dict.

    Matches lines by keyword so format tweaks degrade gracefully:

        Current session: 36% used · resets Jun 12 at 3:20pm (Asia/Seoul)
        Current week (all models): 37% used · resets ...
        Current week (Sonnet only): 0% used

    Returns {} if nothing parseable is found.
    """
    result: dict[str, Any] = {}
    if not text:
        return result

    def _pct(line: str) -> int | None:
        m = re.search(r"(\d+)%\s+used", line)
        return int(m.group(1)) if m else None

    def _resets(line: str) -> str:
        m = re.search(r"resets\s+(.+?)\s*$", line)
        return m.group(1).strip() if m else ""

    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if "current session:" in low:
            pct = _pct(line)
            if pct is not None:
                entry: dict[str, Any] = {"pct": pct}
                resets = _resets(line)
                if resets:
                    entry["resets"] = resets
                result["session"] = entry
        elif "current week (all models):" in low:
            pct = _pct(line)
            if pct is not None:
                entry = {"pct": pct}
                resets = _resets(line)
                if resets:
                    entry["resets"] = resets
                result["week_all"] = entry
        elif "current week (sonnet only):" in low:
            pct = _pct(line)
            if pct is not None:
                result["week_sonnet"] = {"pct": pct}

    return result


def apply_session_floor(usage: dict[str, Any]) -> dict[str, Any]:
    """Floor the 5-hour session pct to 1 when the weekly window has usage but
    the session reads 0 (typical right after a session reset), so its bar
    stays visible alongside the weekly bar instead of being hidden.
    """
    session = usage.get("session")
    week = usage.get("week_all")
    if (
        isinstance(week, dict)
        and isinstance(week.get("pct"), int)
        and week["pct"] >= 1
        and isinstance(session, dict)
        and session.get("pct") == 0
    ):
        return {**usage, "session": {**session, "pct": 1}}
    return usage


# ============================================================================
# Cache I/O (same lock protocol as ~/.claude/statusline.py)
# ============================================================================


def load_usage_cache() -> dict[str, Any] | None:
    """Load cached plan usage, or None if missing/unreadable."""
    try:
        with open(get_usage_cache_path()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None


def save_usage_cache(usage: dict[str, Any]) -> None:
    """Atomically write the usage cache (stamps a fresh `ts`).

    A single non-blocking lock attempt: losing an occasional write to a
    concurrent statusline render is harmless since the data is equivalent.
    """
    cache_path = get_usage_cache_path()
    lock_fd = None
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        if fcntl is not None:
            lockfile = f"{cache_path}.lock"
            lock_fd = os.open(lockfile, os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return  # Another writer holds it; its data is just as fresh
        payload = dict(usage)
        payload["ts"] = int(time.time())
        tmpfile = f"{cache_path}.tmp.{os.getpid()}"
        with open(tmpfile, "w") as f:
            json.dump(payload, f)
        os.replace(tmpfile, cache_path)
    except (IOError, OSError):
        pass
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def refresh_usage() -> str:
    """Fetch `claude -p "/usage"` and refresh the cache.

    A non-blocking lock ensures only one refresh runs at a time across this
    script and statusline.py's background refresh; the guard lock is released
    before writing since save_usage_cache() takes its own lock on the same
    file. Returns "refreshed", "busy" (another refresh in flight), or
    "failed" (subprocess error or unparseable output).
    """
    lockfile = f"{get_usage_cache_path()}.lock"
    lock_fd = None
    usage: dict[str, Any] = {}
    try:
        os.makedirs(os.path.dirname(lockfile), exist_ok=True)
        if fcntl is not None:
            lock_fd = os.open(lockfile, os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return "busy"

        try:
            result = subprocess.run(
                ["claude", "-p", "/usage"],
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return "failed"

        usage = parse_usage_output(result.stdout)
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass

    if not usage:
        return "failed"
    save_usage_cache(apply_session_floor(usage))
    return "refreshed"


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the VibeMon plan-usage cache via `claude -p /usage`"
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=0,
        metavar="SECONDS",
        help="skip the refresh when the cache is newer than this (0 = always refresh)",
    )
    args = parser.parse_args()

    cache = load_usage_cache()
    if args.max_age > 0 and isinstance(cache, dict):
        try:
            if (time.time() - float(cache.get("ts", 0))) <= args.max_age:
                print(json.dumps(cache))
                return 0
        except (TypeError, ValueError):
            pass

    if shutil.which("claude") is None:
        print("claude CLI not found in PATH", file=sys.stderr)
        return 1

    outcome = refresh_usage()
    if outcome == "failed":
        print('failed to fetch or parse `claude -p "/usage"` output', file=sys.stderr)
        return 1

    # "busy": another refresh is in flight; report the current cache as-is.
    cache = load_usage_cache()
    print(json.dumps(cache) if cache else "{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
