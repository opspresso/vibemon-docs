#!/usr/bin/env python3
"""
VibeMon Plan-Usage Cache Refresher

Fetches Claude Code and Codex CLI plan usage and stores it in the shared
usage cache (~/.vibemon/cache/usage.json) — the same file that
~/.claude/statusline.py and the platform hooks read.

Claude: Anthropic's OAuth usage API (the same endpoint the official /usage
command uses, queried directly with the local Claude Code login token — no
active session required), falling back to a `claude -p "/usage"` subprocess
when a login token isn't available or the API call fails.

Codex: the same account-level usage API Codex CLI's own `/status` polls,
queried with the local Codex login token, falling back to the newest local
session log.

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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from usage_cache import (
    apply_session_floor,
    load_usage_cache as _load_usage_cache,
    normalize_percent,
    parse_epoch,
    parse_usage_output,
    provider_updated_at,
    save_usage_cache as _save_usage_cache,
)

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

CLAUDE_TIMEOUT_SECONDS = 30
CLAUDE_TOKEN_TIMEOUT_SECONDS = 3
CLAUDE_API_TIMEOUT_SECONDS = 8
CLAUDE_USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
CLAUDE_CREDENTIALS_FILE = os.path.expanduser("~/.claude/.credentials.json")

CODEX_AUTH_FILE = os.path.expanduser("~/.codex/auth.json")
CODEX_SESSIONS_DIR = os.path.expanduser("~/.codex/sessions")
CODEX_USAGE_API_URL = "https://chatgpt.com/backend-api/wham/usage"
CODEX_FIVE_HOUR_MAX_SECONDS = 6 * 3600


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
# Live Usage via Anthropic OAuth API (works without an active session)
# ============================================================================


def read_claude_token() -> str | None:
    """Read the local Claude Code OAuth access token, or None if unavailable.

    The token is returned only in memory — never logged, printed, or written
    to disk beyond its existing credential store.

    macOS: reads the Keychain item Claude Code itself logs into
    ("Claude Code-credentials"). Falls back to the plain-JSON credentials
    file (~/.claude/.credentials.json) for non-macOS installs and manual
    migrations that use the same token shape.
    """
    if sys.platform == "darwin":
        try:
            raw = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True,
                text=True,
                timeout=CLAUDE_TOKEN_TIMEOUT_SECONDS,
            ).stdout.strip()
            token = json.loads(raw).get("claudeAiOauth", {}).get("accessToken")
            if token:
                return token
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, AttributeError):
            pass
    try:
        with open(CLAUDE_CREDENTIALS_FILE) as f:
            data = json.load(f)
        return data.get("claudeAiOauth", {}).get("accessToken")
    except (FileNotFoundError, json.JSONDecodeError, IOError, AttributeError):
        return None


def fetch_claude_usage_live() -> dict[str, Any] | None:
    """Fetch plan usage directly from Anthropic's OAuth usage API — the same
    endpoint the official /usage command uses — via the local Claude Code
    login token. Unlike the `claude -p "/usage"` text fallback below, this
    needs no active session and returns an exact reset timestamp.

    Returns the same shape as parse_usage_output() (`session`/`week_all`
    entries with `pct` and `resets_at`), or None if a token isn't available,
    the request fails, or the response doesn't look like a usage payload.
    """
    token = read_claude_token()
    if not token:
        return None

    request = urllib.request.Request(
        CLAUDE_USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=CLAUDE_API_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None

    def _window(bucket: Any) -> dict[str, Any] | None:
        if not isinstance(bucket, dict):
            return None
        try:
            pct = normalize_percent(bucket.get("utilization"))
        except (TypeError, ValueError):
            return None
        if pct is None:
            return None
        entry: dict[str, Any] = {"pct": pct}
        resets_at = parse_epoch(bucket.get("resets_at"))
        if resets_at is not None:
            entry["resets_at"] = resets_at
        return entry

    session = _window(data.get("five_hour"))
    week = _window(data.get("seven_day"))
    if session is None and week is None:
        return None

    result: dict[str, Any] = {}
    if session is not None:
        result["session"] = session
    if week is not None:
        result["week_all"] = week
    return result


# ============================================================================
# Codex: Live Usage via ChatGPT API (falls back to local session logs)
# ============================================================================


def read_codex_token() -> tuple[str, str] | None:
    """Read the local Codex CLI OAuth token, or None if unavailable.

    Codex CLI stores its login as a plain JSON file (no OS keychain
    involved), so this works the same way on every platform. The token is
    returned only in memory — never logged, printed, or written to disk
    beyond its existing credential store.
    """
    try:
        with open(CODEX_AUTH_FILE) as f:
            data = json.load(f)
        tokens = data.get("tokens", {})
        token = tokens.get("access_token")
        if not token:
            return None
        return token, tokens.get("account_id", "")
    except (FileNotFoundError, json.JSONDecodeError, IOError, AttributeError):
        return None


def fetch_codex_usage_live() -> dict[str, Any] | None:
    """Fetch plan usage directly from the same account-level usage endpoint
    Codex CLI's own `/status` polls, via the local Codex login token. Needs
    no active session and costs no tokens.

    Returns the same shape as fetch_claude_usage_live() (`session`/
    `week_all` entries with `pct` and `resets_at`), or None if a token isn't
    available, the request fails, or the response has no usable window.
    Credit-balance (premium) plans with no percentage window are skipped —
    there's no meaningful `pct` to report for those.
    """
    creds = read_codex_token()
    if creds is None:
        return None
    token, account_id = creds

    request = urllib.request.Request(
        CODEX_USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "ChatGPT-Account-Id": account_id,
            "User-Agent": "codex-cli",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=CLAUDE_API_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None

    def _window(bucket: Any) -> dict[str, Any] | None:
        if not isinstance(bucket, dict):
            return None
        try:
            pct = normalize_percent(bucket.get("used_percent"))
        except (TypeError, ValueError):
            return None
        if pct is None:
            return None
        entry: dict[str, Any] = {"pct": pct}
        resets_at = parse_epoch(bucket.get("reset_at"))
        if resets_at is not None:
            entry["resets_at"] = resets_at
        return entry

    rate_limit = data.get("rate_limit") if isinstance(data.get("rate_limit"), dict) else {}
    # primary_window/secondary_window aren't fixed to 5h/weekly — whichever
    # window is currently active comes back as "primary". Classify by its
    # actual length instead (mirrors claude-codex-battery's approach).
    session: dict[str, Any] | None = None
    week: dict[str, Any] | None = None
    for raw_window in (rate_limit.get("primary_window"), rate_limit.get("secondary_window")):
        if not isinstance(raw_window, dict):
            continue
        window_seconds = raw_window.get("limit_window_seconds") or 0
        if window_seconds and window_seconds <= CODEX_FIVE_HOUR_MAX_SECONDS:
            session = _window(raw_window)
        else:
            week = _window(raw_window)

    if session is None and week is None:
        return None

    result: dict[str, Any] = {}
    if session is not None:
        result["session"] = session
    if week is not None:
        result["week_all"] = week
    return result


def get_codex_usage_from_sessions() -> dict[str, Any] | None:
    """Fall back to the newest local Codex session log when the live API is
    unavailable — the same `rate_limits` snapshot Codex CLI itself writes to
    `~/.codex/sessions/**/*.jsonl` as it runs.

    Returns the same shape as fetch_codex_usage_live(), or None if no
    session log has a usable rate_limits entry.
    """
    if not os.path.isdir(CODEX_SESSIONS_DIR):
        return None

    files: list[tuple[str, float]] = []
    for dirpath, _dirnames, filenames in os.walk(CODEX_SESSIONS_DIR):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, name)
            try:
                files.append((path, os.path.getmtime(path)))
            except OSError:
                continue
    files.sort(key=lambda item: item[1], reverse=True)

    def _window(bucket: Any) -> dict[str, Any] | None:
        if not isinstance(bucket, dict):
            return None
        try:
            pct = normalize_percent(bucket.get("used_percent"))
        except (TypeError, ValueError):
            return None
        if pct is None:
            return None
        entry: dict[str, Any] = {"pct": pct}
        resets_at = parse_epoch(bucket.get("resets_at"))
        if resets_at is not None:
            entry["resets_at"] = resets_at
        return entry

    for path, _mtime in files[:8]:
        try:
            with open(path, "r", errors="ignore") as f:
                lines = f.read().splitlines()
        except (IOError, OSError):
            continue
        for line in reversed(lines):
            if "rate_limits" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else obj
            rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
            if not isinstance(rate_limits, dict):
                continue
            session = _window(rate_limits.get("primary"))
            week = _window(rate_limits.get("secondary"))
            if session is None and week is None:
                continue
            result: dict[str, Any] = {}
            if session is not None:
                result["session"] = session
            if week is not None:
                result["week_all"] = week
            return result

    return None


# ============================================================================
# Cache I/O (same lock protocol as ~/.claude/statusline.py)
# ============================================================================


def load_usage_cache() -> dict[str, Any] | None:
    """Load cached plan usage, or None if missing/unreadable."""
    return _load_usage_cache(get_usage_cache_path())


def save_usage_cache(usage: dict[str, Any]) -> None:
    """Merge provider updates and stamp each provider independently."""
    _save_usage_cache(get_usage_cache_path(), usage)


def refresh_usage() -> str:
    """Refresh the usage cache for Claude and Codex independently, so one
    provider's outage doesn't block the other's refresh.

    Claude: Anthropic's OAuth usage API directly (no active session
    required), falling back to `claude -p "/usage"` when a token can't be
    found or the API call fails. Codex: the ChatGPT usage API, falling back
    to the newest local session log.

    A non-blocking lock ensures only one refresh runs at a time across this
    script and statusline.py's background refresh; the guard lock is released
    before writing since save_usage_cache() takes its own lock on the same
    file. Returns "refreshed", "busy" (another refresh in flight), or
    "failed" (neither provider produced usable data).
    """
    lockfile = f"{get_usage_cache_path()}.lock"
    lock_fd = None
    claude_usage: dict[str, Any] | None = None
    codex_usage: dict[str, Any] | None = None
    try:
        os.makedirs(os.path.dirname(lockfile), exist_ok=True)
        if fcntl is not None:
            lock_fd = os.open(lockfile, os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return "busy"

        claude_usage = fetch_claude_usage_live()
        if claude_usage is None:
            try:
                result = subprocess.run(
                    ["claude", "-p", "/usage"],
                    capture_output=True,
                    text=True,
                    timeout=CLAUDE_TIMEOUT_SECONDS,
                )
                claude_usage = parse_usage_output(result.stdout) or None
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                claude_usage = None

        codex_usage = fetch_codex_usage_live() or get_codex_usage_from_sessions()
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass

    if not claude_usage and not codex_usage:
        return "failed"

    cache: dict[str, Any] = {}
    if claude_usage:
        cache["claude"] = apply_session_floor(claude_usage)
    if codex_usage:
        cache["codex"] = codex_usage
    save_usage_cache(cache)
    return "refreshed"


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the VibeMon plan-usage cache from Anthropic's usage API "
        '(falls back to `claude -p /usage`)'
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
        providers = [name for name in ("claude", "codex") if isinstance(cache.get(name), dict)]
        if providers and all(
            time.time() - provider_updated_at(cache, name) <= args.max_age
            for name in providers
        ):
            print(json.dumps(cache))
            return 0

    outcome = refresh_usage()
    if outcome == "failed":
        print(
            "failed to refresh usage: no Claude or Codex source was available",
            file=sys.stderr,
        )
        return 1

    # "busy": another refresh is in flight; report the current cache as-is.
    cache = load_usage_cache()
    print(json.dumps(cache) if cache else "{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
