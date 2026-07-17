import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "vibemon"))

from usage_cache import (  # noqa: E402
    get_fresh_provider,
    parse_usage_output,
    save_usage_cache,
    usage_from_rate_limits,
)


class UsageCacheTest(unittest.TestCase):
    def test_rate_limits_are_clamped_and_keep_absolute_reset(self):
        usage = usage_from_rate_limits({
            "rate_limits": {
                "five_hour": {"used_percentage": 140, "resets_at": 2000},
                "seven_day": {"used_percentage": -4, "resets_at": "1970-01-01T01:00:00Z"},
            }
        })

        self.assertEqual(usage["session"], {"pct": 100, "resets_at": 2000.0})
        self.assertEqual(usage["week_all"], {"pct": 0, "resets_at": 3600.0})

    def test_text_parser_ignores_malformed_lines(self):
        usage = parse_usage_output(
            "Current session: unavailable\n"
            "Current week (all models): 37% used · resets tomorrow"
        )

        self.assertNotIn("session", usage)
        self.assertEqual(usage["week_all"], {"pct": 37, "resets": "tomorrow"})

    def test_provider_timestamps_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = str(Path(directory) / "usage.json")
            save_usage_cache(cache_path, {"claude": {"session": {"pct": 10}}}, now=100)
            save_usage_cache(cache_path, {"codex": {"session": {"pct": 20}}}, now=200)
            cache = json.loads(Path(cache_path).read_text())

        self.assertEqual(cache["claude"]["updated_at"], 100)
        self.assertEqual(cache["codex"]["updated_at"], 200)
        self.assertIsNone(get_fresh_provider(cache, "claude", 50, now=200))
        self.assertEqual(
            get_fresh_provider(cache, "codex", 50, now=200)["session"]["pct"],
            20,
        )

    def test_legacy_global_timestamp_remains_readable(self):
        cache = {"ts": 100, "claude": {"session": {"pct": 10}}}

        self.assertIsNotNone(get_fresh_provider(cache, "claude", 10, now=105))
        self.assertIsNone(get_fresh_provider(cache, "claude", 10, now=111))


if __name__ == "__main__":
    unittest.main()
