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
