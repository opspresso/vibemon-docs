# VibeMon Docs

VibeMon is a real-time status monitoring system for AI coding assistants. It displays the current state (thinking, working, done) on ESP32 devices, Desktop App, or cloud service.

## Supported Platforms

| Platform | Character | Description |
|----------|-----------|-------------|
| **Claude Code** | clawd | Anthropic's CLI for Claude |
| **Codex CLI** | codex | OpenAI's CLI for Codex |
| **Kiro IDE** | kiro | Amazon's AI coding assistant |
| **OpenClaw** | claw | Open source AI gateway |

## Installation

### Online Install (Recommended)

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3
```

Non-interactive (for AI agents):

```bash
curl -fsSL https://docs.vibemon.io/install.py | python3 - --claude --token my_token
# --codex / --kiro / --openclaw for other tools, --all for every detected tool
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
  "auto_launch": false,
  "http_urls": [],
  "serial_port": null,
  "vibemon_url": "https://vibemon.io",
  "vibemon_token": ""
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

Claude Code's statusline also reads additional `show_*` display toggles (e.g. `show_cost`, `show_git`, `show_model`, `show_tokens`) and `usage_enabled`/`usage_refresh_seconds` — see [config.example.json](./docs/config.example.json) for the full set of defaults.

### Codex Configuration

Codex uses the same `~/.vibemon/config.json` as Claude Code and Kiro. Enable Codex hooks in `~/.codex/config.toml`:

```toml
[features]
hooks = true
codex_hooks = true
```

Then merge [`codex/hooks.json`](./docs/codex/hooks.json) into your existing `~/.codex/hooks.json` (do not overwrite). Codex hooks are experimental and Windows support is currently disabled.

### OpenClaw Configuration

OpenClaw uses a plugin configuration at `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "entries": {
      "vibemon-bridge": {
        "enabled": true,
        "config": {
          "projectName": "OpenClaw",
          "character": "claw",
          "autoLaunch": false,
          "serialEnabled": false,
          "httpEnabled": false,
          "httpUrls": ["http://127.0.0.1:19280"],
          "vibemonUrl": "https://vibemon.io",
          "vibemonToken": "",
          "debug": false
        }
      }
    }
  }
}
```

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

Electron app with system tray for macOS, Windows, Linux.

Homebrew (macOS, recommended):

```bash
brew tap opspresso/tap
brew install opspresso/tap/vibemon
```

Or via npm:

```bash
npx vibemon@latest
# or install globally
npm install -g vibemon
vibemon
```

Token can be configured via the system tray menu.

| Window Mode | Description |
|-------------|-------------|
| `multi` | One window per project (max 5) - Default |
| `single` | One window with project lock support |

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
| `character` | string | clawd, codex, kiro, or claw (required) |
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
| preCompact | packing |
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
