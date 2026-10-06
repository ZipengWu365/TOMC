"""Explicit offline budgeting; estimates are never presented as provider usage."""

from __future__ import annotations

import re
from typing import Protocol

_TOKEN = re.compile(r"[\u3400-\u9fff]|[^\W_]+(?:_[^\W_]+)*|[^\w\s]|_", re.UNICODE)


class TokenCounter(Protocol):
    """A counter used consistently for original text, packing, and final validation."""

    name: str
    estimated: bool

    def count(self, text: str) -> int:
        """Count tokens in text."""
        ...

    def truncate(self, text: str, budget: int, *, tail: bool = False) -> str:
        """Return a span whose count is at most budget."""
        ...


class RegexCounter:
    """Zero-dependency lexical estimate with individual CJK characters."""

    name = "regex-v1 (estimate)"
    estimated = True

    def count(self, text: str) -> int:
        """Count words, punctuation, and CJK characters."""
        return sum(1 for _ in _TOKEN.finditer(text))

    def truncate(self, text: str, budget: int, *, tail: bool = False) -> str:
        """Preserve original whitespace inside a head or tail span."""
        if budget <= 0:
            return ""
        matches = list(_TOKEN.finditer(text))
        if len(matches) <= budget:
            return text
        return text[matches[-budget].start() :] if tail else text[: matches[budget - 1].end()]


class TiktokenCounter:
    """Explicit opt-in BPE counter; initial encoding setup may download vocabulary."""

    estimated = False

    def __init__(self, encoding: str = "cl100k_base") -> None:
        """Load an installed tiktoken encoding, failing clearly if unavailable."""
        try:
            import tiktoken
        except ImportError:
            raise ImportError("Install tomc-memory[tokenizers] or use tokenizer='regex'.") from None
        self.encoding = tiktoken.get_encoding(encoding)
        self.name = f"tiktoken:{encoding}"

    def count(self, text: str) -> int:
        """Count ordinary text without interpreting special token strings."""
        return len(self.encoding.encode(text, disallowed_special=()))

    def truncate(self, text: str, budget: int, *, tail: bool = False) -> str:
        """Keep valid UTF-8 and recheck the budget after decoding."""
        tokens = self.encoding.encode(text, disallowed_special=())
        if budget <= 0:
            return ""
        kept = tokens[-budget:] if tail else tokens[:budget]
        result = self.encoding.decode_bytes(kept).decode("utf-8", errors="ignore")
        while self.count(result) > budget:
            result = result[1:] if tail else result[:-1]
        return result


def get_counter(name: str | TokenCounter = "regex") -> TokenCounter:
    """Resolve a counter. Default use never attempts a network request."""
    if not isinstance(name, str):
        return name
    if name == "regex":
        return RegexCounter()
    if name.startswith("tiktoken:"):
        return TiktokenCounter(name.split(":", 1)[1])
    raise ValueError("Unknown tokenizer; use regex or tiktoken:cl100k_base.")
