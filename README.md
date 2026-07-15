# VibeMon Docs

VibeMon is a real-time status monitoring system for AI coding assistants. It displays the current state (thinking, working, done) on ESP32 devices, Desktop App, or cloud service.

## Supported Platforms

| Platform | Character | Description |
|----------|-----------|-------------|
| **Claude Code** | clawd | Anthropic's CLI for Claude |
| **Codex CLI** | vibemon | OpenAI's CLI for Codex |
| **Kiro IDE** | kiro | Amazon's AI coding assistant |
| **OpenClaw** | claw | Open source AI gateway |

## Installation

### VibeMon App (Recommended)

Install the desktop app, then let it configure everything else for you — no separate script needed.

Homebrew (macOS, recommended):

```bash
brew tap opspresso/tap
brew install opspresso/tap/vibemon
```

Or via npm:

```bash
npx vibemon@latest
```

Open the app, go to **Settings > AI Tools**, and click **Install** for Claude Code, Codex CLI, Kiro IDE, or OpenClaw. This installs the hooks and writes `~/.vibemon/config.json` for you. See [vibemon-app](https://github.com/opspresso/vibemon-app) for details.

### Non-interactive Install (AI agents, CI)

For headless setups where a GUI app isn't available:

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude --token my_token
# --codex / --kiro / --openclaw for other tools, --all for every detected tool
```

Interactive prompt version:

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3
```

Or point your AI agent at [`docs/setup.md`](./docs/setup.md) (`https://docs.vibemon.io/setup.md`) and have it follow the instructions directly.

### Local Install

```bash
git clone https://github.com/opspresso/vibemon-docs.git
cd vibemon-docs
python3 docs/install.py
```

## Configuration

After installation, edit `~/.vibemon/config.json` to configure your targets:

```json
{
  "debug": false,
  "cache_path": "~/.vibemon/cache/projects.json",
  "auto_launch": true,
  "http_urls": [],
  "serial_port": null,
  "vibemon_token": "",
  "vibemon_url": "https://vibemon.io"
}
```

| Field | Description | Example |
|-------|-------------|---------|
| `debug` | Enable debug logging | `true` |
| `cache_path` | Cache file path for project metadata | `~/.vibemon/cache/projects.json` |
| `auto_launch` | Auto-launch Desktop App on session start | `true` |
| `http_urls` | HTTP targets (Desktop App, ESP32 WiFi) | `["http://127.0.0.1:19280"]` |
| `serial_port` | ESP32 USB serial port (wildcard supported) | `"/dev/cu.usbmodem*"` |
| `vibemon_url` | VibeMon cloud API URL | `https://vibemon.io` |
| `vibemon_token` | VibeMon API access token (from dashboard) | |

Claude Code's statusline reads a separate `~/.vibemon/statusline.json` for display toggles (e.g. `show_cost`, `show_git`, `show_model`, `show_tokens`) and usage-polling settings (`usage_enabled`, `usage_refresh_seconds`, `token_reset_hours`) — see [statusline.example.json](./docs/vibemon/statusline.example.json) for the full set of defaults. This file is optional; statusline.py falls back to sensible defaults (and to any matching keys still in `config.json`) when it's absent.

The Claude Code installer also places a standalone refresher at `~/.vibemon/usage.py`. It fetches plan usage via `claude -p "/usage"` and writes the shared `~/.vibemon/cache/usage.json`, so the Desktop app can run it (`python3 ~/.vibemon/usage.py --max-age 600`) on startup or on a schedule to keep usage data fresh even when no Claude Code session is active.

The reset-countdown fields the hooks attach (`usage5hResetsIn`/`usageWeekResetsIn`) are only populated when an active Claude Code session refreshes the cache through its statusline (the official `rate_limits` path). The `claude -p "/usage"` path used by `usage.py` yields only display strings, so the usage percentages still update but the reset countdown is omitted.

### Codex Configuration

Codex uses the same `~/.vibemon/config.json` as Claude Code and Kiro. Enable Codex hooks in `~/.codex/config.toml`:

```toml
[features]
hooks = true
```

Then merge [`codex/hooks.json`](./docs/codex/hooks.json) into your existing `~/.codex/hooks.json` (do not overwrite). Codex hooks are experimental and Windows support is currently disabled.

### OpenClaw Configuration

The OpenClaw plugin reads transmission settings (`http_urls`, `serial_port`, `vibemon_url`, `vibemon_token`) from the same `~/.vibemon/config.json` as the other tools. It only needs to be registered and enabled in `~/.openclaw/openclaw.json` — OpenClaw doesn't auto-discover extension directories, so the plugin path must also be registered under `plugins.load.paths` or the manifest/entries config alone won't load it:

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

To override the shared settings for OpenClaw only, add a `config` object to the entry (`projectName`, `character`, `httpEnabled`, `httpUrls`, `serialEnabled`, `vibemonUrl`, `vibemonToken`, `autoLaunch`, `debug`) — plugin config always wins over `~/.vibemon/config.json`.

After installing or updating the plugin, rebuild OpenClaw's persisted plugin registry and restart the gateway (`openclaw plugins registry --refresh && openclaw gateway restart`) — the gateway boots from a registry snapshot and won't pick up the plugin's hooks otherwise. The installer runs the refresh automatically when the `openclaw` CLI is available.

## CLI Commands

The hook script supports these commands:

```bash
# Lock monitor to current project
python3 ~/.claude/hooks/vibemon.py --lock [project_name]

# Unlock monitor
python3 ~/.claude/hooks/vibemon.py --unlock

# Get current status
python3 ~/.claude/hooks/vibemon.py --status

# Get/set lock mode (first-project, on-thinking)
python3 ~/.claude/hooks/vibemon.py --lock-mode [mode]

# Reboot ESP32 device
python3 ~/.claude/hooks/vibemon.py --reboot
```

## Apps

### Desktop App

Electron app with system tray for macOS, Windows, Linux. See [Installation](#installation) above to install.

Token can be configured via the system tray menu.

It shows a single character window with a speech bubble that follows it. The window retargets to whichever project is currently active instead of opening one window per project.

Features: frameless floating window, always on top, system tray integration, snap to screen corners, click to focus terminal (macOS).

### ESP32 Hardware

Dedicated LCD display (172×320, ST7789V2).

**Hardware**: ESP32-C6-LCD-1.47 board, USB-C cable

**Required libraries**: LovyanGFX (lovyan03), ArduinoJson (Benoit Blanchon), WebSockets (Markus Sattler, for WebSocket mode)

**Arduino IDE setup**: add the ESP32 Board Manager URL below, install the ESP32 board and required libraries, select the ESP32C6 Dev Module, then upload.

```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

WiFi configuration (`credentials.h`):

```cpp
#define USE_WIFI
#define WIFI_SSID "YOUR_SSID"
#define WIFI_PASSWORD "YOUR_PASSWORD"
```

Optional WebSocket mode:

```cpp
#define USE_WEBSOCKET
#define WS_HOST "ws.vibemon.io"
#define WS_PORT 443
#define WS_PATH "/"
#define WS_USE_SSL true
#define WS_TOKEN "your-access-token"
```

For SSL, change the Partition Scheme to "Huge APP (3MB No OTA/1MB SPIFFS)".

Testing via serial:

```bash
# macOS
echo '{"state":"working","tool":"Bash","project":"my-project"}' > /dev/cu.usbmodem1101

# Linux (set baud rate first)
stty -F /dev/ttyACM0 115200
echo '{"state":"working","tool":"Bash","project":"my-project"}' > /dev/ttyACM0
```

## API

### WebSocket

```
wss://ws.vibemon.io?token=your-access-token
```

Message types:

```json
// Status update
{
  "type": "status",
  "data": {
    "state": "working",
    "tool": "Bash",
    "project": "my-project",
    "model": "opus",
    "memory": 45,
    "character": "clawd"
  }
}

// Project deleted
{
  "type": "delete",
  "data": { "project": "my-project" }
}
```

### HTTP API

```bash
curl -X POST https://vibemon.io/api/status \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "working",
    "project": "my-project",
    "character": "clawd",
    "tool": "Bash",
    "model": "opus",
    "memory": 45
  }'
```

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | start, idle, thinking, planning, working, packing, notification, done, sleep, alert (required) |
| `project` | string | Project name (required) |
| `character` | string | vibemon (default), clawd, kiro, claw, or daangni (required); daangni is manual selection only (no tool maps to it) |
| `tool` | string | Tool name (Bash, Read, Edit, etc.) (optional) |
| `model` | string | Model name (opus, sonnet, etc.) (optional) |
| `memory` | number | Context window usage 0-100 (optional) |

```bash
# Delete agent status
curl -X DELETE "https://vibemon.io/api/status?project=my-project" \
  -H "Authorization: Bearer your-token"

# Aggregated metrics
curl "https://vibemon.io/api/metrics?granularity=HOUR&range=24h" \
  -H "Authorization: Bearer your-token"
```

Token format: `a-z`, `0-9`, `_`, `-`, 8-64 characters (e.g. `my_token_123`).

## State Mapping

### Claude Code

| Event | State |
|-------|-------|
| SessionStart | start |
| UserPromptSubmit | thinking |
| PreToolUse | working |
| SubagentStart | working |
| PreCompact | packing |
| Notification | notification |
| PermissionRequest | notification |
| SessionEnd | done |
| Stop | done |

**Plan Mode**: When Claude Code is in plan mode, `thinking` and `working` states automatically become `planning`.

### Codex CLI

| Event | State |
|-------|-------|
| SessionStart | start |
| UserPromptSubmit | thinking |
| PreToolUse | working |
| SubagentStart | working |
| PermissionRequest | notification |
| PostToolUse | thinking |
| SubagentStop | thinking |
| PreCompact | packing |
| PostCompact | thinking |
| Stop | done |

Codex hooks are experimental, and Windows support is currently disabled for hooks.

### Kiro IDE

| Event | State |
|-------|-------|
| agentSpawn | start |
| promptSubmit / userPromptSubmit | thinking |
| fileCreated / fileEdited / fileDeleted | working |
| preToolUse | working |
| postToolUse | thinking |
| agentStop / stop | done |

### OpenClaw

| Event | State |
|-------|-------|
| gateway_start | start |
| before_agent_start | thinking |
| before_tool_call | working |
| after_tool_call | thinking |
| message_sent / agent_end | done (3s delay) |
| session_end / gateway_stop | done |

## Related Projects

- [vibemon](https://github.com/opspresso/vibemon) - Cloud dashboard & API ([vibemon.io](https://vibemon.io))
- [vibemon-app](https://github.com/opspresso/vibemon-app) - Desktop App & ESP32 hardware client
- [vibemon-static](https://github.com/opspresso/vibemon-static) - Static assets & embeddable rendering engine ([static.vibemon.io](https://static.vibemon.io))
