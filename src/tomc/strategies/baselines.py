"""Offline baselines; BM25 is lexical retrieval, not the paper's BGE hybrid-RAG."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..ledger import pack_rows, raw_rows
from ..schemas import Source
from ..tokenization import TokenCounter
from .base import StrategyOutput

_WORD = re.compile(r"[\u3400-\u9fff]|[a-zA-Z0-9_]+")
_STOP = {"a", "an", "the", "what", "is", "are", "of", "in", "to", "and", "for", "was"}


def rank_bm25(units: list[Source], query: str) -> list[Source]:
    """Rank source lines by Okapi BM25 (k1=1.5, b=0.75), then source order."""
    if not units:
        return []
    terms = set(_WORD.findall(query.lower())) - _STOP
    docs = [Counter(_WORD.findall(u.text.lower())) for u in units]
    df = Counter(t for d in docs for t in d)
    lengths = [sum(d.values()) for d in docs]
    avg = sum(lengths) / len(docs) or 1
    scores = []
    for unit, doc, length in zip(units, docs, lengths):
        score = 0.0
        for term in terms:
            tf = doc[term]
            idf = math.log(1 + (len(units) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / avg))
        scores.append((score, unit))
    return [u for _, u in sorted(scores, key=lambda x: (-x[0], x[1].order))]


class RawStrategy:
    """Full raw reference: deliberately does not apply the memory budget."""

    name = "raw"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Return the complete input and flag budget overflow explicitly."""
        warnings = ["Raw keeps the complete input and can exceed the selected budget."]
        return StrategyOutput(
            history, "raw", evidence=units, raw_fallback=history, warnings=warnings
        )


class TruncationStrategy:
    """Keep a contiguous head or tail span, possibly cutting a source line."""

    def __init__(self, tail: bool = False) -> None:
        """Choose head (default) or tail truncation."""
        self.tail = tail
        self.name = "tail" if tail else "head"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Truncate text; partial lines are not listed as intact evidence."""
        text = counter.truncate(history, budget, tail=self.tail)
        return StrategyOutput(
            text,
            self.name,
            raw_fallback=text,
            warnings=["Truncation can cut a statement or retain an obsolete value."],
        )


class RetrievalStrategy:
    """Line-level BM25 retrieval with complete source rows."""

    name = "rag"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Rank lexically and serialize fitting lines in source order."""
        _, kept = pack_rows(raw_rows(rank_bm25(units, query)), budget, counter)
        evidence = [u for u in units if u.source_id in kept]
        text, kept = pack_rows(raw_rows(evidence), budget, counter)
        return StrategyOutput(
            text,
            "bm25",
            evidence=[u for u in evidence if u.source_id in kept],
            raw_fallback=text,
            warnings=["Lexical BM25; distinct from the frozen BGE hybrid-RAG baseline."],
        )
