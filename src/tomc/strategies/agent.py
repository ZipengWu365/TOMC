"""Historical TOMC2 software-trace adapter with audited whole-record serialization."""

from __future__ import annotations

import re
from dataclasses import replace

from .._vendor.tomc2 import TOMC2AgentCompiler, TraceUnit
from ..ledger import pack_rows, raw_rows
from ..schemas import LedgerRecord, Source
from ..tokenization import TokenCounter
from .base import StrategyOutput


class TOMC2Strategy:
    """Preserve goals, repository entities, tests, attempts, facts, verifiers, and recency."""

    name = "tomc2"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Adapt the frozen compiler's section builders without executing suggested commands."""
        if not units:
            return StrategyOutput("", "agent_ledger", warnings=["No source history to compile."])
        core = TOMC2AgentCompiler()
        trace = [TraceUnit(u.order, u.text) for u in units]
        blocks = [
            ("GOAL", core._goals(trace, query)),
            ("REPOSITORY", core._repo_map(trace)),
            ("TEST_ERROR", core._test_error_ledger(trace)),
            ("ATTEMPT", core._attempt_ledger(trace)),
            ("FACT", core._facts(trace, query)),
            ("VERIFIER", core._verifiers(trace)),
            ("NEXT_ACTION", core._next_action(trace, query)),
        ]
        ledger: list[LedgerRecord] = []
        rows: list[tuple[str, str]] = []
        for kind, block in blocks:
            subsection = ""
            for line in block.splitlines()[1:]:
                if not line.startswith("- "):
                    subsection = line.rstrip(":")
                    continue
                if "no_" in line and "_detected" in line:
                    continue
                value = line[2:]
                source_ids = tuple(dict.fromkeys(re.findall(r"(?:source[=:]\s*)(u\d+)\b", value)))
                if kind == "VERIFIER":
                    source_ids = tuple(u.source_id for u in units if value in u.text)
                key = f"{kind.lower()}_{len(ledger)}"
                basis = (
                    "heuristic_prior"
                    if kind == "NEXT_ACTION" or (kind == "VERIFIER" and not source_ids)
                    else "heuristic_observation"
                )
                if kind == "GOAL" and value.startswith("explicit_query:"):
                    basis = "user_query"
                ledger.append(LedgerRecord(kind, key, value, source_ids, basis=basis))
                label = f"{kind}/{subsection}" if subsection else kind
                rows.append((key, f"[{label}] {value}"))
        compiled, kept = pack_rows(rows, int(budget * 0.70), counter)
        ledger = [replace(row, included=row.key in kept) for row in ledger]
        remainder = max(0, budget - counter.count(compiled) - (1 if compiled else 0))
        _, raw_ids = pack_rows(raw_rows(list(reversed(units))), remainder, counter)
        raw_text, raw_ids = pack_rows(
            raw_rows([u for u in units if u.source_id in raw_ids]), remainder, counter
        )
        text = "\n".join(s for s in (compiled, raw_text) if s)
        support = {s for row in ledger if row.included for s in row.sources} | raw_ids
        return StrategyOutput(
            text,
            "agent_ledger",
            ledger,
            [u for u in units if u.source_id in support],
            raw_text,
            [
                "TOMC2 uses heuristic trace extraction. A 'passed' or 'resolved' row "
                "is a source observation, not an independently verified fact. "
                "Verifier commands are displayed only; never executed."
            ],
            {
                "kernel": "research-tomc2-section-builders",
                "serialization": "whole-record-v1",
                "rows_before_packing": len(rows),
            },
        )
