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
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
# Characters too common in Chinese questions to identify what the task is about.
_CJK_STOP = set(
    "的了是在吗呢吧啊什么哪个怎多少用有和与及或为被把这那我你他她们现目当前最新终后请问"
)
RECENT_SHARE = 0.12  # budget share kept for the latest lines that name the task's words
CHANGE_SHARE = 0.04  # and for the latest lines announcing a change ("Scratch that, use X.")


def rank_bm25(units: list[Source], query: str, *, later_first: bool = False) -> list[Source]:
    """Rank source lines by Okapi BM25 (k1=1.5, b=0.75), then source order.

    ``later_first`` breaks ties toward the later line, for tasks about a current value.
    Other tasks keep the earlier line, which holds the first link of a chain such as
    "The ledger service is owned by Saffron." / "Saffron reports to Oberon."
    """
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
    sign = -1 if later_first else 1
    return [u for _, u in sorted(scores, key=lambda x: (-x[0], sign * x[1].order))]


def task_terms(query: str) -> tuple[set[str], set[str]]:
    """Stemmed content words of the task, and Chinese character pairs that name its subject."""
    from ..adaptive import content_terms  # adaptive builds on this module

    pairs = set()
    for run in _CJK_RUN.findall(query):
        pairs.update(
            run[i : i + 2] for i in range(len(run) - 1) if not set(run[i : i + 2]) & _CJK_STOP
        )
    return content_terms(query), pairs


def _latest(units, keep, reserve, counter):
    kept, used = [], 0
    for unit in reversed(units):
        if reserve - used < 8:
            break
        if not keep(unit):
            continue
        cost = counter.count(f"[RAW {unit.source_id}] {unit.text}")
        if used + cost <= reserve:
            kept.append(unit)
            used += cost
    return kept


def recent_mentions(
    units: list[Source], query: str, budget: int, counter: TokenCounter
) -> list[Source]:
    """The latest lines naming one of the task's words, within RECENT_SHARE of the budget,
    and the latest lines announcing a change, within CHANGE_SHARE.

    Ranking alone can fill the budget with older lines that repeat the task's words more
    often, dropping the line that changed the value most recently; a correction such as
    "Scratch that, go with Django." may not repeat the task's words at all.
    """
    from ..adaptive import words
    from .latest import announces_change

    terms, pairs = task_terms(query)
    # A stem's first letters appear in each word it came from ("duty" from "duties"):
    # a cheap test before stemming the line.
    prefixes = {t[: max(3, len(t) - 1)] for t in terms}

    def named(unit):
        if any(p in unit.text for p in pairs):
            return True
        lower = unit.text.lower()
        return any(p in lower for p in prefixes) and terms.intersection(words(unit.text))

    kept = []
    if terms or pairs:
        kept = _latest(units, named, int(RECENT_SHARE * budget), counter)
    first = {u.source_id for u in kept}
    changes = [u for u in units if u.source_id not in first]
    return kept + _latest(changes, announces_change, int(CHANGE_SHARE * budget), counter)


def rank_with_recency(
    units: list[Source], query: str, budget: int, counter: TokenCounter, *, later_first=False
) -> list[Source]:
    """BM25 order behind a small reserve for the latest lines that name the task's words."""
    recent = recent_mentions(units, query, budget, counter)
    first = {u.source_id for u in recent}
    ranked = rank_bm25(units, query, later_first=later_first)
    return recent + [u for u in ranked if u.source_id not in first]


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
        """Rank lexically, keeping the latest mentions, and serialize lines in source order."""
        ranked = rank_with_recency(units, query, budget, counter)
        _, kept = pack_rows(raw_rows(ranked), budget, counter)
        evidence = [u for u in units if u.source_id in kept]
        text, kept = pack_rows(raw_rows(evidence), budget, counter)
        return StrategyOutput(
            text,
            "bm25",
            evidence=[u for u in evidence if u.source_id in kept],
            raw_fallback=text,
            warnings=["Lexical BM25; distinct from the frozen BGE hybrid-RAG baseline."],
        )
