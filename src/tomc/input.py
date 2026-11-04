"""Text-only imports for paste, JSON messages and JSONL conversation files."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

from .schemas import Message

# A single line that opens a message envelope: an error is clearer than a silent text import.
_ENVELOPE = re.compile(r'^\s*(?:\{\s*"(?:messages|role|content)"|\[\s*\{\s*"(?:role|content)")')


def parse_history(value: object) -> str | list[Message]:
    """Accept common text-message envelopes; reject unsupported blocks without dropping them.

    There is no length cap: the compiler scales linearly (about 2.6 s per million
    estimated tokens on CPU) and the paper's experiments compile 10M-token histories.
    """
    if isinstance(value, str):
        value = value.removeprefix("\ufeff")
        if not re.match(r'^\s*(?:\[\s*(?:\{|\])|\{\s*["}])', value):
            return value
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            lines = [line for line in value.splitlines() if line.strip()]
            if len(lines) == 1:
                if _ENVELOPE.match(value):
                    raise ValueError(
                        f"This looks like JSON messages but is not valid JSON ({error.msg} at "
                        f"line {error.lineno}, column {error.colno}). Fix the JSON, or paste "
                        "the conversation as plain text."
                    ) from None
                return value
            # JSONL: each nonempty line is a complete message object. Anything else, such
            # as notes that begin with a JSON line, is plain text.
            try:
                items = [json.loads(line) for line in lines]
            except json.JSONDecodeError:
                return value
            if not all(isinstance(i, Mapping) and ("content" in i or "role" in i) for i in items):
                return value
            value = items
    if isinstance(value, Mapping):
        if "messages" in value:
            value = value["messages"]
        elif "content" in value:
            value = [value]
        else:
            raise ValueError("JSON needs a messages list or text content field.")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("Paste text, a messages JSON object, a message list, or JSONL.")
    messages = []
    for item in value:
        if isinstance(item, Message):
            message = item
        else:
            if not isinstance(item, Mapping) or "content" not in item:
                raise ValueError("Each message needs a text content field.")
            content = item["content"]
            if isinstance(content, list):
                blocks = []
                for block in content:
                    if (
                        not isinstance(block, Mapping)
                        or block.get("type") not in ("text", "input_text", "output_text")
                        or not isinstance(block.get("text"), str)
                    ):
                        raise ValueError(
                            "Only text blocks are supported; export images/tools as text first."
                        )
                    blocks.append(block["text"])
                content = "\n".join(blocks)
            if content is None and item.get("tool_calls"):
                content = ""
            if not isinstance(content, str):
                raise ValueError("Only text content is supported.")
            if item.get("tool_calls"):
                content += "\nTOOL_CALLS=" + json.dumps(
                    item["tool_calls"], ensure_ascii=False, sort_keys=True
                )
            message = Message(content, item.get("role", "user"))
        if not isinstance(message.content, str) or not isinstance(message.role, str):
            raise ValueError("Message content and role must be text.")
        messages.append(message)
    return messages
