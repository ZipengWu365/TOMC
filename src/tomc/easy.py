"""A small handoff API: supply a history and next task, then use the ready prompt."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .adaptive import AdaptiveRetrievalStrategy, adaptive_selection
from .compiler import compile_memory
from .input import parse_history
from .ledger import normalize
from .routing import hybrid_route
from .schemas import CompilationResult
from .strategies.typed import TOMCStrategy
from .tokenization import get_counter


@dataclass
class PreparedContext:
    """A ready-to-paste prompt, provider-neutral messages, and optional audit details."""

    prompt: str
    messages: list[dict[str, str]]
    compilation: CompilationResult
    note: str


# Without an explicit budget, keep most of the history. In the Claude Code trial,
# keeping 40-70% matched the full history on every question. Short histories keep
# 80%; longer ones keep less, down to 60% at a million estimated tokens.
MIN_DEFAULT_BUDGET = 1024


def default_keep_ratio(history_tokens: int) -> float:
    """0.8 up to 10K estimated tokens, 0.6 from 1M, continuous log-linear between (0.7 at 100K)."""
    if history_tokens <= 10_000:
        return 0.8
    if history_tokens >= 1_000_000:
        return 0.6
    return 0.8 - 0.1 * (math.log10(history_tokens) - 4)


def default_budget(history_tokens: int) -> int:
    """Return the budget used when none is given: 60-80% of the history, at least 1,024.

    The kept amount still grows with the history: a longer one never gets a smaller budget.
    """
    # The epsilon absorbs float noise such as 100,000 * 0.7 = 70,000.00000000001.
    return max(
        MIN_DEFAULT_BUDGET, math.ceil(history_tokens * default_keep_ratio(history_tokens) - 1e-9)
    )


_SPEAKER = re.compile(
    r"^\s*(?:\[role=)?(user|assistant|human|ai|system|tool|claude|codex|chatgpt|gpt)\s*[:\]：]",
    re.I | re.M,
)


def is_conversation(parsed: object) -> bool:
    """A chat history: messages from more than one role, or a transcript with speakers."""
    if isinstance(parsed, str):
        return len({m.lower() for m in _SPEAKER.findall(parsed)}) >= 2
    roles = {getattr(m, "role", None) for m in parsed}
    return len(parsed) > 1 and (len(roles) > 1 or bool(roles & {"assistant", "tool"}))


def _positive(value: object, message: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        raise ValueError(message)


def prepare_context(
    history: object,
    task: str,
    budget: int | None = None,
    *,
    adaptive: bool | None = None,
    max_chars: int | None = None,
) -> PreparedContext:
    """Keep a fitting history intact; otherwise use existing hybrid routing offline.

    Budget covers memory only, using the lexical counter. Without a budget, 80%
    of a short history's estimated tokens are kept, falling to 60% for a history
    of a million or more (at least 1,024), so short histories stay intact. Task
    and prompt framing add overhead. No reader is called and no persistent memory
    is written.

    ``adaptive`` may keep less than the budget when the task's evidence is
    unambiguous. By default it applies to notes and documents; conversation
    histories keep the full-budget selection used for long-context compression.

    ``max_chars`` lowers the budget so the memory fits a client that cuts long tool
    outputs: at most that many characters and a quarter as many estimated tokens,
    so scripts such as Chinese, with more tokens per character, fit as well.
    """
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Describe what you want the model to do next.")
    _positive(budget, "Memory budget must be a positive integer.")
    _positive(max_chars, "The character limit must be a positive integer.")
    parsed = parse_history(history)
    if adaptive is None:
        adaptive = not is_conversation(parsed)
    text, units = normalize(parsed)
    if not units:
        raise ValueError("Paste a history or load an example first.")
    history_tokens = get_counter("regex").count(text)
    if budget is None:
        budget = default_budget(history_tokens)
    requested = budget
    if max_chars is not None:
        per_token = len(text) / max(history_tokens, 1)
        budget = max(1, min(budget, max_chars // 4, int(0.9 * max_chars / per_token)))
    for _ in range(4):
        fits = history_tokens <= budget
        strategy = "raw" if fits else "hybrid"
        route_reason = None
        if adaptive and not fits:
            # Raw evidence may stop below the budget when the task's evidence is unambiguous;
            # typed records compile exactly as before.
            route, route_reason = hybrid_route(text, task)
            strategy = (
                AdaptiveRetrievalStrategy()
                if route == "rag"
                else TOMCStrategy(True, raw_selector=adaptive_selection)
            )
        result = compile_memory(parsed, task, budget, strategy)
        size = len(result.compiled_memory)
        if max_chars is None or size <= max_chars or budget == 1:
            break
        # Rendered records can use more characters per token than the history.
        budget = max(1, int(0.95 * budget * max_chars / size))
    if route_reason and not isinstance(strategy, str):
        result.diagnostics["route_reason"] = route_reason
    if budget < requested:
        result.diagnostics["delivery_limit"] = {
            "max_chars": max_chars,
            "requested_budget": requested,
            "budget": budget,
        }
    if fits:
        note = "This history fits. Kept the complete input; no compression was needed."
    elif result.compiled_memory:
        note = "Prepared relevant memory automatically. Inspect retained sources in the audit details; keep the original history for omitted details."
        if budget < requested:
            note += (
                f" Kept the most relevant part within {max_chars:,} characters so one tool"
                " result can carry it whole; ask a narrower question if something is missing."
            )
    else:
        note = "No complete record fits. Increase the memory size before handing this to a model."
    messages = result.reader_messages(task.strip())
    prompt = (
        messages[0]["content"] + "\n\n" + messages[1]["content"] if result.compiled_memory else ""
    )
    return PreparedContext(prompt, messages, result, note)
