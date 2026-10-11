"""Adapters around the paper's preserved state/path/count kernels."""

from __future__ import annotations

from dataclasses import replace

from .._vendor import reference as ref
from ..ledger import pack_rows, raw_rows
from ..routing import task_route
from ..schemas import LedgerRecord, Source
from ..tokenization import TokenCounter
from .base import StrategyOutput
from .baselines import rank_bm25


class TOMCStrategy:
    """Compile normalized operations; optionally reserve 58% for source text."""

    def __init__(self, raw_fallback: bool = False) -> None:
        """Choose compiler-only or the reference 0.42 compiled-fraction layout."""
        self.raw = raw_fallback
        self.name = "tomc_raw" if raw_fallback else "tomc"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Execute all normalized operations so snapshot-copy dependencies remain intact."""
        route = task_route(query)
        cfg = ref.TOMCConfig(token_counter=counter.count)
        sources = [ref.SourceUnit(u.source_id, u.order, u.text) for u in units]
        records = ref.compile_records(route, sources, query, cfg)
        warnings = [
            "The default parser recognizes key = value, B copies A, and x -[rel]-> y. "
            "Unstructured prose is preserved as evidence, not inferred state."
        ]
        if route == ref.Route.COUNT:
            warnings.append(
                "Counts use all nonempty content lines and the paper's English lexical tokenizer."
            )
        ledger = [LedgerRecord(r.record_type, r.key, r.value, r.sources) for r in records]
        rows = [(str(i), r.render()) for i, r in enumerate(records)]
        compiled_budget = int(0.42 * budget) if self.raw and rows else budget
        compiled, kept = pack_rows(rows, compiled_budget, counter)
        ledger = [replace(r, included=str(i) in kept) for i, r in enumerate(ledger)]
        support = {s for r in ledger if r.included for s in r.sources}
        raw_text = ""
        raw_ids: set[str] = set()
        if self.raw or not rows:
            # Share unused compiled capacity; exact final counting includes separators.
            remaining = max(0, budget - counter.count(compiled) - (1 if compiled else 0))
            ranked = rank_bm25(units, query)
            _, raw_ids = pack_rows(raw_rows(ranked), remaining, counter)
            raw_text, raw_ids = pack_rows(
                raw_rows([u for u in units if u.source_id in raw_ids]), remaining, counter
            )
        if not rows:
            warnings.append("No supported typed records for this query; using source retrieval.")
        text = "\n".join(s for s in (compiled, raw_text) if s)
        if counter.count(text) > budget:
            # For counters whose boundary merges behave unexpectedly, repack as atomic lines.
            text, _ = pack_rows(
                [(str(i), s) for i, s in enumerate(text.splitlines())], budget, counter
            )
            ledger = [
                replace(r, included=r.included and records[i].render() in text.splitlines())
                for i, r in enumerate(ledger)
            ]
            raw_ids = {
                u.source_id for u in units if f"[RAW {u.source_id}] {u.text}" in text.splitlines()
            }
            raw_text = "\n".join(row for key, row in raw_rows(units) if key in raw_ids)
            support = {s for r in ledger if r.included for s in r.sources}
        return StrategyOutput(
            text,
            route.value,
            ledger,
            [u for u in units if u.source_id in support | raw_ids],
            raw_text,
            warnings,
            {
                "operation_scope": "all_content_lines",
                "count_scope": "all_content_lines",
                "kernel": "paper-reference",
                "rows_before_packing": len(rows),
            },
        )
