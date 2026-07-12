#!/usr/bin/env python3
"""
VibeMon Installation Script
Installs hooks and configuration for Claude Code, Codex, Kiro IDE, or OpenClaw.

Usage (Interactive):
  curl -fsSL https://docs.vibemon.io/install.py | python3

Usage (Non-interactive for AI agents):
  curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude
  curl -fsSL https://docs.vibemon.io/install.py | python3 - --codex
  curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude --token YOUR_TOKEN
  curl -fsSL https://docs.vibemon.io/install.py | python3 - --all --yes
"""

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError


# Global flag for non-interactive mode (auto-approve all prompts)
AUTO_APPROVE = False


def setup_tty_input():
    """Reopen stdin from /dev/tty to allow interactive input when piped."""
    if not sys.stdin.isatty():
        try:
            sys.stdin = open("/dev/tty", "r")
        except OSError:
            # In non-interactive mode, this is expected and OK
            pass

# VibeMon install files base URL
DOCS_BASE_URL = "https://docs.vibemon.io"

# Shared configuration example file
CONFIG_EXAMPLE_FILE = "config.example.json"

# Claude Code statusline display configuration example file
STATUSLINE_EXAMPLE_FILE = "statusline.example.json"

# All recognized statusline-only config keys, used to migrate values out of
# a pre-split single config.json into the new statusline.json.
STATUSLINE_KEYS = frozenset({
    "token_reset_hours", "usage_enabled", "usage_refresh_seconds",
    "show_project", "show_git", "show_model", "show_tokens", "show_cost",
    "show_duration", "show_lines", "show_memory", "show_usage",
    "show_usage_reset", "show_version", "show_statusline",
})


def colored(text: str, color: str) -> str:
    """Return colored text for terminal output."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Ask a yes/no question and return the answer."""
    global AUTO_APPROVE
    if AUTO_APPROVE:
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input(f"{question} {suffix}: ").strip().lower()
        except EOFError:
            return default
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'")


def mask_token(token: str) -> str:
    """Mask a token, showing only first 4 and last 4 characters."""
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


TOKEN_PATTERN = re.compile(r"^[a-z0-9_-]{8,64}$")


def warn_if_invalid_token(token: str) -> None:
    """Print a warning if token doesn't match the expected format (8-64 chars: a-z, 0-9, _, -)."""
    if not TOKEN_PATTERN.match(token):
        print(f"  {colored('!', 'yellow')} Warning: token format looks invalid (expected 8-64 chars: a-z, 0-9, _, -)")


def configure_token(config: dict, cli_token: str = None) -> dict:
    """Configure VibeMon API token. Uses CLI token if provided, otherwise interactive."""
    global AUTO_APPROVE
    current_token = config.get("vibemon_token", "")

    print(f"\n{colored('VibeMon API Token Configuration:', 'cyan')}")
    print("  Create your own token (8-64 chars, a-z, 0-9, _, -)")

    # If token provided via CLI, use it directly
    if cli_token:
        config["vibemon_token"] = cli_token
        print(f"  {colored('✓', 'green')} Token set from CLI argument")
        return config

    # Non-interactive mode without token: keep existing or skip
    if AUTO_APPROVE:
        if current_token:
            print(f"  {colored('✓', 'green')} Token unchanged: {mask_token(current_token)}")
        else:
            print(f"  {colored('!', 'yellow')} No token configured (use --token to set)")
        return config

    # Interactive mode
    if current_token:
        print(f"  Current token: {colored(mask_token(current_token), 'yellow')}")
        if ask_yes_no("  Change token?", default=False):
            try:
                new_token = input("  Enter new token: ").strip()
                if new_token:
                    warn_if_invalid_token(new_token)
                    config["vibemon_token"] = new_token
                    print(f"  {colored('✓', 'green')} Token updated")
                else:
                    print(f"  {colored('!', 'yellow')} Token unchanged (empty input)")
            except EOFError:
                print(f"  {colored('!', 'yellow')} Token unchanged")
        else:
            print(f"  {colored('✓', 'green')} Token unchanged")
    else:
        print(f"  No token configured.")
        try:
            token = input("  Enter token (or press Enter to skip): ").strip()
            if token:
                warn_if_invalid_token(token)
                config["vibemon_token"] = token
                print(f"  {colored('✓', 'green')} Token saved")
            else:
                print(f"  {colored('!', 'yellow')} Token skipped")
        except EOFError:
            print(f"  {colored('!', 'yellow')} Token skipped")

    return config


