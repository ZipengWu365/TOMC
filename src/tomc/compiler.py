"""Small public API shared by the CLI, demo, and reader integrations."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence

from .ledger import normalize
from .routing import hybrid_route
from .schemas import CompilationResult, CompilationStats, Message, StrategyName
from .strategies import (
    CompressionStrategy,
    RawStrategy,
    RetrievalStrategy,
    TOMC2Strategy,
    TOMCStrategy,
    TruncationStrategy,
)
from .strategies.latest import parent_id, split_long_units
from .tokenization import TokenCounter, get_counter

STRATEGIES = ("raw", "head", "tail", "rag", "tomc", "tomc2", "tomc_raw", "hybrid")
# Line-selecting methods; their pieces of an over-long line keep IDs such as u12.1.
SPLITTING = ("rag", "tomc", "tomc_raw")


def compile_memory(
    messages: str | Sequence[Message | Mapping[str, object]],
    query: str,
    token_budget: int = 4096,
    strategy: StrategyName | CompressionStrategy = "tomc_raw",
    *,
    tokenizer: str | TokenCounter = "regex",
    input_price_per_million: float | None = None,
    deterministic: bool = True,
) -> CompilationResult:
    """Compile history offline. All built-ins are deterministic except measured latency.

    Raw deliberately ignores token_budget as an uncompressed comparison. Other
    strategies must satisfy the selected counter's budget. Prices are supplied by
    the caller, cover memory input only, and are not measured API charges.
    """
    start = time.perf_counter()
    if isinstance(token_budget, bool) or not isinstance(token_budget, int) or token_budget < 0:
        raise ValueError("token_budget must be a nonnegative integer")
    if not isinstance(query, str):
        raise TypeError("query must be text")
    if input_price_per_million is not None and (
        not math.isfinite(input_price_per_million) or input_price_per_million < 0
    ):
        raise ValueError("input_price_per_million must be finite and nonnegative")
    history, units = normalize(messages)
    counter = get_counter(tokenizer)
    requested = strategy if isinstance(strategy, str) else strategy.name
    route_reason = "Explicit strategy selection."
    actual = requested
    if actual == "hybrid":
        actual, route_reason = hybrid_route(history, query)
    if isinstance(strategy, str):
        builtins: dict[str, CompressionStrategy] = {
            "raw": RawStrategy(),
            "head": TruncationStrategy(),
            "tail": TruncationStrategy(True),
            "rag": RetrievalStrategy(),
            "tomc": TOMCStrategy(),
            "tomc2": TOMC2Strategy(),
            "tomc_raw": TOMCStrategy(True),
        }
        if actual not in builtins:
            raise ValueError(f"Unknown strategy {actual!r}; choose {', '.join(STRATEGIES)}")
        implementation = builtins[actual]
    else:
        implementation = strategy
    lines = units
    if implementation.name in SPLITTING:
        units = split_long_units(units, token_budget, counter)
    output = implementation.compress(history, units, query, token_budget, counter)
    if units is not lines:
        # Evidence stays whole input lines; the memory cites the pieces it kept.
        cited = {parent_id(u.source_id) for u in output.evidence}
        output.evidence = [u for u in lines if u.source_id in cited]
    before, after = counter.count(history), counter.count(output.text)
    if actual != "raw" and after > token_budget:
        raise RuntimeError("Strategy violated the selected tokenizer budget")
    warnings = list(output.warnings)
    if counter.estimated:
        warnings.append("Token counts are lexical estimates, not provider-billed tokens.")
    if units and not output.text:
        warnings.append("No complete record fits this budget. Increase it or choose truncation.")
    if after > before:
        warnings.append("Structured metadata increased this short input's size.")
    price = input_price_per_million
    stats = CompilationStats(
        before,
        after,
        token_budget,
        after / before if before else 0.0,
        before / after if after else None,
        before - after,
        round((time.perf_counter() - start) * 1000, 3),
        counter.name,
        counter.estimated,
        after <= token_budget,
        before * price / 1e6 if price is not None else None,
        after * price / 1e6 if price is not None else None,
        price,
    )
    split = {parent_id(u.source_id) for u in units if "." in u.source_id}
    diagnostics = {
        **output.diagnostics,
        **({"split_lines": len(split)} if split else {}),
        "selected_strategy": actual,
        "route_reason": route_reason,
        "deterministic_requested": deterministic,
        "source_units": len(lines),
        "evidence_scope": "audit metadata outside the reader token budget",
    }
    return CompilationResult(
        output.text,
        output.ledger,
        output.evidence,
        output.raw_fallback,
        stats,
        requested,
        output.route,
        warnings,
        diagnostics,
    )
