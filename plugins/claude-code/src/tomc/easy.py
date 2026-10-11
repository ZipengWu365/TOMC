"""A small handoff API: supply a history and next task, then use the ready prompt."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .compiler import compile_memory
from .input import parse_history
from .ledger import normalize
from .schemas import CompilationResult
from .tokenization import get_counter


@dataclass
class PreparedContext:
    """A ready-to-paste prompt, provider-neutral messages, and optional audit details."""

    prompt: str
    messages: list[dict[str, str]]
    compilation: CompilationResult
    note: str


# Without an explicit budget, keep most of the history. In the Claude Code trial,
# keeping 40-70% matched the full history on every question; 80% leaves margin.
DEFAULT_KEEP_RATIO = 0.8
MIN_DEFAULT_BUDGET = 1024


def default_budget(history_tokens: int) -> int:
    """Return the budget used when none is given: 80% of the history, at least 1,024."""
    return max(MIN_DEFAULT_BUDGET, math.ceil(history_tokens * DEFAULT_KEEP_RATIO))


def prepare_context(history: object, task: str, budget: int | None = None) -> PreparedContext:
    """Keep a fitting history intact; otherwise use existing hybrid routing offline.

    Budget covers memory only, using the lexical counter. Without a budget, about
    80% of the history's estimated tokens are kept (at least 1,024), so short
    histories stay intact. Task and prompt framing add overhead. No reader is
    called and no persistent memory is written.
    """
    if not isinstance(task, str) or not task.strip():
        raise ValueError("Describe what you want the model to do next.")
    if budget is not None and (
        isinstance(budget, bool) or not isinstance(budget, int) or budget < 1
    ):
        raise ValueError("Memory budget must be a positive integer.")
    parsed = parse_history(history)
    text, units = normalize(parsed)
    if not units:
        raise ValueError("Paste a history or load an example first.")
    history_tokens = get_counter("regex").count(text)
    if budget is None:
        budget = default_budget(history_tokens)
    fits = history_tokens <= budget
    result = compile_memory(parsed, task, budget, "raw" if fits else "hybrid")
    if fits:
        note = "This history fits. Kept the complete input; no compression was needed."
    elif result.compiled_memory:
        note = "Prepared relevant memory automatically. Inspect retained sources in the audit details; keep the original history for omitted details."
    else:
        note = "No complete record fits. Increase the memory size before handing this to a model."
    messages = result.reader_messages(task.strip())
    prompt = (
        messages[0]["content"] + "\n\n" + messages[1]["content"] if result.compiled_memory else ""
    )
    return PreparedContext(prompt, messages, result, note)