def load_or_create_config(config_path: Path, example_content: str) -> dict:
    """Load existing config or create from example."""
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass

    # Parse example content
    try:
        return json.loads(example_content)
    except json.JSONDecodeError:
        return {
            "debug": False,
            "cache_path": "~/.vibemon/cache/projects.json",
            "auto_launch": True,
            "http_urls": [],
            "serial_port": None,
            "vibemon_url": "https://vibemon.io",
            "vibemon_token": ""
        }


def save_config(config_path: Path, config: dict) -> bool:
    """Save config to file."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        return True
    except Exception as e:
        print(f"  {colored('✗', 'red')} Failed to save config: {e}")
        return False


def load_json_or_backup(path: Path) -> dict:
    """Load JSON from path; if it's corrupt, back it up to .bak before it gets overwritten."""
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        backup_path = path.with_name(path.name + ".bak")
        try:
            backup_path.write_text(path.read_text())
            print(f"  {colored('!', 'yellow')} {path.name} had invalid JSON, backed up to {backup_path.name}")
        except OSError as e:
            print(f"  {colored('✗', 'red')} Failed to back up {path.name}: {e}")
        return {}


def download_file(url: str) -> str:
    """Download a file from URL and return its content."""
    try:
        with urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        raise RuntimeError(f"Failed to download {url}: {e}")


def show_diff(old_content: str, new_content: str, filename: str) -> bool:
    """Show unified diff between old and new content. Returns True if different."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"existing {filename}",
        tofile=f"new {filename}",
        lineterm=""
    ))

    if not diff:
        return False

    print(f"\n  {colored('Diff:', 'yellow')}")
    for line in diff[:50]:
        line = line.rstrip("\n")
        if line.startswith("+") and not line.startswith("+++"):
            print(f"    {colored(line, 'green')}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"    {colored(line, 'red')}")
        elif line.startswith("@@"):
            print(f"    {colored(line, 'cyan')}")
        else:
            print(f"    {line}")

    if len(diff) > 50:
        print(f"    {colored(f'... ({len(diff) - 50} more lines)', 'yellow')}")

    return True


def write_file_with_diff(dst: Path, content: str, description: str, executable: bool = False) -> bool:
    """Write content to a file, showing diff if it already exists."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            old_content = dst.read_text()

            if old_content == content:
                print(f"  {colored('✓', 'green')} {description} (no changes)")
                return True

            print(f"\n  {colored('!', 'yellow')} {description} already exists")
            has_diff = show_diff(old_content, content, dst.name)

            if has_diff:
                if ask_yes_no(f"  Overwrite {description}?"):
                    dst.write_text(content)
                    if executable:
                        dst.chmod(dst.stat().st_mode | 0o111)
                    print(f"  {colored('✓', 'green')} {description} (updated)")
                    return True
                else:
                    print(f"  {colored('!', 'yellow')} {description} (skipped)")
                    return False
            return False
        else:
            dst.write_text(content)
            if executable:
                dst.chmod(dst.stat().st_mode | 0o111)
            print(f"  {colored('✓', 'green')} {description}")
            return True

    except Exception as e:
        print(f"  {colored('✗', 'red')} {description}: {e}")
        return False


def get_hook_commands(hook_entries: list) -> set:
    """Extract all command strings from hook entries."""
    commands = set()
    for entry in hook_entries:
        if "hooks" in entry:
            for hook in entry.get("hooks", []):
                if "command" in hook:
                    commands.add(hook["command"])
        elif "command" in entry:
            commands.add(entry["command"])
    return commands


def filter_new_hooks(entry: dict, existing_cmds: set) -> dict:
    """Return entry with already-registered hook commands removed, or None if nothing new remains."""
    if "hooks" in entry:
        new_hook_list = [h for h in entry.get("hooks", []) if h.get("command") not in existing_cmds]
        if not new_hook_list:
            return None
        return {**entry, "hooks": new_hook_list}
    elif "command" in entry:
        return None if entry["command"] in existing_cmds else entry
    return entry


