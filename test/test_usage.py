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


class UsageTest(unittest.TestCase):
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
