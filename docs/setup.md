# VibeMon Setup Guide

You are an AI agent. This guide will help you set up real-time status monitoring with VibeMon.

## What is VibeMon?

VibeMon displays your current state (thinking, working, idle, etc.) to your human operator in real-time. It helps them see what you're doing at a glance.

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

**Install all platforms:**
```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --all
```

The script will:
1. Download and install the necessary hook files
2. Merge hooks into existing config files (preserves your settings)
3. Configure your token (in `~/.vibemon/config.json` or platform config)

**That's it!** After installation, restart your IDE to apply changes.

## Interactive Setup (For Humans)

If you prefer an interactive setup with prompts:

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3
```

## Manual Setup

If automatic installation doesn't work, follow the steps below for your platform.

### Step 1: Create Configuration (Claude Code, Codex & Kiro only)

Create `~/.vibemon/config.json` (not needed for OpenClaw):

```json
{
  "debug": false,
  "cache_path": "~/.vibemon/cache/projects.json",
  "auto_launch": false,
  "http_urls": [],
  "serial_port": null,
  "vibemon_url": "https://vibemon.io",
  "vibemon_token": "YOUR_TOKEN_HERE"
}
```

### For Claude Code (Manual)

Download hook files:
```bash
mkdir -p ~/.claude/hooks
curl -o ~/.claude/hooks/vibemon.py https://docs.vibemon.io/claude/hooks/vibemon.py
curl -o ~/.claude/statusline.py https://docs.vibemon.io/claude/statusline.py
chmod +x ~/.claude/hooks/vibemon.py ~/.claude/statusline.py
```

**IMPORTANT: Do NOT overwrite `~/.claude/settings.json`!**

Merge the following into your existing `~/.claude/settings.json`, preserving all existing settings:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ],
    "PreToolUse": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ],
    "PreCompact": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ],
    "Notification": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/vibemon.py" }] }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/statusline.py"
  }
}
```

**Merge instructions:**
- If `hooks` key exists, append VibeMon hooks to each event array
- If `statusLine` key exists, ask your human before replacing
- Keep all other existing settings unchanged

### For Codex CLI (Manual)

Download hook files:
```bash
mkdir -p ~/.codex/hooks
curl -o ~/.codex/hooks/vibemon.py https://docs.vibemon.io/codex/hooks/vibemon.py
chmod +x ~/.codex/hooks/vibemon.py
```

Enable Codex hooks in `~/.codex/config.toml`:
```toml
[features]
hooks = true
codex_hooks = true
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
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 ~/.codex/hooks/vibemon.py" }
        ]
      }
    ]
  }
}
```

**Notes:**
- Codex hooks are experimental as of 2026-04-23
- Official docs currently state Windows support is disabled for hooks
- Restart your Codex session after updating config files

### For Kiro IDE (Manual)

Download hook files:
```bash
mkdir -p ~/.kiro/hooks ~/.kiro/agents
curl -o ~/.kiro/hooks/vibemon.py https://docs.vibemon.io/kiro/hooks/vibemon.py
curl -o ~/.kiro/hooks/vibemon-prompt-submit.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-prompt-submit.kiro.hook
curl -o ~/.kiro/hooks/vibemon-agent-stop.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-agent-stop.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-created.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-created.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-edited.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-edited.kiro.hook
curl -o ~/.kiro/hooks/vibemon-file-deleted.kiro.hook https://docs.vibemon.io/kiro/hooks/vibemon-file-deleted.kiro.hook
chmod +x ~/.kiro/hooks/vibemon.py
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
    "postToolUse": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "postToolUse"] }
    ],
    "stop": [
      { "command": "python3", "args": ["~/.kiro/hooks/vibemon.py", "agentStop"] }
    ]
  }
}
```

### For OpenClaw (Manual)

Download plugin files:
```bash
mkdir -p ~/.openclaw/extensions/vibemon-bridge
curl -o ~/.openclaw/extensions/vibemon-bridge/openclaw.plugin.json https://docs.vibemon.io/openclaw/extensions/openclaw.plugin.json
curl -o ~/.openclaw/extensions/vibemon-bridge/index.mjs https://docs.vibemon.io/openclaw/extensions/index.mjs
```

**IMPORTANT: Do NOT overwrite `~/.openclaw/openclaw.json`!**

Merge the following into your existing `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "entries": {
      "vibemon-bridge": {
        "enabled": true,
        "config": {
          "vibemonUrl": "https://vibemon.io",
          "vibemonToken": "YOUR_TOKEN_HERE"
        }
      }
    }
  }
}
```

## Token Information

**You can create your own token!** No registration required.

### How to Create a Token

1. **Choose any token you like** that follows this format:
   - Allowed characters: `a-z`, `0-9`, `_` (underscore), `-` (hyphen)
   - Length: 8-64 characters
   - Examples: `my_workspace_01`, `project-alpha-token`, `dev_machine_2026`

2. **Use it immediately** - tokens are auto-registered on first use

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
| Hook not triggering | Check `~/.codex/hooks.json` and ensure `hooks = true` and `codex_hooks = true` in `~/.codex/config.toml` |
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

## More Information

- Dashboard: https://vibemon.io
- Install Script: https://docs.vibemon.io/install.py
- Setup Guide: https://docs.vibemon.io/setup.md
