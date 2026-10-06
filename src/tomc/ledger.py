"""Input normalization and whole-record serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from .schemas import Message, Source
from .tokenization import TokenCounter


def normalize(messages: str | Sequence[Message | Mapping[str, object]]) -> tuple[str, list[Source]]:
    """Preserve line text and order; reject unsupported multimodal content explicitly."""
    if isinstance(messages, str):
        items = [Message(messages, "context")]
        original = messages
    else:
        if not isinstance(messages, Sequence):
            raise TypeError("messages must be text or a sequence of messages")
        items = []
        for msg in messages:
            if isinstance(msg, Message):
                items.append(msg)
                continue
            if not isinstance(msg, Mapping):
                raise TypeError("Each message must be a Message or a mapping")
            content = msg.get("content", "")
            if content is None and msg.get("tool_calls"):
                content = ""
            if not isinstance(content, str) or not isinstance(msg.get("role", "user"), str):
                raise TypeError("Only text content and string roles are supported")
            if msg.get("tool_calls"):
                content += "\nTOOL_CALLS=" + json.dumps(
                    msg["tool_calls"], ensure_ascii=False, sort_keys=True
                )
            items.append(Message(content, str(msg.get("role", "user"))))
        original = "\n\n".join(f"[role={m.role}]\n{m.content}" for m in items)
    units = []
    for mi, msg in enumerate(items):
        if not isinstance(msg.content, str) or not isinstance(msg.role, str):
            raise TypeError("Message content and role must be strings")
        for li, line in enumerate(msg.content.splitlines(), 1):
            if line.strip():
                units.append(Source(f"u{len(units)}", len(units), line, mi, li, msg.role))
    return original, units


def pack_rows(
    rows: Sequence[tuple[str, str]], budget: int, counter: TokenCounter
) -> tuple[str, set[str]]:
    """Pack complete rendered rows, including all separators in the measured budget."""
    output: list[str] = []
    keys: set[str] = set()
    used = 0
    for key, row in rows:
        # Cheap additive precheck for large histories, exact check on every accepted row.
        if counter.count(row) > budget - used:
            continue
        candidate = "\n".join((*output, row))
        cost = counter.count(candidate)
        if cost <= budget:
            output.append(row)
            keys.add(key)
            used = cost
    return "\n".join(output), keys


def raw_rows(units: Sequence[Source]) -> list[tuple[str, str]]:
    """Render source-addressed evidence without editing its text."""
    return [(u.source_id, f"[RAW {u.source_id}] {u.text}") for u in units]