def merge_hooks(existing: dict, new_hooks: dict) -> dict:
    """Merge new hooks into existing hooks configuration (Claude format)."""
    result = {}

    for event, new_entries in new_hooks.items():
        if event not in existing:
            result[event] = new_entries
        else:
            existing_entries = existing[event]
            existing_cmds = get_hook_commands(existing_entries)
            result[event] = existing_entries.copy()

            for new_entry in new_entries:
                filtered_entry = filter_new_hooks(new_entry, existing_cmds)
                if filtered_entry is not None:
                    result[event].append(filtered_entry)

    for event in existing:
        if event not in result:
            result[event] = existing[event]

    return result


def merge_kiro_hooks(existing: dict, new_hooks: dict) -> dict:
    """Merge new hooks into existing hooks configuration (Kiro format)."""
    result = {}

    def get_kiro_hook_id(hook: dict) -> str:
        """Create unique identifier for a Kiro hook."""
        cmd = hook.get("command", "")
        args = " ".join(hook.get("args", []))
        return f"{cmd} {args}"

    for event, new_entries in new_hooks.items():
        if event not in existing:
            result[event] = new_entries
        else:
            existing_entries = existing[event]
            existing_ids = {get_kiro_hook_id(h) for h in existing_entries}
            result[event] = existing_entries.copy()

            for new_entry in new_entries:
                if get_kiro_hook_id(new_entry) not in existing_ids:
                    result[event].append(new_entry)

    for event in existing:
        if event not in result:
            result[event] = existing[event]

    return result


class FileSource:
    """Abstract file source for local or remote files."""

    def __init__(self, local_dir: Path = None):
        self.local_dir = local_dir
        self.is_online = True

        if local_dir is not None:
            # Check if running from local directory with install files
            # Files may be in local_dir/claude/ or local_dir/install/claude/
            if (local_dir / "claude").exists():
                self.is_online = False
            elif (local_dir / "install" / "claude").exists():
                self.local_dir = local_dir / "install"
                self.is_online = False

    def get_file(self, path: str) -> str:
        """Get file content from local or remote source."""
        if self.is_online:
            url = f"{DOCS_BASE_URL}/{path}"
            return download_file(url)
        else:
            return (self.local_dir / path).read_text()


def is_tool_installed(command: str, home_dir: Path) -> bool:
    """Check if a tool is installed via its CLI command or existing config directory."""
    return shutil.which(command) is not None or home_dir.exists()


# Caches the resolved token so ~/.vibemon/config.json is only configured once per run
VIBEMON_CONFIG_CACHE = {}


def configure_vibemon_config(source: FileSource, cli_token: str = None) -> str:
    """Configure ~/.vibemon/config.json once per run and return the resolved token."""
    if "token" in VIBEMON_CONFIG_CACHE:
        return VIBEMON_CONFIG_CACHE["token"]

    vibemon_home = Path.home() / ".vibemon"
    vibemon_home.mkdir(parents=True, exist_ok=True)
    config_path = vibemon_home / "config.json"
    config_content = source.get_file(CONFIG_EXAMPLE_FILE)

    print("\nConfiguring VibeMon:")
    config = load_or_create_config(config_path, config_content)

    if not config_path.exists():
        print("  Creating new config at ~/.vibemon/config.json")
    else:
        print(f"  {colored('✓', 'green')} ~/.vibemon/config.json exists")

    config = configure_token(config, cli_token)

    if save_config(config_path, config):
        print(f"  {colored('✓', 'green')} ~/.vibemon/config.json saved")

    VIBEMON_CONFIG_CACHE["token"] = config.get("vibemon_token", "")
    return VIBEMON_CONFIG_CACHE["token"]


