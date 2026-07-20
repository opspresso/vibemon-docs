import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "docs" / "vibemon"))

import vibemon_core  # noqa: E402


EVENT_STATE_MAP = {"SessionStart": "start", "Stop": "done"}


def run_hook(event: dict, argv: list[str] | None = None) -> list[dict]:
    """Drive vibemon_core.run() with a stdin event; return sent payloads."""
    sent: list[dict] = []

    def build_payload(state, tool, project, data):
        return {"state": state, "tool": tool, "project": project}

    def capture_send(payload, is_start):
        sent.append(payload)

    stdin = io.StringIO(json.dumps(event))
    with (
        patch.object(sys, "argv", ["vibemon.py"] + (argv or [])),
        patch.object(sys, "stdin", stdin),
        patch.object(vibemon_core, "send_to_all", capture_send),
        redirect_stderr(io.StringIO()),
    ):
        vibemon_core.run(
            event_state_map=EVENT_STATE_MAP,
            build_payload=build_payload,
            start_event="SessionStart",
        )
    return sent


class UsageFieldsTest(unittest.TestCase):
    def test_usage_fields_include_model_scoped_week(self):
        with patch.object(vibemon_core.time, "time", return_value=1000):
            fields = vibemon_core._usage_fields({
                "session": {"pct": 5, "resets_at": 1600},
                "week_all": {"pct": 7, "resets_at": 7000},
                "week_fable": {"pct": 12, "resets_at": 7000, "label": "Fable"},
            })

        self.assertEqual(fields["usage5h"], 5)
        self.assertEqual(fields["usageWeek"], 7)
        self.assertEqual(fields["usageWeekModel"], 12)
        self.assertEqual(fields["usageWeekModelResetsIn"], 100)
        self.assertEqual(fields["usageWeekModelLabel"], "Fable")

    def test_usage_fields_omit_model_week_when_absent(self):
        fields = vibemon_core._usage_fields({
            "session": {"pct": 5},
            "week_all": {"pct": 7},
        })

        self.assertNotIn("usageWeekModel", fields)
        self.assertNotIn("usageWeekModelLabel", fields)


class VibemonHomeGuardTest(unittest.TestCase):
    def test_session_in_vibemon_home_is_not_reported(self):
        vibemon_home = os.path.expanduser("~/.vibemon")
        sent = run_hook({"hook_event_name": "SessionStart", "cwd": vibemon_home})
        self.assertEqual(sent, [])

    def test_suppress_env_still_skips_reporting(self):
        with patch.dict(os.environ, {"VIBEMON_SUPPRESS_HOOKS": "1"}):
            sent = run_hook({"hook_event_name": "SessionStart", "cwd": "/tmp"})
        self.assertEqual(sent, [])

    def test_regular_project_session_is_reported(self):
        sent = run_hook({"hook_event_name": "SessionStart", "cwd": "/tmp"})
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["state"], "start")

    def test_unmapped_event_is_skipped(self):
        # e.g. a PostToolUse registration left behind by an older install
        sent = run_hook({"hook_event_name": "PostToolUse", "cwd": "/tmp"})
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
