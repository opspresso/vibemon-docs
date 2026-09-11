import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "vibemon"))
sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "claude"))


class StatuslineCacheTest(unittest.TestCase):
    def test_save_to_cache_writes_project_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            cache_path = str(Path(directory) / "projects.json")
            os.environ["VIBEMON_CACHE_PATH"] = cache_path
            try:
                statusline = importlib.import_module("statusline")
                statusline.save_to_cache("my-project", "Fable 5", 42)

                with open(cache_path) as f:
                    cache = json.load(f)
            finally:
                del os.environ["VIBEMON_CACHE_PATH"]

            entry = cache["my-project"]
            self.assertEqual(entry["model"], "Fable 5")
            self.assertEqual(entry["memory"], 42)
            self.assertIn("ts", entry)


class ReadInputTest(unittest.TestCase):
    def test_reads_payload_decoded_as_utf8(self):
        from statusline import read_input

        stdin = io.StringIO('{"model": {"display_name": "Claude 한국"}}')
        with patch.object(sys, "stdin", stdin):
            content = read_input()

        self.assertIn('"display_name": "Claude 한국"', content)


class UsageSegmentTest(unittest.TestCase):
    def test_usage_segment_includes_model_scoped_week_bar(self):
        statusline = importlib.import_module("statusline")
        segment = statusline.build_usage_segment({
            "session": {"pct": 5},
            "week_all": {"pct": 7},
            "week_fable": {"pct": 12, "label": "Fable"},
        })

        self.assertIn("S ", segment)
        self.assertIn("W ", segment)
        self.assertIn("F ", segment)

    def test_usage_segment_without_model_week_has_no_extra_bar(self):
        statusline = importlib.import_module("statusline")
        segment = statusline.build_usage_segment({
            "session": {"pct": 5},
            "week_all": {"pct": 7},
        })

        self.assertIn("S ", segment)
        self.assertIn("W ", segment)
        self.assertNotIn("F ", segment)


if __name__ == "__main__":
    unittest.main()