def configure_statusline_config(source: FileSource) -> None:
    """Configure ~/.vibemon/statusline.json (Claude Code statusline display
    settings). On first creation, migrates any statusline-only keys found in
    a pre-split single config.json so existing customizations aren't reset.
    """
    vibemon_home = Path.home() / ".vibemon"
    vibemon_home.mkdir(parents=True, exist_ok=True)
    statusline_path = vibemon_home / "statusline.json"
    config_path = vibemon_home / "config.json"
    is_new = not statusline_path.exists()

    print("\nConfiguring statusline display settings:")
    statusline_content = source.get_file(STATUSLINE_EXAMPLE_FILE)
    statusline_config = load_or_create_config(statusline_path, statusline_content)

    if is_new:
        print("  Creating new config at ~/.vibemon/statusline.json")
        if config_path.exists():
            try:
                legacy = json.loads(config_path.read_text())
            except json.JSONDecodeError:
                legacy = {}
            migrated = {k: legacy[k] for k in STATUSLINE_KEYS if k in legacy}
            if migrated:
                statusline_config.update(migrated)
                print(f"  {colored('✓', 'green')} Migrated {len(migrated)} statusline setting(s) from config.json")
    else:
        print(f"  {colored('✓', 'green')} ~/.vibemon/statusline.json exists")

    if save_config(statusline_path, statusline_config):
        print(f"  {colored('✓', 'green')} ~/.vibemon/statusline.json saved")


