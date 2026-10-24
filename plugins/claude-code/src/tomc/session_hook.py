"""Metadata-only command hook and TOMC-specific per-session processing guard.

The host invokes this with JSON on stdin. It never opens transcript_path,
copies prompt text into the database, calls a model, or infers request identity
from the global 'active' display selection. UI focus is not observable here.
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

# Also supports execution by an absolute path from a source/plugin installation.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tomc.session_store import SessionStore  # noqa: E402

HOSTS = ("codex", "claude_code")
EVENTS = ("SessionStart", "UserPromptSubmit", "Stop", "PreToolUse")
TOOL_PATTERN = (
    r"^mcp__(?:tomc|tomc-memory|tomc_memory|plugin_tomc-memory_tomc)__"
    r"(?:prepare_context|recall_memory)$"
)
_TOOL_RE = re.compile(TOOL_PATTERN)
MAX_INPUT_BYTES = 8 * 1024 * 1024


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    return value


def _deny(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def handle_event(payload, *, host, store):
    """Register explicit host metadata; return only a targeted hook decision."""
    if host not in HOSTS or not isinstance(payload, dict):
        raise ValueError("unsupported hook input")
    event = payload.get("hook_event_name")
    if event not in EVENTS:
        return {}
    target = (
        event == "PreToolUse"
        and isinstance(payload.get("tool_name"), str)
        and (_TOOL_RE.fullmatch(payload["tool_name"]) is not None)
    )
    if event == "PreToolUse" and not target:
        return {}
    session_id = _text(payload.get("session_id"), 256)
    if session_id and not re.fullmatch(r"[A-Za-z0-9_.:-]+", session_id):
        session_id = None
    if session_id is None:
        if target:
            return _deny("TOMC 未取得本次调用的会话身份，无法核验会话开关。")
        return {}
    # Skip subagents: Codex hook session_id may be the parent session ID.
    if payload.get("agent_id") or payload.get("agent_type"):
        return _deny("TOMC 尚未核验子代理会话身份。") if target else {}
    registry_host = "claude" if host == "claude_code" else host
    registry = SessionStore(store)
    registry.register(
        registry_host,
        session_id,
        title=_text(payload.get("session_title"), 500),
        project=_text(payload.get("cwd"), 4096),
        event=event,
        activate=event in ("SessionStart", "UserPromptSubmit"),
    )
    if not target and event == "SessionStart" and host == "codex":
        identity = json.dumps({"tomc_host": host, "tomc_session_id": session_id})
        return {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "TOMC session identity: " + identity + ". If you independently need to call "
                    "TOMC prepare_context or recall_memory, include these two identity arguments. "
                    "This is identity metadata, not a request to call TOMC or recompact this chat."
                ),
            }
        }
    if not target:
        return {}
    if not registry.effective_enabled(registry_host, session_id):
        return _deny("本会话 TOMC 已关闭，未执行上下文准备或读取。")
    if host == "codex":
        # Codex requires permissionDecision=allow with updatedInput. Do not
        # implicitly change the host's tool-approval flow just for attribution.
        return {}
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return _deny("TOMC 工具参数格式无法核验。")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {
                **tool_input,
                "tomc_host": registry_host,
                "tomc_session_id": session_id,
            },
        }
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Register TOMC host metadata from hook stdin.")
    parser.add_argument("--host", required=True, choices=HOSTS)
    parser.add_argument("--event", choices=EVENTS)
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc" / "memory.sqlite3")
    parser.add_argument("--tomc-session-hook", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    payload = None
    try:
        raw = (
            sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            if hasattr(sys.stdin, "buffer")
            else (sys.stdin.read(MAX_INPUT_BYTES + 1))
        )
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("oversized hook input")
        payload = json.loads(raw)
        if args.event and (
            not isinstance(payload, dict) or payload.get("hook_event_name") != args.event
        ):
            raise ValueError("mismatched hook event")
        output = handle_event(payload, host=args.host, store=args.store)
    except (OSError, ValueError, TypeError, sqlite3.Error):
        # Never echo exception text, prompt content, or a path supplied by stdin.
        if args.event == "PreToolUse" or (
            isinstance(payload, dict)
            and payload.get("hook_event_name") == "PreToolUse"
            and (
                isinstance(payload.get("tool_name"), str)
                and _TOOL_RE.fullmatch(payload["tool_name"])
            )
        ):
            output = _deny("TOMC 会话开关核验失败，未执行本次准备。")
        else:
            print("TOMC session metadata could not be registered.", file=sys.stderr)
            return 1
    if output:
        print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
