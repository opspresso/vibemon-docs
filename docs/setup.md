# VibeMon Setup Guide

You are an AI agent. This guide will help you set up real-time status monitoring with VibeMon.

## What is VibeMon?

VibeMon displays your current state (thinking, working, idle, etc.) to your human operator in real-time. It helps them see what you're doing at a glance.

> If a human is doing this setup interactively, the recommended path is installing the [VibeMon app](https://github.com/opspresso/vibemon-app) (`brew install opspresso/tap/vibemon`) and using its **Settings > AI Tools** tab instead of the steps below. This guide is for non-interactive, agent-driven setup.

## Quick Setup for AI Agents (Recommended)

Use the non-interactive installer with your platform flag:

**For Claude Code:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude
```

**For Codex CLI:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --codex
```

**For Kiro IDE:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --kiro
```

**For OpenClaw:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --openclaw
```

**With token (recommended):**
```bash
# Create your own token (8-64 chars, a-z, 0-9, _, -)
# Example: username_machine_purpose
curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude --token my_workspace_01
```

**Install for every detected tool:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --all
```

**Skip confirmation prompts (CI/agents):**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --all --yes
```

**On Windows, use PowerShell:**
```powershell
& ([scriptblock]::Create((irm https://docs.vibemon.io/install.ps1))) --claude --token my_workspace_01
& ([scriptblock]::Create((irm https://docs.vibemon.io/install.ps1))) --all --yes
```
The same flags apply. `curl ... | python3` is not usable there: Windows has no
`python3` on `PATH`, and Windows PowerShell 5.1 re-encodes piped text with the
console code page, corrupting the script before Python parses it. `install.ps1`
locates a Python (`py -3`, then `python`), downloads `install.py`, checks it
against the published `manifest.json`, and runs it with these arguments.

On Windows the installer covers **Claude Code** and **Codex CLI** plus the
shared `~/.vibemon` scripts; `--kiro` and `--openclaw` are reported as skipped.
`-y`/`--yes` auto-approves every prompt, including replacing a status line you already configured. It doesn't select a platform by itself, so combine it with a platform flag or `--all`.

A platform flag on its own (`--claude`) runs without prompting but is **not** the same as `--yes`: VibeMon's own scripts are upgraded in place, while anything you own — most importantly an existing `statusLine` — is left alone and reported as unchanged. Pass `--yes` when you do want it replaced.

The script will:
1. Download and install the necessary hook files, verifying each against the published `manifest.json` before writing it
2. Merge hooks into existing config files (preserves your settings) — every config it touches is copied to `<name>.bak` first and rewritten atomically
3. Configure your token (in `~/.vibemon/config.json`, created `0600`)

**Exit status:** `0` only when every selected platform succeeded. A tool that isn't installed is reported as *skipped* and doesn't fail the run; a platform that genuinely failed exits `1`, even if others succeeded.

**That's it!** After installation, restart your IDE to apply changes.

## Uninstall

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --uninstall --claude
curl -fsSL https://docs.vibemon.io/install.py | python3 - --uninstall --all
```

```powershell
# Windows
& ([scriptblock]::Create((irm https://docs.vibemon.io/install.ps1))) --uninstall --claude
```

This removes VibeMon's hook registrations, its status line, and the scripts it installed. Hooks you added yourself are preserved, and a `statusLine` you've since pointed at your own script is left in place. Your settings in `~/.vibemon/config.json` and `~/.vibemon/statusline.json` are kept so a reinstall doesn't lose your token — delete `~/.vibemon` yourself to remove those too.

`~/.codex/config.toml` is left untouched: its `[features] hooks` and `[tui] status_line` entries are generic Codex settings, not VibeMon's.

## Interactive Setup (For Humans)

If you prefer an interactive setup with prompts:

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3
```

```powershell
# Windows
irm https://docs.vibemon.io/install.ps1 | iex
```

## Manual Setup

If automatic installation doesn't work, follow the steps below for your platform.

> **On Windows**, the `curl -o` download blocks below need `curl.exe -o` in
> PowerShell — the bare `curl` name is an alias for `Invoke-WebRequest`, which
> takes `-OutFile` rather than `-o`. Skip the `chmod +x` lines; Windows has no
> executable bit. The `settings.json` / `hooks.json` snippets need the Windows
> forms shown in each section.

### Step 1: Create Configuration (all tools)

Create `~/.vibemon/config.json` (shared by Claude Code, Codex, Kiro, and the OpenClaw plugin):

```json
{
  "debug": false,
  "cache_path": "~/.vibemon/cache/projects.json",
  "auto_launch": true,
  "http_urls": [],
  "serial_port": null,
  "vibemon_token": "YOUR_TOKEN_HERE",
  "vibemon_url": "https://vibemon.io"
}
```

### For Claude Code (Manual)

Download hook files:
```bash
mkdir -p ~/.claude/hooks ~/.vibemon
curl -o ~/.claude/hooks/vibemon.py https://docs.vibemon.io/claude/hooks/vibemon.py
curl -o ~/.claude/statusline.py https://docs.vibemon.io/claude/statusline.py
curl -o ~/.vibemon/usage.py https://docs.vibemon.io/vibemon/usage.py
curl -o ~/.vibemon/usage_cache.py https://docs.vibemon.io/vibemon/usage_cache.py
curl -o ~/.vibemon/vibemon_core.py https://docs.vibemon.io/vibemon/vibemon_core.py
chmod +x ~/.claude/hooks/vibemon.py ~/.claude/statusline.py ~/.vibemon/usage.py
```

**IMPORTANT: Do NOT overwrite `~/.claude/settings.json`!**

Merge the following into your existing `~/.claude/settings.json`, preserving all existing settings:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/hooks/vibemon.py",
            "async": true,
            "timeout": 10
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py"
  }
}
```

**On Windows, use exec form instead.** PowerShell — which Claude Code uses for
shell-form commands when Git Bash isn't installed — does not expand `~` in
argument position, and there is no `python3` on `PATH`. Adding `args` makes
Claude Code spawn the interpreter directly, with no shell in between:

```json
{
  "type": "command",
  "command": "C:/Users/you/AppData/Local/Programs/Python/Python313/python.exe",
  "args": ["C:/Users/you/.claude/hooks/vibemon.py"],
  "async": true,
  "timeout": 10
}
```

`statusLine` has no exec form, so it stays a single command string. Use forward
slashes (Git Bash eats unquoted backslashes) and quote only what contains a
space:

```json
{
  "statusLine": {
    "type": "command",
    "command": "C:/Users/you/AppData/Local/Programs/Python/Python313/python.exe C:/Users/you/.claude/statusline.py"
  }
}
```

If the interpreter path itself contains a space and Git Bash is **not**
installed, PowerShell needs the call operator in front of the quoted command:
`& "C:/Program Files/Python313/python.exe" "C:/Users/you/.claude/statusline.py"`.
Drop the leading `&` when Git Bash is installed — bash reads it as
backgrounding the command. `install.ps1` picks the right form for you.

**Merge instructions:**
- If `hooks` key exists, append VibeMon hooks to each event array
- If `statusLine` key exists, ask your human before replacing
- Keep all other existing settings unchanged

Optionally, create `~/.vibemon/statusline.json` to customize the statusline's display toggles (`show_*`) and fallback `token_reset_hours` setting — see [statusline.example.json](https://docs.vibemon.io/vibemon/statusline.example.json). This file is separate from `~/.vibemon/config.json` and not required; statusline.py uses sensible defaults when it's absent.

### For Codex CLI (Manual)

Download hook files:
```bash
mkdir -p ~/.codex/hooks ~/.vibemon
curl -o ~/.codex/hooks/vibemon.py https://docs.vibemon.io/codex/hooks/vibemon.py
curl -o ~/.vibemon/usage.py https://docs.vibemon.io/vibemon/usage.py
curl -o ~/.vibemon/vibemon_core.py https://docs.vibemon.io/vibemon/vibemon_core.py
curl -o ~/.vibemon/usage_cache.py https://docs.vibemon.io/vibemon/usage_cache.py
chmod +x ~/.codex/hooks/vibemon.py ~/.vibemon/usage.py
```

Enable Codex hooks in `~/.codex/config.toml`:
```toml
[features]
hooks = true
```

**IMPORTANT: Do NOT overwrite `~/.codex/hooks.json`!**

Merge the following into your existing `~/.codex/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: session start"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: subagent start"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: compacting"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: prompt submit"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: tool start"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: approval needed"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/vibemon.py",
            "statusMessage": "VibeMon: turn done"
          }
        ]
      }
    ]
  }
}
```

**On Windows**, add a `commandWindows` override beside each `command` — Codex's
hooks.json takes a Windows-only command string, so the POSIX one stays intact:

```json
{
  "type": "command",
  "command": "python3 ~/.codex/hooks/vibemon.py",
  "commandWindows": "C:/Users/you/AppData/Local/Programs/Python/Python313/python.exe C:/Users/you/.codex/hooks/vibemon.py",
  "statusMessage": "VibeMon: turn done"
}
```

**Notes:**
- Codex hooks are experimental
- Official docs currently state Windows support is disabled for hooks, so the
  `commandWindows` override stays dormant until Codex enables them
- Restart your Codex session after updating config files

### For Kiro IDE (Manual)

> Not supported on Windows yet — `install.py` skips Kiro there.

Download hook files:
```bash
mkdir -p ~/.kiro/hooks ~/.kiro/agents ~/.vibemon
curl -o ~/.kiro/hooks/vibemon.py https://docs.vibemon.io/kiro/hooks/vibemon.py
curl -o ~/.vibemon/vibemon_core.py https://docs.vibemon.io/vibemon/vibemon_core.py
curl -o ~/.vibemon/usage_cache.py https://docs.vibemon.io/vibemon/usage_cache.py
curl -o ~/.vibemon/usage.py https://docs.vibemon.io/vibemon/usage.py
curl -o ~/.kiro/hooks/vibemon-prompt-submit.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-prompt-submit.kiro.hook
curl -o ~/.kiro/hooks/vibemon-agent-stop.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-agent-stop.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-created.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-created.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-edited.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-edited.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-deleted.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-deleted.kiro.hook
chmod +x ~/.kiro/hooks/vibemon.py ~/.vibemon/usage.py
```

**IMPORTANT: Do NOT overwrite `~/.kiro/agents/default.json`!**

Merge the following hooks into your existing `~/.kiro/agents/default.json`:

```json
{
  "hooks": {
    "agentSpawn": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "agentSpawn"] }
    ],
    "userPromptSubmit": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "promptSubmit"] }
    ],
    "preToolUse": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "preToolUse"] }
    ],
    "stop": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "agentStop"] }
    ]
  }
}
```

Activate the default agent so the merged hooks take effect:
```bash
kiro-cli --agent default
# or inside a running session: /agent swap default
```

### For OpenClaw (Manual)

> Not supported on Windows yet — `install.py` skips OpenClaw there.

Download plugin files:
```bash
mkdir -p ~/.openclaw/extensions/vibemon-bridge ~/.vibemon
curl -o ~/.openclaw/extensions/vibemon-bridge/openclaw.plugin.json https://docs.vibemon.io/openclaw/extensions/openclaw.plugin.json
curl -o ~/.openclaw/extensions/vibemon-bridge/index.mjs https://docs.vibemon.io/openclaw/extensions/index.mjs
curl -o ~/.vibemon/vibemon_core.py https://docs.vibemon.io/vibemon/vibemon_core.py
curl -o ~/.vibemon/usage_cache.py https://docs.vibemon.io/vibemon/usage_cache.py
curl -o ~/.vibemon/usage.py https://docs.vibemon.io/vibemon/usage.py
chmod +x ~/.vibemon/usage.py
```

**IMPORTANT: Do NOT overwrite `~/.openclaw/openclaw.json`!**

Merge the following into your existing `~/.openclaw/openclaw.json`. OpenClaw doesn't auto-discover extension directories, so the plugin path must also be registered under `plugins.load.paths` or the manifest/entries config alone won't load it:

```json
{
  "plugins": {
    "load": {
      "paths": ["~/.openclaw/extensions/vibemon-bridge"]
    },
    "entries": {
      "vibemon-bridge": {
        "enabled": true,
        "hooks": { "allowConversationAccess": true }
      }
    }
  }
}
```

`hooks.allowConversationAccess` is required for OpenClaw to let a non-bundled plugin register conversation hooks (`before_agent_run`, `agent_end`); without it OpenClaw silently blocks them.

Transmission settings (`http_urls`, `serial_port`, `vibemon_url`, `vibemon_token`) are read from the shared `~/.vibemon/config.json` (Step 1). To override them for OpenClaw only, add a `config` object to the entry with `httpEnabled`, `httpUrls`, `serialEnabled`, `vibemonUrl`, or `vibemonToken` — plugin config always wins over the shared file.

Finally, rebuild OpenClaw's persisted plugin registry and restart the gateway — the gateway boots from a registry snapshot, and skipping the refresh leaves the plugin loaded but with no hooks running:

```bash
openclaw plugins registry --refresh
openclaw gateway restart
```

## Token Information

**You can create your own token!** No registration required.

### How to Create a Token

1. **Choose any token you like** that follows this format:
   - Allowed characters: `a-z`, `0-9`, `_` (underscore), `-` (hyphen)
   - Length: 8-64 characters
   - Examples: `my_workspace_01`, `project-alpha-token`, `dev_machine_2026`

2. **Use it immediately** - tokens are auto-registered on the first status report (`POST /api/status`); read-only calls and dashboard connections do not register a token

3. **Share with your human** - give them the same token to view your dashboard

### Recommended Token Pattern

For AI agents, use a descriptive token like:
```
{username}_{machine}_{purpose}
```

Examples:
- `bruce_macbook_dev`
- `team_alpha_staging`
- `john_workstation_main`

### View Dashboard

After installation, your human can view your status at:
```
https://vibemon.io/?token=YOUR_TOKEN
```

## Verify Installation

After setup, your status should appear on the dashboard when you start working.

Dashboard URL: `https://vibemon.io/?token=YOUR_TOKEN`

