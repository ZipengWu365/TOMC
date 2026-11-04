"""Adapters around the paper's preserved state/path/count kernels."""

from __future__ import annotations

from dataclasses import replace

from .._vendor import reference as ref
from ..ledger import pack_rows, raw_rows
from ..routing import task_route
from ..schemas import LedgerRecord, Source
from ..tokenization import TokenCounter
from .base import StrategyOutput
from .baselines import rank_with_recency
from .latest import UNCAPPED, StateLines, identity, refine_records


class TOMCStrategy:
    """Compile normalized operations; optionally reserve 58% for source text."""

    def __init__(self, raw_fallback: bool = False, raw_selector=None) -> None:
        """Choose compiler-only or the reference 0.42 compiled-fraction layout.

        ``raw_selector(units, query, budget, counter)`` may return the source IDs to keep
        as raw evidence, or None to fill the remaining budget as before. The method name
        stays the same; diagnostics report whether the selector shrank the evidence.
        """
        self.raw = raw_fallback
        self.raw_selector = raw_selector
        self.name = "tomc_raw" if raw_fallback else "tomc"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Execute all normalized operations so snapshot-copy dependencies remain intact."""
        route = task_route(query)
        cfg = ref.TOMCConfig(token_counter=counter.count)
        sources = [ref.SourceUnit(u.source_id, u.order, u.text) for u in units]
        # The kernel compiles every key; the adapter then keeps the task's keys first.
        uncapped = replace(cfg, max_state_rows=UNCAPPED, max_count_rows=UNCAPPED)
        parser = StateLines(units)
        records = ref.compile_records(route, sources, query, uncapped, parser=parser)
        refined = refine_records(route, records, units, query, parser, cfg)
        records = [r for r, _ in refined]
        warnings = [
            "The default parser recognizes key = value and key: value lines (also in lists, "
            "after a label such as Update:, or several separated by ;), B copies A, and "
            "x -[rel]-> y, outside code blocks. "
            "Unstructured prose is preserved as evidence, not inferred state."
        ]
        if route == ref.Route.COUNT:
            warnings.append(
                "Counts use all nonempty content lines and the paper's English lexical tokenizer; "
                "Chinese terms named in the task are counted as exact substrings."
            )
        by_id = {u.source_id: u for u in units}
        ledger = [
            LedgerRecord(
                r.record_type,
                r.key,
                r.value,
                (*r.sources, *later),
                basis="later_line_may_change" if later else "normalized_operation",
            )
            for r, later in refined
        ]
        # A doubtful value travels with the later line that put it in doubt.
        rows = [
            (str(i), "\n".join([r.render(), *(f"[RAW {s}] {by_id[s].text}" for s in later)]))
            for i, (r, later) in enumerate(refined)
        ]
        compiled_budget = int(0.42 * budget) if self.raw and rows else budget
        compiled, kept = pack_rows(rows, compiled_budget, counter)
        if route == ref.Route.STATE:
            # Packing follows the task's priority; the reader sees the kernel's order by key.
            listed = sorted(range(len(rows)), key=lambda i: identity(records[i].key))
            compiled = "\n".join(rows[i][1] for i in listed if str(i) in kept)
        ledger = [replace(r, included=str(i) in kept) for i, r in enumerate(ledger)]
        shown = {s for i, (_, later) in enumerate(refined) if str(i) in kept for s in later}
        if shown:
            warnings.append(
                "A later line may have changed some values; they are marked STATE? (or PATH?) "
                "and followed by that line. Check it before relying on the value."
            )
        support = {s for r in ledger if r.included for s in r.sources}
        raw_text = ""
        raw_ids: set[str] = set()
        selection = {}
        if self.raw or not rows:
            # Share unused compiled capacity; exact final counting includes separators.
            remaining = max(0, budget - counter.count(compiled) - (1 if compiled else 0))
            chosen = None
            if self.raw_selector is not None:
                chosen, reason = self.raw_selector(units, query, remaining, counter)
                selection = {
                    "adaptive": "filled" if chosen is None else "shrunk",
                    "adaptive_reason": reason,
                }
            if chosen is None:
                # Current-value and count tasks prefer the later line on a tie.
                later_first = route in (ref.Route.STATE, ref.Route.COUNT)
                ranked = rank_with_recency(
                    units, query, remaining, counter, later_first=later_first
                )
                _, raw_ids = pack_rows(
                    raw_rows([u for u in ranked if u.source_id not in shown]), remaining, counter
                )
            else:
                raw_ids = chosen - shown
                warnings.append("Adaptive lexical selection kept less than the budget allows.")
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
            lines = text.splitlines()
            ledger = [
                replace(r, included=r.included and records[i].render() in lines)
                for i, r in enumerate(ledger)
            ]
            raw_ids = {
                u.source_id for u in units if f"[RAW {u.source_id}] {u.text}" in text.splitlines()
            }
            raw_text = "\n".join(row for key, row in raw_rows(units) if key in raw_ids)
            support = {s for r in ledger if r.included for s in r.sources}
        if route == ref.Route.STATE:
            ledger.sort(key=lambda r: identity(r.key))
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
                **selection,
            },
        )
