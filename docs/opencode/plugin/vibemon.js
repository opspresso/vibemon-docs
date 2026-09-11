/**
 * VibeMon Plugin for opencode
 *
 * opencode has no Claude Code-style hooks, so this plugin bridges opencode
 * events to VibeMon's shared hook pipeline: the adapter
 * (~/.config/opencode/hooks/vibemon.py) feeds vibemon_core.py
 * (~/.vibemon/vibemon_core.py), the same way the Claude Code, Codex, Kiro,
 * and OpenClaw integrations do.
 *
 * Bridge mapping:
 *   session.created                 -> SessionStart       -> start
 *   chat.message                    -> UserPromptSubmit   -> thinking
 *   tool.execute.before             -> PreToolUse         -> working
 *   tool.execute.after              -> PostToolUse        -> thinking
 *   permission.ask                  -> PermissionRequest  -> notification
 *   experimental.session.compacting -> PreCompact         -> packing
 *   session.idle                    -> Stop               -> done
 *   session.deleted                 -> SessionEnd         -> done
 *
 * opencode auto-discovers plugins in ~/.config/opencode/plugins/ at startup,
 * so no config merge is needed. install.py inspects the PYTHON / HOOK_SCRIPT
 * constants below and, on Windows or a custom config home, rewrites them with
 * absolute paths at install time.
 */

import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const OPENCODE_HOME = path.join(os.homedir(), ".config", "opencode");
const HOOK_SCRIPT = path.join(OPENCODE_HOME, "hooks", "vibemon.py");
const PYTHON = "python3";

const sessions = new Map();

function modelName(model) {
  if (!model) return "";
  if (typeof model === "string") return model;
  if (model.modelID) return model.modelID;
  if (model.id) return model.id;
  return "";
}

function sessionDirectory(props) {
  const info = props && props.info;
  if (info && typeof info.directory === "string") return info.directory;
  return "";
}

// Fire-and-forget: write the same payload opencode's other hooks produce and
// let the adapter process it. Never await, so the bridge cannot block opencode.
function sendStatus(eventName, extra = {}) {
  try {
    const payload = {
      hook_event_name: eventName,
      tool_name: extra.tool || "",
      cwd: extra.cwd || "",
      transcript_path: "",
      permission_mode: "default",
      model: extra.model || "",
      memory: 0,
    };
    const child = spawn(PYTHON, [HOOK_SCRIPT], {
      stdio: ["pipe", "ignore", "ignore"],
    });
    child.on("error", () => {});
    child.stdin.on("error", () => {});
    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
    if (child.unref) child.unref();
  } catch {
    // Never let a bridge failure affect opencode.
  }
}

export const vibemon = async ({ directory, worktree }) => {
  const defaultDir =
    (typeof directory === "string" && directory) ||
    (typeof worktree === "string" && worktree) ||
    process.cwd();

  return {
    event: async ({ event }) => {
      try {
        const props = (event && event.properties) || {};
        const sessionID =
          props.sessionID || (props.info && props.info.id) || "";
        const ctx = sessions.get(sessionID) || {};

        switch (event.type) {
          case "session.created": {
            const dir = sessionDirectory(props) || ctx.directory || defaultDir;
            const model = modelName(props.info && props.info.model) || ctx.model;
            sessions.set(sessionID, { directory: dir, model });
            sendStatus("SessionStart", { cwd: dir, model });
            break;
          }
          case "session.idle": {
            sendStatus("Stop", { cwd: ctx.directory, model: ctx.model });
            break;
          }
          case "session.deleted": {
            sendStatus("SessionEnd", { cwd: ctx.directory, model: ctx.model });
            sessions.delete(sessionID);
            break;
          }
        }
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },

    "chat.message": async (input = {}) => {
      try {
        const ctx = sessions.get(input.sessionID) || {};
        const model = modelName(input.model) || ctx.model;
        const dir = ctx.directory || defaultDir;
        sessions.set(input.sessionID, { directory: dir, model });
        sendStatus("UserPromptSubmit", { cwd: dir, model });
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },

    "tool.execute.before": async (input = {}) => {
      try {
        const ctx = sessions.get(input.sessionID) || {};
        sendStatus("PreToolUse", {
          cwd: ctx.directory,
          tool: typeof input.tool === "string" ? input.tool : "",
          model: ctx.model,
        });
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },

    "tool.execute.after": async (input = {}) => {
      try {
        const ctx = sessions.get(input.sessionID) || {};
        sendStatus("PostToolUse", {
          cwd: ctx.directory,
          tool: typeof input.tool === "string" ? input.tool : "",
          model: ctx.model,
        });
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },

    "permission.ask": async (input = {}) => {
      try {
        const ctx = sessions.get(input.sessionID) || {};
        sendStatus("PermissionRequest", {
          cwd: ctx.directory,
          tool: typeof input.tool === "string" ? input.tool : "",
          model: ctx.model,
        });
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },

    "experimental.session.compacting": async (input = {}) => {
      try {
        const ctx = sessions.get(input.sessionID) || {};
        sendStatus("PreCompact", {
          cwd: ctx.directory,
          model: ctx.model,
        });
      } catch {
        // Never let a bridge failure affect opencode.
      }
    },
  };
};