#!/usr/bin/env python3
"""
VibeMon Hook for Codex CLI
Desktop App + ESP32 (USB Serial / HTTP)
Note: Codex provides the active model directly in hook payloads.
Shared transport lives in vibemon_core.py (~/.vibemon/vibemon_core.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Locate vibemon_core.py: repo checkout first (docs/vibemon/), then the
# installed copy (~/.vibemon/).
for _core_dir in (
    Path(__file__).resolve().parent.parent.parent / "vibemon",
    Path.home() / ".vibemon",
):
    if (_core_dir / "vibemon_core.py").is_file():
        sys.path.insert(0, str(_core_dir))
        break

try:
    import vibemon_core as core
except ImportError:
    print(
        "[vibemon] vibemon_core.py not found — re-run the installer: "
        "curl -fsSL https://docs.vibemon.io/install.py | python3",
        file=sys.stderr,
    )
    sys.exit(0)

# Character configuration
CHARACTER = "codex"

# Event to state mapping (immutable)
EVENT_STATE_MAP: dict[str, str] = {
    "SessionStart": "start",
    "UserPromptSubmit": "thinking",
    "PreToolUse": "working",
    "PermissionRequest": "notification",
    "SubagentStart": "working",
    "PreCompact": "packing",
    "Stop": "done",
}


def build_payload(
    state: str, tool: str, project: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Build payload dict for sending to monitor. Codex includes the active
    model in the hook payload; the statusline cache is only a fallback."""
    metadata = core.get_project_metadata(project)
    usage = core.get_codex_usage_metadata()
    model_name = data.get("model", "")

    return {
        "state": state,
        "tool": tool,
        "project": project,
        "model": model_name or metadata.get("model", ""),
        "memory": metadata.get("memory", 0),
        "character": CHARACTER,
        "terminalId": core.get_terminal_id(),
        **usage,
    }


if __name__ == "__main__":
    core.run(
        event_state_map=EVENT_STATE_MAP,
        build_payload=build_payload,
        start_event="SessionStart",
    )
    sys.exit(0)
