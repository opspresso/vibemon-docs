import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
