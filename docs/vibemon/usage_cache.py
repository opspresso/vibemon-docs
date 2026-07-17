"""Shared plan-usage parsing and cache helpers for VibeMon."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


def parse_epoch(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None
    return None


def normalize_percent(value: Any) -> int | None:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return None


def usage_from_rate_limits(data: dict[str, Any]) -> dict[str, Any] | None:
    rate_limits = data.get("rate_limits")
    if not isinstance(rate_limits, dict):
        return None

    def _entry(bucket: Any) -> dict[str, Any] | None:
        if not isinstance(bucket, dict):
            return None
        pct = normalize_percent(bucket.get("used_percentage"))
        if pct is None:
            return None
        entry: dict[str, Any] = {"pct": pct}
        resets_at = parse_epoch(bucket.get("resets_at"))
        if resets_at is not None:
            entry["resets_at"] = resets_at
        return entry

    session = _entry(rate_limits.get("five_hour"))
    week = _entry(rate_limits.get("seven_day"))
    if session is None and week is None:
        return None
    result: dict[str, Any] = {}
    if session is not None:
        result["session"] = session
    if week is not None:
        result["week_all"] = week
    return result


def parse_usage_output(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not text:
        return result

    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        match = re.search(r"(\d+(?:\.\d+)?)%\s+used", line)
        pct = normalize_percent(match.group(1)) if match else None
        if pct is None:
            continue
        entry: dict[str, Any] = {"pct": pct}
        reset_match = re.search(r"resets\s+(.+?)\s*$", line)
        if reset_match:
            entry["resets"] = reset_match.group(1).strip()
        if "current session:" in low:
            result["session"] = entry
        elif "current week (all models):" in low:
            result["week_all"] = entry
        elif "current week (sonnet only):" in low:
            result["week_sonnet"] = entry
    return result


def apply_session_floor(usage: dict[str, Any]) -> dict[str, Any]:
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


def load_usage_cache(cache_path: str) -> dict[str, Any] | None:
    try:
        with open(cache_path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None


def provider_updated_at(cache: dict[str, Any] | None, provider: str) -> float:
    if not isinstance(cache, dict):
        return 0
    data = cache.get(provider)
    if isinstance(data, dict):
        try:
            return float(data.get("updated_at", cache.get("ts", 0)))
        except (TypeError, ValueError):
            return 0
    return 0


def get_fresh_provider(
    cache: dict[str, Any] | None,
    provider: str,
    max_age_seconds: int,
    now: float | None = None,
) -> dict[str, Any] | None:
    if not isinstance(cache, dict):
        return None
    data = cache.get(provider)
    if not isinstance(data, dict):
        return None
    observed_at = provider_updated_at(cache, provider)
    current_time = time.time() if now is None else now
    if observed_at <= 0 or current_time - observed_at > max_age_seconds:
        return None
    return data


def save_usage_cache(cache_path: str, updates: dict[str, Any], now: float | None = None) -> bool:
    lock_fd = None
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        if fcntl is not None:
            lock_fd = os.open(f"{cache_path}.lock", os.O_CREAT | os.O_WRONLY, 0o644)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                return False

        payload = dict(load_usage_cache(cache_path) or {})
        updated_at = int(time.time() if now is None else now)
        for provider, value in updates.items():
            if not isinstance(value, dict):
                continue
            payload[provider] = {**value, "updated_at": updated_at}
        # Retain ts for older installed hooks; freshness decisions use the
        # provider-level updated_at above.
        payload["ts"] = updated_at
        tmpfile = f"{cache_path}.tmp.{os.getpid()}"
        with open(tmpfile, "w") as f:
            json.dump(payload, f)
        os.replace(tmpfile, cache_path)
        return True
    except (IOError, OSError):
        return False
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass
