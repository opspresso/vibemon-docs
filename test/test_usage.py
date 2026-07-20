import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "vibemon"))

import usage  # noqa: E402


def _fake_urlopen(payload):
    class _Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    return lambda *args, **kwargs: _Response(json.dumps(payload).encode())


class UsageTest(unittest.TestCase):
    def test_claude_live_usage_parses_limits_array(self):
        payload = {
            "five_hour": {"utilization": 5.0, "resets_at": "2026-07-20T06:10:00+00:00"},
            "seven_day": {"utilization": 7.0, "resets_at": "2026-07-24T17:00:00+00:00"},
            "seven_day_opus": None,
            "limits": [
                {"kind": "session", "percent": 5, "resets_at": "2026-07-20T06:10:00+00:00"},
                {"kind": "weekly_all", "percent": 7, "resets_at": "2026-07-24T17:00:00+00:00"},
                {
                    "kind": "weekly_scoped",
                    "percent": 12,
                    "resets_at": "2026-07-24T17:00:00+00:00",
                    "scope": {"model": {"id": None, "display_name": "Fable"}},
                },
            ],
        }
        with (
            patch.object(usage, "read_claude_token", return_value="token"),
            patch.object(usage.urllib.request, "urlopen", _fake_urlopen(payload)),
        ):
            result = usage.fetch_claude_usage_live()

        self.assertEqual(result["session"]["pct"], 5)
        self.assertEqual(result["week_all"]["pct"], 7)
        self.assertEqual(result["week_fable"]["pct"], 12)
        self.assertEqual(result["week_fable"]["label"], "Fable")
        self.assertIn("resets_at", result["week_fable"])

    def test_claude_live_usage_falls_back_to_legacy_buckets(self):
        payload = {
            "five_hour": {"utilization": 5.0, "resets_at": "2026-07-20T06:10:00+00:00"},
            "seven_day": {"utilization": 7.0, "resets_at": "2026-07-24T17:00:00+00:00"},
        }
        with (
            patch.object(usage, "read_claude_token", return_value="token"),
            patch.object(usage.urllib.request, "urlopen", _fake_urlopen(payload)),
        ):
            result = usage.fetch_claude_usage_live()

        self.assertEqual(result["session"]["pct"], 5)
        self.assertEqual(result["week_all"]["pct"], 7)
        self.assertNotIn("week_fable", result)

    def test_codex_windows_are_classified_by_duration(self):
        self.assertEqual(usage._codex_window_kind({"window_minutes": 300}), "session")
        self.assertEqual(usage._codex_window_kind({"window_minutes": 10080}), "week_all")
        self.assertIsNone(usage._codex_window_kind({"window_minutes": 43200}))
        self.assertEqual(
            usage._codex_window_kind({"limit_window_seconds": 5 * 3600}),
            "session",
        )

    def test_codex_session_fallback_does_not_report_month_as_session(self):
        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / "session.jsonl"
            session_path.write_text(json.dumps({
                "payload": {
                    "rate_limits": {
                        "primary": {
                            "used_percent": 42,
                            "window_minutes": 43200,
                            "resets_at": 2000,
                        }
                    }
                }
            }))
            with patch.object(usage, "CODEX_SESSIONS_DIR", directory):
                self.assertIsNone(usage.get_codex_usage_from_sessions())

    def test_codex_session_fallback_handles_week_only_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            session_path = Path(directory) / "session.jsonl"
            session_path.write_text(json.dumps({
                "payload": {
                    "rate_limits": {
                        "primary": {
                            "used_percent": 42,
                            "window_minutes": 10080,
                            "resets_at": 2000,
                        }
                    }
                }
            }))
            with patch.object(usage, "CODEX_SESSIONS_DIR", directory):
                result = usage.get_codex_usage_from_sessions()

        self.assertNotIn("session", result)
        self.assertEqual(result["week_all"]["pct"], 42)

    def test_main_refreshes_only_missing_provider(self):
        cache = {
            "claude": {
                "updated_at": 100,
                "session": {"pct": 10, "updated_at": 100},
            }
        }
        with (
            patch.object(sys, "argv", ["usage.py", "--max-age", "600"]),
            patch.object(usage, "load_usage_cache", side_effect=[cache, cache]),
            patch.object(usage, "available_providers", return_value={"claude", "codex"}),
            patch.object(usage.time, "time", return_value=200),
            patch.object(usage, "refresh_usage", return_value="busy") as refresh,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(usage.main(), 0)

        refresh.assert_called_once_with({"codex"})

    def test_main_refreshes_when_model_week_bucket_is_stale(self):
        # statusline.py keeps session/week_all fresh on every render, but the
        # model-scoped weekly bucket (week_fable) only refreshes via the API
        # path — a stale one must force a refresh or it decays and vanishes.
        cache = {
            "claude": {
                "updated_at": 10000,
                "session": {"pct": 10, "updated_at": 10000},
                "week_all": {"pct": 8, "updated_at": 10000},
                "week_fable": {"pct": 12, "label": "Fable", "updated_at": 100},
            }
        }
        with (
            patch.object(sys, "argv", ["usage.py", "--max-age", "600"]),
            patch.object(usage, "load_usage_cache", return_value=cache),
            patch.object(usage, "available_providers", return_value={"claude"}),
            patch.object(usage.time, "time", return_value=10100),
            patch.object(usage, "refresh_usage", return_value="busy") as refresh,
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(usage.main(), 0)

        refresh.assert_called_once_with({"claude"})

    def test_main_skips_refresh_when_only_installed_provider_is_fresh(self):
        cache = {
            "claude": {
                "updated_at": 100,
                "session": {"pct": 10, "updated_at": 100},
            }
        }
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["usage.py", "--max-age", "600"]),
            patch.object(usage, "load_usage_cache", return_value=cache),
            patch.object(usage, "available_providers", return_value={"claude"}),
            patch.object(usage.time, "time", return_value=200),
            patch.object(usage, "refresh_usage") as refresh,
            redirect_stdout(output),
        ):
            self.assertEqual(usage.main(), 0)

        refresh.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), cache)

    def test_refresh_reports_cache_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = str(Path(directory) / "usage.json")
            with (
                patch.object(usage, "get_usage_cache_path", return_value=cache_path),
                patch.object(
                    usage,
                    "fetch_claude_usage_live",
                    return_value={"session": {"pct": 1}},
                ),
                patch.object(usage, "save_usage_cache", return_value=False),
            ):
                self.assertEqual(usage.refresh_usage({"claude"}), "failed-to-save")

    def test_main_returns_failure_when_cache_write_fails(self):
        error = io.StringIO()
        with (
            patch.object(sys, "argv", ["usage.py"]),
            patch.object(usage, "load_usage_cache", return_value=None),
            patch.object(usage, "refresh_usage", return_value="failed-to-save"),
            redirect_stdout(io.StringIO()),
            redirect_stderr(error),
        ):
            self.assertEqual(usage.main(), 1)

        self.assertIn("cache write failed", error.getvalue())


if __name__ == "__main__":
    unittest.main()
