"""Shared result contract for native request adapters. Never includes credentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .easy import PreparedContext


@dataclass
class AdaptedRequest:
    payload: dict[str, Any]
    transformed: bool
    reason: str
    before_tokens: int
    after_tokens: int
    prepared: PreparedContext | None = None
    task: str | None = None
    counter: str = "regex-request-json-v1 (estimate)"
    prefix_count: int | None = None
    replacement_count: int | None = None
    anchor_count: int | None = None
    # Old-history size behind a replayed compilation, when no new one ran.
    context_input_tokens: int | None = None

    @property
    def context_tokens(self) -> int | None:
        """Estimated old-history tokens this request's memory was prepared from."""
        if self.prepared is not None:
            return self.prepared.compilation.stats.input_tokens
        return self.context_input_tokens