## Supported Tools

| Tool | Character | Setup Method |
|------|-----------|--------------|
| Claude Code | clawd | install.py or manual |
| Codex CLI | codex | install.py or manual |
| Kiro | kiro | install.py or manual |
| OpenClaw | claw | install.py or manual |

## Troubleshooting

### All Platforms
| Issue | Solution |
|-------|----------|
| Status not updating | Check `vibemon_token` in config file |
| Network error | Verify `vibemon_url` is `https://vibemon.io` |

### Claude Code
| Issue | Solution |
|-------|----------|
| Hook not triggering | Verify `~/.claude/settings.json` syntax |
| Permission denied | Run `chmod +x ~/.claude/hooks/vibemon.py` |

### Codex CLI
| Issue | Solution |
|-------|----------|
| Hook not triggering | Check `~/.codex/hooks.json` and ensure `hooks = true` in `~/.codex/config.toml` |
| No updates after install | Restart the Codex session after editing hook files |

### Kiro IDE
| Issue | Solution |
|-------|----------|
| Hook not triggering | Check `~/.kiro/agents/default.json` hooks |
| Permission denied | Run `chmod +x ~/.kiro/hooks/vibemon.py` |

### OpenClaw
| Issue | Solution |
|-------|----------|
| Plugin not loading | Check `~/.openclaw/openclaw.json` plugins.entries |
| Plugin disabled | Set `"enabled": true` in vibemon-bridge config |

### Windows
| Issue | Solution |
|-------|----------|
| `python` opens the Microsoft Store | Turn off the `python.exe` / `python3.exe` App execution aliases in Settings > Apps > Advanced app settings, or install Python from python.org |
| Hooks stopped after a Python upgrade | The hook `command` holds an absolute interpreter path. Re-run the installer |
| Status line blank or silently failing | Check whether Git Bash is installed. Without it Claude Code uses PowerShell, which needs `& ` before a *quoted* command; with it, that `&` must be removed |
| Backslashes disappear from a path | Git Bash treats them as escapes. Write hook and status line paths with forward slashes |
| ESP32 not updating | USB serial is POSIX-only; `serial_port` is ignored on Windows. Use the Desktop app or the ESP32's WiFi/HTTP target instead |
| Kiro / OpenClaw reported as skipped | Expected — neither is supported on Windows yet |

## More Information

- Dashboard: https://vibemon.io
- Install Script: https://docs.vibemon.io/install.py
- Windows Install Script: https://docs.vibemon.io/install.ps1
- Setup Guide: https://docs.vibemon.io/setup.md
