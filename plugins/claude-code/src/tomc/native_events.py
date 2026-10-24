"""Recognize observed native-compaction events without guessing host state.

These pure adapters consume events forwarded by a trusted host integration.
An MCP server does not receive these events automatically.  ``None`` means
unrecognized or malformed input, never evidence that native compaction is idle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

CompactionState = Literal["active", "completed"]


def codex_compaction_state(event: object) -> CompactionState | None:
    """Read a Codex app-server ``contextCompaction`` item notification.

    Only the documented JSON-RPC notification envelope is accepted.  Usage
    updates, a compact request, legacy notifications, and capability/config
    fields do not establish an observed compaction lifecycle transition.
    Conversation routing and transport authenticity are the caller's job.
    """
    if not isinstance(event, Mapping):
        return None
    method = event.get("method")
    if method not in ("item/started", "item/completed"):
        return None
    params = event.get("params")
    if not isinstance(params, Mapping):
        return None
    item = params.get("item")
    if not isinstance(item, Mapping) or item.get("type") != "contextCompaction":
        return None
    return "active" if method == "item/started" else "completed"


def claude_compaction_state(event: object) -> CompactionState | None:
    """Read the JSON stdin payload forwarded from a Claude Code compact hook.

    ``PreCompact`` means a compact operation is about to run; it may still be
    blocked or fail.  ``PostCompact`` reports a completed compact operation.
    Only documented manual/auto triggers are accepted.  No transcript content
    or session-id shape is inferred, and this function cannot modify messages.
    """
    if not isinstance(event, Mapping):
        return None
    if event.get("trigger") not in ("manual", "auto"):
        return None
    name = event.get("hook_event_name")
    if name == "PreCompact":
        return "active"
    if name == "PostCompact":
        return "completed"
    return None


def extract_state(host: str, event: object) -> CompactionState | None:
    """Dispatch a trusted host event using canonical host names.

    Supported host names are exactly ``codex`` and ``claude``.  Unknown hosts
    or events return ``None``.  This is an event recognizer, not a detector of
    enabled compaction, a session-state tracker, or an idle-state assertion.
    """
    if host == "codex":
        return codex_compaction_state(event)
    if host == "claude":
        return claude_compaction_state(event)
    return None