def install_claude(source: FileSource, cli_token: str = None) -> bool:
    """Install VibeMon for Claude Code."""
    claude_home = Path.home() / ".claude"
    if not is_tool_installed("claude", claude_home):
        print(f"\n{colored('!', 'yellow')} Claude Code not detected. Skipping installation.")
        return False

    print(f"\n{colored('Installing VibeMon for Claude Code...', 'cyan')}\n")

    claude_home.mkdir(parents=True, exist_ok=True)
    (claude_home / "hooks").mkdir(parents=True, exist_ok=True)

    print("Copying files:")

    # statusline.py -> ~/.claude/statusline.py
    content = source.get_file("claude/statusline.py")
    write_file_with_diff(claude_home / "statusline.py", content, "~/.claude/statusline.py", executable=True)

    # hooks/vibemon.py -> ~/.claude/hooks/vibemon.py
    content = source.get_file("claude/hooks/vibemon.py")
    write_file_with_diff(claude_home / "hooks" / "vibemon.py", content, "~/.claude/hooks/vibemon.py", executable=True)

    # Handle settings.json
    print("\nConfiguring settings.json:")
    settings_file = claude_home / "settings.json"
    new_settings = json.loads(source.get_file("claude/settings.json"))

    if settings_file.exists():
        existing_settings = load_json_or_backup(settings_file)

        if "hooks" in existing_settings:
            existing_settings["hooks"] = merge_hooks(
                existing_settings["hooks"], new_settings["hooks"]
            )
        else:
            existing_settings["hooks"] = new_settings["hooks"]

        if "statusLine" in existing_settings:
            existing_cmd = existing_settings["statusLine"].get("command", "")
            new_cmd = new_settings["statusLine"].get("command", "")
            if existing_cmd != new_cmd:
                print(f"\n  Current statusLine: {colored(existing_cmd, 'yellow')}")
                print(f"  New statusLine:     {colored(new_cmd, 'cyan')}")
                if ask_yes_no("Replace statusLine?"):
                    existing_settings["statusLine"] = new_settings["statusLine"]
                    print(f"  {colored('✓', 'green')} statusLine updated")
                else:
                    print(f"  {colored('!', 'yellow')} statusLine unchanged")
            else:
                print(f"  {colored('✓', 'green')} statusLine already configured")
        else:
            existing_settings["statusLine"] = new_settings["statusLine"]
            print(f"  {colored('✓', 'green')} statusLine added")

        settings_file.write_text(json.dumps(existing_settings, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} hooks merged into settings.json")
    else:
        settings_file.write_text(json.dumps(new_settings, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} settings.json created")

    configure_vibemon_config(source, cli_token)
    configure_statusline_config(source)

    print(f"\n{colored('Claude Code installation complete!', 'green')}")
    return True


def ensure_feature_flag_enabled(config_text: str, key: str) -> str:
    """Ensure a boolean key is set to true within the [features] section of config.toml."""
    if re.search(rf"^{re.escape(key)}\s*=\s*true\s*$", config_text, re.MULTILINE):
        return config_text

    features_match = re.search(r"(?ms)^\[features\]\n(.*?)(?=^\[|\Z)", config_text)
    if features_match:
        section = features_match.group(0)
        if re.search(rf"^{re.escape(key)}\s*=", section, re.MULTILINE):
            section = re.sub(
                rf"^{re.escape(key)}\s*=\s*false\s*$",
                f"{key} = true",
                section,
                flags=re.MULTILINE,
            )
        else:
            section = section.rstrip() + f"\n{key} = true\n"
        return config_text[:features_match.start()] + section + config_text[features_match.end():]

    suffix = "" if config_text.endswith("\n") else "\n"
    return config_text + suffix + f"\n[features]\n{key} = true\n"


def ensure_codex_hooks_enabled(config_text: str) -> str:
    """Ensure Codex hooks feature flags are enabled in config.toml.

    Sets both the current key (`hooks`) and the deprecated alias
    (`codex_hooks`) some Codex CLI versions still read.
    """
    config_text = ensure_feature_flag_enabled(config_text, "hooks")
    config_text = ensure_feature_flag_enabled(config_text, "codex_hooks")
    return config_text


def install_codex(source: FileSource, cli_token: str = None) -> bool:
    """Install VibeMon for Codex CLI."""
    codex_home = Path.home() / ".codex"
    if not is_tool_installed("codex", codex_home):
        print(f"\n{colored('!', 'yellow')} Codex CLI not detected. Skipping installation.")
        return False

    print(f"\n{colored('Installing VibeMon for Codex CLI...', 'cyan')}\n")

    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "hooks").mkdir(parents=True, exist_ok=True)

    print("Copying files:")

    content = source.get_file("codex/hooks/vibemon.py")
    write_file_with_diff(
        codex_home / "hooks" / "vibemon.py",
        content,
        "~/.codex/hooks/vibemon.py",
        executable=True,
    )

    print("\nConfiguring hooks.json:")
    hooks_file = codex_home / "hooks.json"
    new_hooks = json.loads(source.get_file("codex/hooks.json"))

    if hooks_file.exists():
        existing_hooks = load_json_or_backup(hooks_file)

        existing_map = existing_hooks.get("hooks", {})
        new_map = new_hooks.get("hooks", {})
        existing_hooks["hooks"] = merge_hooks(existing_map, new_map)
        hooks_file.write_text(json.dumps(existing_hooks, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} hooks merged into ~/.codex/hooks.json")
    else:
        hooks_file.write_text(json.dumps(new_hooks, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} ~/.codex/hooks.json created")

    print("\nConfiguring config.toml:")
    config_toml_file = codex_home / "config.toml"
    if config_toml_file.exists():
        existing_toml = config_toml_file.read_text()
        updated_toml = ensure_codex_hooks_enabled(existing_toml)
        config_toml_file.write_text(updated_toml)
        print(f"  {colored('✓', 'green')} codex_hooks enabled in ~/.codex/config.toml")
    else:
        config_toml_file.write_text(source.get_file("codex/config.toml"))
        print(f"  {colored('✓', 'green')} ~/.codex/config.toml created")

    configure_vibemon_config(source, cli_token)

    print(f"\n{colored('Codex CLI installation complete!', 'green')}")
    print(f"\n{colored('Notes:', 'yellow')}")
    print("  • Codex hooks are experimental and currently disabled on Windows")
    print("  • Restart your Codex session after installation")
    return True


def install_kiro(source: FileSource, cli_token: str = None) -> bool:
    """Install VibeMon for Kiro IDE."""
    kiro_home = Path.home() / ".kiro"
    if not is_tool_installed("kiro", kiro_home):
        print(f"\n{colored('!', 'yellow')} Kiro IDE not detected. Skipping installation.")
        return False

    print(f"\n{colored('Installing VibeMon for Kiro IDE...', 'cyan')}\n")

    kiro_home.mkdir(parents=True, exist_ok=True)
    (kiro_home / "hooks").mkdir(parents=True, exist_ok=True)
    (kiro_home / "agents").mkdir(parents=True, exist_ok=True)

    print("Copying files:")

    # vibemon.py -> ~/.kiro/hooks/vibemon.py
    content = source.get_file("kiro/hooks/vibemon.py")
    write_file_with_diff(kiro_home / "hooks" / "vibemon.py", content, "~/.kiro/hooks/vibemon.py", executable=True)

    # Handle agents/default.json (merge, don't overwrite)
    print("\nConfiguring agents/default.json:")
    agent_file = kiro_home / "agents" / "default.json"
    new_agent = json.loads(source.get_file("kiro/agents/default.json"))

    if agent_file.exists():
        existing_agent = load_json_or_backup(agent_file)

        if "hooks" in existing_agent:
            existing_agent["hooks"] = merge_kiro_hooks(
                existing_agent["hooks"], new_agent["hooks"]
            )
            print(f"  {colored('✓', 'green')} hooks merged into agents/default.json")
        else:
            existing_agent["hooks"] = new_agent["hooks"]
            print(f"  {colored('✓', 'green')} hooks added to agents/default.json")

        agent_file.write_text(json.dumps(existing_agent, indent=2) + "\n")
    else:
        agent_file.write_text(json.dumps(new_agent, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} agents/default.json created")

    # .kiro.hook files
    kiro_hook_files = [
        "vibemon-prompt-submit.kiro.hook",
        "vibemon-agent-stop.kiro.hook",
        "vibemon-file-created.kiro.hook",
        "vibemon-file-edited.kiro.hook",
        "vibemon-file-deleted.kiro.hook",
    ]
    for hook_file in kiro_hook_files:
        content = source.get_file(f"kiro/hooks/{hook_file}")
        write_file_with_diff(kiro_home / "hooks" / hook_file, content, f"~/.kiro/hooks/{hook_file}")

    configure_vibemon_config(source, cli_token)

    print(f"\n{colored('Kiro IDE installation complete!', 'green')}")
    print(f"\n{colored('Next steps (Kiro CLI):', 'yellow')}")
    print("  Kiro CLI hooks only run on the \"default\" custom agent VibeMon just")
    print("  created (the built-in kiro_default agent can't be hooked directly).")
    print("  Activate it with: kiro-cli --agent default")
    print("  or inside a session: /agent swap default")
    return True


def ensure_plugin_path_registered(config: dict, plugin_dir: str) -> bool:
    """Ensure plugin_dir is listed in config["plugins"]["load"]["paths"].

    OpenClaw doesn't auto-discover extension directories -- plugins must be
    explicitly registered here or the manifest/entries config alone won't
    load them. Returns True if the config was changed.
    """
    if "plugins" not in config or not isinstance(config["plugins"], dict):
        config["plugins"] = {}
    plugins = config["plugins"]

    if "load" not in plugins or not isinstance(plugins["load"], dict):
        plugins["load"] = {}
    load = plugins["load"]

    if "paths" not in load or not isinstance(load["paths"], list):
        load["paths"] = []
    paths = load["paths"]

    if plugin_dir in paths:
        return False
    paths.append(plugin_dir)
    return True


def install_openclaw(source: FileSource, cli_token: str = None) -> bool:
    """Install VibeMon plugin for OpenClaw."""
    openclaw_home = Path.home() / ".openclaw"
    if not is_tool_installed("openclaw", openclaw_home):
        print(f"\n{colored('!', 'yellow')} OpenClaw not detected. Skipping installation.")
        return False

    print(f"\n{colored('Installing VibeMon Plugin for OpenClaw...', 'cyan')}\n")

    # Reuse the shared VibeMon token when --token wasn't passed explicitly
    token = cli_token
    if not token:
        vibemon_config_path = Path.home() / ".vibemon" / "config.json"
        if vibemon_config_path.exists():
            try:
                token = json.loads(vibemon_config_path.read_text()).get("vibemon_token") or None
            except json.JSONDecodeError:
                pass

    plugin_dir = openclaw_home / "extensions" / "vibemon-bridge"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    print("Copying plugin files:")

    # openclaw.plugin.json
    content = source.get_file("openclaw/extensions/openclaw.plugin.json")
    write_file_with_diff(plugin_dir / "openclaw.plugin.json", content, "openclaw.plugin.json")

    # index.mjs
    content = source.get_file("openclaw/extensions/index.mjs")
    write_file_with_diff(plugin_dir / "index.mjs", content, "index.mjs")

    # Handle openclaw.json (merge, don't overwrite)
    print("\nConfiguring openclaw.json:")
    config_file = openclaw_home / "openclaw.json"

    vibemon_plugin_config = {
        "enabled": True,
        "config": {
            "serialEnabled": False,
            "httpEnabled": False,
            "httpUrls": ["http://127.0.0.1:19280"],
            "autoLaunch": False,
            "vibemonUrl": "https://vibemon.io",
            "vibemonToken": token or "",
            "debug": False
        }
    }

    if config_file.exists():
        existing_config = load_json_or_backup(config_file)

        # Ensure plugins.entries structure exists
        if "plugins" not in existing_config:
            existing_config["plugins"] = {}
        if "entries" not in existing_config["plugins"]:
            existing_config["plugins"]["entries"] = {}

        if ensure_plugin_path_registered(existing_config, str(plugin_dir)):
            print(f"  {colored('✓', 'green')} plugin path registered in plugins.load.paths")

        # Merge vibemon-bridge plugin (preserve existing config if present)
        if "vibemon-bridge" in existing_config["plugins"]["entries"]:
            existing_plugin = existing_config["plugins"]["entries"]["vibemon-bridge"]
            # Update token if provided via CLI or found in the shared VibeMon config
            if token and "config" in existing_plugin:
                existing_plugin["config"]["vibemonToken"] = token
            print(f"  {colored('✓', 'green')} vibemon-bridge plugin already configured")
            if token:
                print(f"  {colored('✓', 'green')} token updated")
        else:
            existing_config["plugins"]["entries"]["vibemon-bridge"] = vibemon_plugin_config
            print(f"  {colored('✓', 'green')} vibemon-bridge plugin added")

        config_file.write_text(json.dumps(existing_config, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} openclaw.json updated (existing settings preserved)")
    else:
        new_config = {
            "plugins": {
                "entries": {
                    "vibemon-bridge": vibemon_plugin_config
                }
            }
        }
        ensure_plugin_path_registered(new_config, str(plugin_dir))
        config_file.write_text(json.dumps(new_config, indent=2) + "\n")
        print(f"  {colored('✓', 'green')} openclaw.json created")

    print(f"\n{colored('OpenClaw installation complete!', 'green')}")
    print(f"\n{colored('Next steps:', 'yellow')}")
    print("  1. Restart OpenClaw Gateway: openclaw gateway restart")
    print("  2. Check logs for: [vibemon] Plugin loaded")
    print(f"\n{colored('Config options (in ~/.openclaw/openclaw.json):', 'yellow')}")
    print("  • serialEnabled: true to send status to ESP32 via USB")
    print("  • httpEnabled:   true to send status to Desktop App (localhost)")
    print("  • vibemonUrl:    VibeMon cloud service URL (https://vibemon.io)")
    print("  • vibemonToken:  Your token (8-64 chars, a-z, 0-9, _, -)")

    return True


def valid_token_arg(value: str) -> str:
    """Validate --token format for argparse (8-64 chars: a-z, 0-9, _, -)."""
    if not TOKEN_PATTERN.match(value):
        raise argparse.ArgumentTypeError("invalid token format (expected 8-64 chars: a-z, 0-9, _, -)")
    return value


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="VibeMon Installation Script",
        epilog="""
Examples:
  Interactive mode:
    curl -fsSL https://docs.vibemon.io/install.py | python3

  Non-interactive (for AI agents):
    curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude
    curl -fsSL https://docs.vibemon.io/install.py | python3 - --codex
    curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude --token my_token
    curl -fsSL https://docs.vibemon.io/install.py | python3 - --all --yes
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Platform selection (mutually exclusive for single, but --all overrides)
    parser.add_argument("--claude", action="store_true",
                        help="Install for Claude Code")
    parser.add_argument("--codex", action="store_true",
                        help="Install for Codex CLI")
    parser.add_argument("--kiro", action="store_true",
                        help="Install for Kiro IDE")
    parser.add_argument("--openclaw", action="store_true",
                        help="Install for OpenClaw")
    parser.add_argument("--all", action="store_true",
                        help="Install for all platforms")

    # Configuration options
    parser.add_argument("--token", type=valid_token_arg, metavar="TOKEN",
                        help="VibeMon API token (8-64 chars: a-z, 0-9, _, -)")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Auto-approve all prompts. Does not select a platform by itself; "
                             "combine with --claude/--codex/--kiro/--openclaw/--all, "
                             "otherwise the interactive menu still appears")

    return parser.parse_args()


def run_install(platform_name: str, install_fn, source: FileSource, cli_token: str = None) -> bool:
    """Run a platform installer, isolating exceptions so one platform's failure doesn't abort the rest."""
    try:
        return install_fn(source, cli_token)
    except Exception as e:
        print(f"\n{colored('✗', 'red')} {platform_name} installation failed: {e}")
        return False


def main():
    """Main entry point."""
    global AUTO_APPROVE

    args = parse_args()

    # Determine if non-interactive mode (any platform flag provided)
    non_interactive = args.claude or args.codex or args.kiro or args.openclaw or args.all
    AUTO_APPROVE = args.yes or non_interactive

    # Enable interactive input when running via curl pipe (only if interactive)
    if not non_interactive:
        setup_tty_input()

    # Determine if running locally or online
    # Note: __file__ is in globals(), not dir() (which returns local vars inside a function)
    script_path = Path(__file__).parent.resolve() if "__file__" in globals() else None
    source = FileSource(script_path)

    mode = "online" if source.is_online else "local"

    print(f"\n{colored('╔════════════════════════════════════════╗', 'cyan')}")
    print(f"{colored('║', 'cyan')}     VibeMon Installation Script        {colored('║', 'cyan')}")
    print(f"{colored('╚════════════════════════════════════════╝', 'cyan')}")
    print(f"  Mode: {colored(mode, 'yellow')}")

    results = []

    # Non-interactive mode: install based on flags
    if non_interactive:
        if args.all:
            results.append(run_install("Claude Code", install_claude, source, args.token))
            results.append(run_install("Codex CLI", install_codex, source, args.token))
            results.append(run_install("Kiro IDE", install_kiro, source, args.token))
            results.append(run_install("OpenClaw", install_openclaw, source, args.token))
        else:
            if args.claude:
                results.append(run_install("Claude Code", install_claude, source, args.token))
            if args.codex:
                results.append(run_install("Codex CLI", install_codex, source, args.token))
            if args.kiro:
                results.append(run_install("Kiro IDE", install_kiro, source, args.token))
            if args.openclaw:
                results.append(run_install("OpenClaw", install_openclaw, source, args.token))
    else:
        # Interactive mode: show menu
        print("\nSelect platform to install:")
        print(f"  {colored('1)', 'cyan')} Claude Code")
        print(f"  {colored('2)', 'cyan')} Codex CLI")
        print(f"  {colored('3)', 'cyan')} Kiro IDE")
        print(f"  {colored('4)', 'cyan')} OpenClaw")
        print(f"  {colored('5)', 'cyan')} All")
        print(f"  {colored('q)', 'cyan')} Quit")

        while True:
            try:
                choice = input("\nYour choice [1/2/3/4/5/q]: ").strip().lower()
            except EOFError:
                print("\nInstallation cancelled.")
                sys.exit(0)
            if choice in ("1", "claude"):
                results.append(run_install("Claude Code", install_claude, source))
                break
            elif choice in ("2", "codex"):
                results.append(run_install("Codex CLI", install_codex, source))
                break
            elif choice in ("3", "kiro"):
                results.append(run_install("Kiro IDE", install_kiro, source))
                break
            elif choice in ("4", "openclaw"):
                results.append(run_install("OpenClaw", install_openclaw, source))
                break
            elif choice in ("5", "all"):
                results.append(run_install("Claude Code", install_claude, source))
                results.append(run_install("Codex CLI", install_codex, source))
                results.append(run_install("Kiro IDE", install_kiro, source))
                results.append(run_install("OpenClaw", install_openclaw, source))
                break
            elif choice in ("q", "quit", "exit"):
                print("\nInstallation cancelled.")
                sys.exit(0)
            else:
                print("Please enter 1, 2, 3, 4, 5, or q")

    if any(results):
        print(f"\n{colored('Done!', 'green')} Restart your IDE to apply changes.\n")
    else:
        print(f"\n{colored('!', 'yellow')} No platforms were installed.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
