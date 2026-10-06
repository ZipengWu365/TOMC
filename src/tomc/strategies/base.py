"""Extensible strategy interface independent of reader providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..schemas import LedgerRecord, Source
from ..tokenization import TokenCounter


@dataclass
class StrategyOutput:
    """Internal result before shared accounting and validation."""

    text: str
    route: str
    ledger: list[LedgerRecord] = field(default_factory=list)
    evidence: list[Source] = field(default_factory=list)
    raw_fallback: str = ""
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, object] = field(default_factory=dict)


class CompressionStrategy(Protocol):
    """Implement compress to register a custom strategy via compile_memory."""

    name: str

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Compile to a measured budget, reporting provenance and limitations."""
        ...
