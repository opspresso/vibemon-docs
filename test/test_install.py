import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "docs"))

import install  # noqa: E402
from install import ensure_codex_status_line, remove_stale_vibemon_hooks  # noqa: E402


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


class EnsureCodexStatusLineTest(unittest.TestCase):
    def test_adds_tui_section(self):
        result = ensure_codex_status_line("[features]\nhooks = true\n")
        self.assertIn("[tui]\nstatus_line = [", result)
        self.assertIn('"context-used"', result)
        self.assertIn('"context-window-size"', result)

    def test_preserves_existing_items_and_adds_missing_items(self):
        config = '[tui]\nstatus_line = [\n  "model-name",\n]\n'
        result = ensure_codex_status_line(config)
        self.assertIn('"model-name"', result)
        self.assertIn('"context-used"', result)
        self.assertIn('"context-window-size"', result)

    def test_inserts_parent_before_nested_tui_table(self):
        config = '[tui.model_availability_nux]\n"gpt-5.5" = 4\n'
        result = ensure_codex_status_line(config)
        self.assertLess(result.index("[tui]"), result.index("[tui.model_availability_nux]"))

    def test_is_idempotent(self):
        once = ensure_codex_status_line("[features]\nhooks = true\n")
        self.assertEqual(ensure_codex_status_line(once), once)


if __name__ == "__main__":
    unittest.main()


class StripAllVibemonHooksTest(unittest.TestCase):
    def test_removes_vibemon_and_keeps_user_hooks(self):
        existing = {"Stop": [VIBEMON_ENTRY, USER_ENTRY], "PreToolUse": [VIBEMON_ENTRY]}
        changed = install.strip_all_vibemon_hooks(existing)
        self.assertEqual(sorted(changed), ["PreToolUse", "Stop"])
        self.assertEqual(existing, {"Stop": [USER_ENTRY]})

    def test_no_vibemon_hooks_is_a_noop(self):
        existing = {"Stop": [USER_ENTRY]}
        self.assertEqual(install.strip_all_vibemon_hooks(existing), [])
        self.assertEqual(existing, {"Stop": [USER_ENTRY]})


