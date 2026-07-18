import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "docs"))

from install import remove_stale_vibemon_hooks  # noqa: E402


VIBEMON_ENTRY = {
    "hooks": [
        {"type": "command", "command": "python3 ~/.codex/hooks/vibemon.py"}
    ]
}
USER_ENTRY = {
    "hooks": [{"type": "command", "command": "python3 ~/my-hook.py"}]
}
NEW_HOOKS = {"Stop": [VIBEMON_ENTRY]}


class RemoveStaleVibemonHooksTest(unittest.TestCase):
    def test_vibemon_only_event_is_deleted(self):
        existing = {"PostToolUse": [VIBEMON_ENTRY], "Stop": [VIBEMON_ENTRY]}
        removed = remove_stale_vibemon_hooks(existing, NEW_HOOKS)
        self.assertEqual(removed, ["PostToolUse"])
        self.assertNotIn("PostToolUse", existing)
        self.assertIn("Stop", existing)

    def test_user_hooks_under_stale_event_are_preserved(self):
        existing = {
            "PostToolUse": [
                {
                    "hooks": [
                        {"type": "command", "command": "python3 ~/.codex/hooks/vibemon.py"},
                        {"type": "command", "command": "python3 ~/my-hook.py"},
                    ]
                }
            ]
        }
        removed = remove_stale_vibemon_hooks(existing, NEW_HOOKS)
        self.assertEqual(removed, ["PostToolUse"])
        self.assertEqual(
            existing["PostToolUse"],
            [{"hooks": [{"type": "command", "command": "python3 ~/my-hook.py"}]}],
        )

    def test_events_in_new_hooks_are_untouched(self):
        existing = {"Stop": [VIBEMON_ENTRY, USER_ENTRY]}
        removed = remove_stale_vibemon_hooks(existing, NEW_HOOKS)
        self.assertEqual(removed, [])
        self.assertEqual(existing["Stop"], [VIBEMON_ENTRY, USER_ENTRY])

    def test_kiro_format_args_entry_is_removed(self):
        existing = {
            "postToolUse": [
                {"command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "postToolUse"]}
            ],
            "stop": [
                {"command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "agentStop"]}
            ],
        }
        new_hooks = {"stop": existing["stop"]}
        removed = remove_stale_vibemon_hooks(existing, new_hooks)
        self.assertEqual(removed, ["postToolUse"])
        self.assertNotIn("postToolUse", existing)
        self.assertIn("stop", existing)

    def test_non_vibemon_stale_event_is_kept(self):
        existing = {"PostToolUse": [USER_ENTRY]}
        removed = remove_stale_vibemon_hooks(existing, NEW_HOOKS)
        self.assertEqual(removed, [])
        self.assertEqual(existing["PostToolUse"], [USER_ENTRY])


if __name__ == "__main__":
    unittest.main()
