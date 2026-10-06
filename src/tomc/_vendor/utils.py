from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator, Sequence

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def approx_token_count(text: str) -> int:
    """Fast provider-independent token estimate used only for budgeting/auditing.

    API-reported token usage remains the source of truth for cost reporting.
    """

    if not text:
        return 0
    return max(1, len(_TOKEN_RE.findall(text)))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_json_hash(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        f.flush()


def truncate_words(text: str, budget_tokens: int) -> str:
    if approx_token_count(text) <= budget_tokens:
        return text
    words = text.split()
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if approx_token_count(" ".join(words[:mid])) <= budget_tokens:
            lo = mid
        else:
            hi = mid - 1
    return " ".join(words[: max(1, lo)])


def pack_blocks(blocks: Sequence[str], budget_tokens: int) -> str:
    """Pack ordered blocks while preserving earlier, higher-priority blocks."""

    if budget_tokens <= 0:
        return ""
    out: list[str] = []
    used = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        count = approx_token_count(block)
        if used + count <= budget_tokens:
            out.append(block)
            used += count
            continue
        remaining = budget_tokens - used
        if remaining > 8:
            clipped = truncate_words(block, remaining)
            if clipped:
                out.append(clipped)
        break
    return "\n\n".join(out)


def normalize_messages(messages: Sequence[dict[str, Any]]) -> str:
    """Convert chat/tool messages into an auditable text transcript."""

    lines: list[str] = []
    for idx, msg in enumerate(messages):
        role = str(msg.get("role", "unknown"))
        content = msg.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False)
        extra = msg.get("extra") or {}
        action_text = ""
        if isinstance(extra, dict) and extra.get("actions"):
            action_text = "\nACTIONS=" + json.dumps(extra["actions"], ensure_ascii=False)
        lines.append(f"[message={idx} role={role}]\n{content}{action_text}")
    return "\n\n".join(lines)
