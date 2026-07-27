import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "docs"))

import install  # noqa: E402
from install import ensure_codex_status_line, remove_stale_vibemon_hooks  # noqa: E402


# Windows has no POSIX permission bits — os.chmod there only toggles a
# read-only attribute, so st_mode always reads back 0o666.
POSIX_ONLY = unittest.skipIf(os.name == "nt", "POSIX file modes")

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

    @POSIX_ONLY
    def test_creates_file_with_requested_mode(self):
        install.write_text_atomic(self.path, "{}\n", mode=0o600)
        self.assertEqual(self.path.read_text(), "{}\n")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    @POSIX_ONLY
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
        with mock.patch.object(install.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                install.write_text_atomic(self.path, "replacement")
        self.assertEqual(self.path.read_text(), "original")
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir()], ["settings.json"])

    def test_line_endings_are_preserved_verbatim(self):
        """The installed bytes have to hash to the manifest value on every OS.

        Text-mode writes translate \\n to \\r\\n on Windows, which would leave
        every installed script permanently mismatched against manifest.json.
        """
        install.write_text_atomic(self.path, "a\nb\n")
        self.assertEqual(self.path.read_bytes(), b"a\nb\n")


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


DOCS_DIR = Path(__file__).parents[1] / "docs"
CLAUDE_SETTINGS = json.loads((DOCS_DIR / "claude" / "settings.json").read_text(encoding="utf-8"))
CODEX_HOOKS = json.loads((DOCS_DIR / "codex" / "hooks.json").read_text(encoding="utf-8"))


class WindowsFake:
    """Pretend to be Windows with a known Python and home directory."""

    PYTHON = "C:/Python313/python.exe"
    HOME = "C:/Users/dev"

    def __enter__(self):
        self._patches = [
            mock.patch.object(install, "IS_WINDOWS", True),
            mock.patch.object(install.sys, "executable", self.PYTHON),
            mock.patch.object(install.Path, "home", staticmethod(lambda: Path(self.HOME))),
            mock.patch.object(install, "has_git_bash", lambda: True),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self._patches):
            patch.stop()
        return False


class PosixFake:
    """Pin the platform to POSIX, so the "adapters are a no-op here" contract
    can be asserted from any runner.

    Without it these tests only assert anything on a POSIX machine: on the
    Windows CI runner the adapters correctly rewrite the config and the
    assertion inverts.
    """

    def __enter__(self):
        self._patch = mock.patch.object(install, "IS_WINDOWS", False)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        return False