class RenamedVibemonCommandTest(unittest.TestCase):
    """A hook whose command moved must not survive under a still-used event.

    merge_hooks() dedupes by command, so the renamed entry is *added*; without
    this cleanup the old one keeps invoking a script the installer removed.
    """

    def test_stale_command_under_active_event_is_removed(self):
        moved = {
            "hooks": [{"type": "command", "command": "python3 ~/.vibemon/hooks/vibemon.py"}]
        }
        existing = {"Stop": [VIBEMON_ENTRY, USER_ENTRY]}
        removed = remove_stale_vibemon_hooks(existing, {"Stop": [moved]})
        self.assertEqual(removed, ["Stop"])
        self.assertEqual(existing["Stop"], [USER_ENTRY])

    def test_matching_command_is_kept(self):
        existing = {"Stop": [VIBEMON_ENTRY]}
        self.assertEqual(remove_stale_vibemon_hooks(existing, NEW_HOOKS), [])
        self.assertEqual(existing["Stop"], [VIBEMON_ENTRY])

    def test_kiro_args_rename_is_removed(self):
        existing = {"stop": [{"command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "agentStop"]}]}
        renamed = {"stop": [{"command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "onStop"]}]}
        self.assertEqual(remove_stale_vibemon_hooks(existing, renamed), ["stop"])
        self.assertNotIn("stop", existing)


class AskYesNoTest(unittest.TestCase):
    def setUp(self):
        self._saved = (install.AUTO_APPROVE, install.NON_INTERACTIVE)

    def tearDown(self):
        install.AUTO_APPROVE, install.NON_INTERACTIVE = self._saved

    def test_auto_approve_answers_yes_even_when_unattended_is_false(self):
        install.AUTO_APPROVE, install.NON_INTERACTIVE = True, True
        self.assertTrue(install.ask_yes_no("?", unattended=False))

    def test_unattended_answer_is_used_without_yes_flag(self):
        install.AUTO_APPROVE, install.NON_INTERACTIVE = False, True
        # statusLine-style prompt: leave the user's setting alone.
        self.assertFalse(install.ask_yes_no("?", unattended=False))
        # Owned-file upgrade prompt: proceed.
        self.assertTrue(install.ask_yes_no("?", unattended=True))

    def test_unattended_falls_back_to_default(self):
        install.AUTO_APPROVE, install.NON_INTERACTIVE = False, True
        self.assertTrue(install.ask_yes_no("?", default=True))
        self.assertFalse(install.ask_yes_no("?", default=False))


class SelectedPlatformsTest(unittest.TestCase):
    class Args:
        def __init__(self, **kw):
            for key in ("claude", "codex", "kiro", "openclaw", "vibemon", "all"):
                setattr(self, key, kw.get(key, False))

    def test_all_expands_to_the_four_tools(self):
        self.assertEqual(
            install.selected_platforms(self.Args(all=True)), list(install.ALL_PLATFORMS)
        )

    def test_flags_keep_a_stable_order(self):
        args = self.Args(openclaw=True, claude=True)
        self.assertEqual(install.selected_platforms(args), ["claude", "openclaw"])

    def test_no_flags_means_show_the_menu(self):
        self.assertEqual(install.selected_platforms(self.Args()), [])


class ReportAndExitTest(unittest.TestCase):
    def _exit_code(self, results):
        try:
            install.report_and_exit(results, "Install")
        except SystemExit as e:
            return e.code
        return 0

    def test_all_succeeded_exits_zero(self):
        self.assertEqual(self._exit_code([("Claude Code", True)]), 0)

    def test_partial_failure_exits_nonzero(self):
        """any() used to report exit 0 here, hiding broken installs."""
        self.assertEqual(
            self._exit_code([("Claude Code", True), ("Codex CLI", False)]), 1
        )

    def test_skipped_tool_does_not_fail_the_run(self):
        self.assertEqual(
            self._exit_code([("Claude Code", True), ("Kiro IDE", install.SKIPPED)]), 0
        )

    def test_everything_skipped_exits_nonzero(self):
        self.assertEqual(self._exit_code([("Kiro IDE", install.SKIPPED)]), 1)


class WriteTextAtomicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "settings.json"

    def test_creates_file_with_requested_mode(self):
        install.write_text_atomic(self.path, "{}\n", mode=0o600)
        self.assertEqual(self.path.read_text(), "{}\n")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_preserves_existing_mode(self):
        self.path.write_text("old")
        os.chmod(self.path, 0o600)
        install.write_text_atomic(self.path, "new")
        self.assertEqual(self.path.read_text(), "new")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_leaves_no_temp_file_behind(self):
        install.write_text_atomic(self.path, "x")
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["settings.json"])

    def test_original_survives_a_failed_write(self):
        self.path.write_text("original")
        with mock.patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                install.write_text_atomic(self.path, "replacement")
        self.assertEqual(self.path.read_text(), "original")
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["settings.json"])


class BackupFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        install.BACKED_UP.clear()
        self.addCleanup(install.BACKED_UP.clear)
        self.path = Path(self.tmp.name) / "settings.json"

    def test_backs_up_a_valid_file(self):
        self.path.write_text("valid")
        install.backup_file(self.path)
        self.assertEqual((self.path.with_suffix(".json.bak")).read_text(), "valid")

    def test_backs_up_only_once_per_run(self):
        self.path.write_text("first")
        install.backup_file(self.path)
        self.path.write_text("second")
        install.backup_file(self.path)
        self.assertEqual((self.path.with_suffix(".json.bak")).read_text(), "first")

    def test_missing_file_is_a_noop(self):
        install.backup_file(self.path)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])


class VerifyContentTest(unittest.TestCase):
    def setUp(self):
        self._saved = dict(install.REMOTE_MANIFEST)
        install.REMOTE_MANIFEST.clear()

    def tearDown(self):
        install.REMOTE_MANIFEST.clear()
        install.REMOTE_MANIFEST.update(self._saved)

    def test_matching_hash_passes(self):
        content = "print('hi')\n"
        digest = hashlib.sha256(content.encode()).hexdigest()
        install.REMOTE_MANIFEST["claude/statusline.py"] = digest
        install.verify_content("claude/statusline.py", content)  # no raise

    def test_mismatched_hash_raises(self):
        install.REMOTE_MANIFEST["claude/statusline.py"] = "0" * 64
        with self.assertRaises(install.IntegrityError):
            install.verify_content("claude/statusline.py", "tampered")

    def test_unmanifested_path_is_not_checked(self):
        install.verify_content("claude/settings.json", "anything")  # no raise