class AdaptClaudeSettingsTest(unittest.TestCase):
    def test_posix_output_is_byte_identical_to_the_packaged_file(self):
        """Existing POSIX installs must not see a single changed character."""
        settings = json.loads(json.dumps(CLAUDE_SETTINGS))
        with PosixFake():
            self.assertEqual(install.adapt_claude_settings(settings), CLAUDE_SETTINGS)

    def test_windows_hooks_use_exec_form(self):
        with WindowsFake():
            settings = install.adapt_claude_settings(json.loads(json.dumps(CLAUDE_SETTINGS)))
        hook = settings["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertEqual(hook["command"], WindowsFake.PYTHON)
        self.assertEqual(hook["args"], [f"{WindowsFake.HOME}/.claude/hooks/vibemon.py"])
        # Untouched fields survive the rewrite.
        self.assertTrue(hook["async"])
        self.assertEqual(hook["timeout"], 10)

    def test_windows_hooks_never_keep_a_tilde(self):
        """PowerShell does not expand `~` in argument position."""
        with WindowsFake():
            settings = install.adapt_claude_settings(json.loads(json.dumps(CLAUDE_SETTINGS)))
        self.assertNotIn("~", json.dumps(settings))
        self.assertNotIn("python3", json.dumps(settings))

    def test_windows_statusline_stays_shell_form(self):
        """statusLine has no exec form, so it must remain a single string."""
        with WindowsFake():
            settings = install.adapt_claude_settings(json.loads(json.dumps(CLAUDE_SETTINGS)))
        status_line = settings["statusLine"]
        self.assertNotIn("args", status_line)
        self.assertEqual(
            status_line["command"],
            f"{WindowsFake.PYTHON} {WindowsFake.HOME}/.claude/statusline.py",
        )


class WindowsShellCommandTest(unittest.TestCase):
    PY = "C:/Python313/python.exe"
    PY_SPACED = "C:/Program Files/Python313/python.exe"
    SCRIPT_SPACED = "C:/Users/a b/.claude/statusline.py"

    def test_space_free_paths_are_shell_agnostic(self):
        for git_bash in (True, False):
            with mock.patch.object(install, "has_git_bash", lambda: git_bash):
                self.assertEqual(
                    install.windows_shell_command(self.PY, "C:/Users/dev/x.py"),
                    f"{self.PY} C:/Users/dev/x.py",
                )

    def test_a_quoted_argument_alone_stays_shell_agnostic(self):
        """Only a quoted *command* forces the PowerShell call operator."""
        for git_bash in (True, False):
            with mock.patch.object(install, "has_git_bash", lambda: git_bash):
                self.assertEqual(
                    install.windows_shell_command(self.PY, self.SCRIPT_SPACED),
                    f'{self.PY} "{self.SCRIPT_SPACED}"',
                )

    def test_quoted_command_gets_an_ampersand_only_without_git_bash(self):
        with mock.patch.object(install, "has_git_bash", lambda: True):
            self.assertEqual(
                install.windows_shell_command(self.PY_SPACED, "C:/Users/dev/x.py"),
                f'"{self.PY_SPACED}" C:/Users/dev/x.py',
            )
        with mock.patch.object(install, "has_git_bash", lambda: False):
            self.assertEqual(
                install.windows_shell_command(self.PY_SPACED, "C:/Users/dev/x.py"),
                f'& "{self.PY_SPACED}" C:/Users/dev/x.py',
            )


class AdaptCodexHooksTest(unittest.TestCase):
    def test_posix_output_is_unchanged(self):
        hooks = json.loads(json.dumps(CODEX_HOOKS))
        with PosixFake():
            self.assertEqual(install.adapt_codex_hooks(hooks), CODEX_HOOKS)

    def test_windows_override_is_added_beside_the_posix_command(self):
        with WindowsFake():
            hooks = install.adapt_codex_hooks(json.loads(json.dumps(CODEX_HOOKS)))
        hook = hooks["hooks"]["Stop"][0]["hooks"][0]
        self.assertEqual(hook["command"], "python3 ~/.codex/hooks/vibemon.py")
        self.assertEqual(
            hook["commandWindows"],
            f"{WindowsFake.PYTHON} {WindowsFake.HOME}/.codex/hooks/vibemon.py",
        )


KIRO_AGENT = json.loads((DOCS_DIR / "kiro" / "agents" / "default.json").read_text(encoding="utf-8"))
KIRO_HOOK_FILE = (DOCS_DIR / "kiro" / "hooks" / "vibemon-file-created.kiro.hook").read_text(
    encoding="utf-8"
)


class AdaptKiroTest(unittest.TestCase):
    def test_posix_agent_is_unchanged(self):
        agent = json.loads(json.dumps(KIRO_AGENT))
        with PosixFake():
            self.assertEqual(install.adapt_kiro_agent(agent), KIRO_AGENT)

    def test_posix_hook_file_is_returned_verbatim(self):
        """These files are hashed in manifest.json, so POSIX must not touch them."""
        with PosixFake():
            self.assertEqual(install.adapt_kiro_hook_file(KIRO_HOOK_FILE), KIRO_HOOK_FILE)

    def test_windows_agent_keeps_the_event_name_argument(self):
        with WindowsFake():
            agent = install.adapt_kiro_agent(json.loads(json.dumps(KIRO_AGENT)))
        hook = agent["hooks"]["agentSpawn"][0]
        self.assertEqual(hook["command"], WindowsFake.PYTHON)
        self.assertEqual(
            hook["args"],
            [f"{WindowsFake.HOME}/.kiro/hooks/vibemon.py", "agentSpawn"],
        )

    def test_windows_hook_file_command_keeps_the_event_name(self):
        with WindowsFake():
            adapted = json.loads(install.adapt_kiro_hook_file(KIRO_HOOK_FILE))
        self.assertEqual(
            adapted["then"]["command"],
            f"{WindowsFake.PYTHON} {WindowsFake.HOME}/.kiro/hooks/vibemon.py fileCreated",
        )
        # Everything else about the definition survives the rewrite.
        self.assertEqual(adapted["when"], {"type": "fileCreated", "patterns": ["**/*"]})
        self.assertEqual(adapted["then"]["type"], "runCommand")

    def test_windows_hook_file_has_no_tilde_or_python3(self):
        with WindowsFake():
            adapted = install.adapt_kiro_hook_file(KIRO_HOOK_FILE)
        self.assertNotIn("~", adapted)
        self.assertNotIn("python3", adapted)

    def test_a_hook_file_without_vibemon_is_left_alone(self):
        other = json.dumps({"then": {"type": "runCommand", "command": "echo hi"}})
        with WindowsFake():
            self.assertEqual(install.adapt_kiro_hook_file(other), other)


class HookIdentityTest(unittest.TestCase):
    def test_args_and_windows_override_are_part_of_the_identity(self):
        exec_form = {"command": "python.exe", "args": ["C:/x/.claude/hooks/vibemon.py"]}
        self.assertIn("vibemon.py", install._hook_identity(exec_form))
        override = {"command": "python3 ~/a.py", "commandWindows": "python.exe C:/a.py"}
        self.assertIn("C:/a.py", install._hook_identity(override))

    def test_exec_form_and_windows_override_are_recognized_as_vibemon(self):
        self.assertTrue(
            install._is_vibemon_hook(
                {"command": "python.exe", "args": ["C:/x/.claude/hooks/vibemon.py"]}
            )
        )
        self.assertTrue(
            install._is_vibemon_hook(
                {"command": "echo hi", "commandWindows": "python.exe C:/x/vibemon.py"}
            )
        )
        self.assertFalse(install._is_vibemon_hook({"command": "python.exe", "args": ["x.py"]}))

    def test_a_user_hook_sharing_the_interpreter_does_not_shadow_ours(self):
        """Deduping on `command` alone would drop the VibeMon hook entirely."""
        existing = [{"hooks": [{"type": "command", "command": "python.exe", "args": ["fmt.py"]}]}]
        ours = {"hooks": [{"type": "command", "command": "python.exe", "args": ["vibemon.py"]}]}
        kept = install.filter_new_hooks(ours, install.get_hook_identities(existing))
        self.assertEqual(kept, ours)

    def test_an_identical_exec_form_hook_is_deduped(self):
        entry = {"hooks": [{"type": "command", "command": "python.exe", "args": ["vibemon.py"]}]}
        self.assertIsNone(
            install.filter_new_hooks(entry, install.get_hook_identities([entry]))
        )


class WriteFileWithDiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "vibemon.py"

    def test_crlf_copy_is_rewritten_instead_of_reported_unchanged(self):
        """An older Windows install wrote CRLF; its hash never matches the manifest.

        A text comparison sees no difference, so the file would stay mismatched
        forever and the Desktop app would keep reporting an update.
        """
        self.path.write_bytes(b"print('x')\r\n")
        self.assertTrue(install.write_file_with_diff(self.path, "print('x')\n", "hook"))
        self.assertEqual(self.path.read_bytes(), b"print('x')\n")

    def test_identical_bytes_are_left_alone(self):
        self.path.write_bytes(b"print('x')\n")
        before = self.path.stat().st_mtime_ns
        self.assertTrue(install.write_file_with_diff(self.path, "print('x')\n", "hook"))
        self.assertEqual(self.path.stat().st_mtime_ns, before)


class UninstallHooksFromJsonTest(unittest.TestCase):
    """--uninstall --codex used to leave every VibeMon hook in hooks.json.

    hooks.json *is* {"hooks": {...events...}}, so descending into "hooks" and
    then reading "hooks" again found nothing and the function returned early.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        install.BACKED_UP.clear()
        self.addCleanup(install.BACKED_UP.clear)
        self.path = Path(self.tmp.name) / "hooks.json"

    def _write(self, config):
        self.path.write_text(json.dumps(config), encoding="utf-8")

    def test_codex_shape_hooks_are_removed(self):
        self._write({"hooks": {"Stop": [VIBEMON_ENTRY]}})
        install._uninstall_hooks_from_json(self.path, [], "hooks.json")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {})

    def test_user_hooks_and_other_keys_survive(self):
        self._write({"version": 2, "hooks": {"Stop": [VIBEMON_ENTRY, USER_ENTRY]}})
        install._uninstall_hooks_from_json(self.path, [], "hooks.json")
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")),
            {"version": 2, "hooks": {"Stop": [USER_ENTRY]}},
        )
