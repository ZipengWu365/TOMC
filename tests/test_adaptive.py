"""Adaptive selection keeps less than the budget only when the evidence is unambiguous."""

import sys
from pathlib import Path

import pytest

from tomc.adaptive import adaptive_selection, content_terms, stem, words
from tomc.easy import prepare_context
from tomc.ledger import normalize
from tomc.store import MemoryStore
from tomc.tokenization import get_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "adaptive"))
from suite import conversation_cases, note_cases, trap_cases, two_hop_cases  # noqa: E402

COUNTER = get_counter("regex")


@pytest.mark.parametrize(
    ("words", "same"),
    [
        (("owns", "owner", "owned", "owning"), True),
        (("service", "services"), True),
        (("release", "released", "releases"), True),
        (("page", "paging"), True),
        (("blocker", "blocked"), True),
        (("duty", "duties"), True),
        (("data", "date"), False),
    ],
)
def test_light_stemming(words, same):
    assert (len({stem(w) for w in words}) == 1) is same


def test_framing_and_format_words_are_not_content():
    terms = content_terms(
        "Report the current release channel for Aurora. Return only compact JSON with keys."
    )
    assert terms == {"releas", "channel", "aurora"}


def notes(channel="amber"):
    return note_cases()[0].history.replace("**amber**", f"**{channel}**", 1)


def test_clear_evidence_shrinks_and_keeps_every_fact():
    case = note_cases()[0]
    fill = prepare_context(case.history, case.task, 4096, adaptive=False).compilation
    adaptive = prepare_context(case.history, case.task, 4096, adaptive=True).compilation
    assert adaptive.diagnostics["adaptive"] == "shrunk"
    assert adaptive.stats.output_tokens <= 0.3 * fill.stats.output_tokens
    for fact in case.facts:
        assert all(text in adaptive.compiled_memory for text in fact)
    # The budget is still the ceiling, and the margin floor is respected.
    assert 1024 <= adaptive.stats.output_tokens <= 4096


def test_a_changed_and_reverted_decision_is_reported_as_it_now_reads():
    task = note_cases()[0].task
    for channel in ("jade", "amber"):
        memory = prepare_context(
            notes(channel), task, 4096, adaptive=True
        ).compilation.compiled_memory
        assert f"The current release channel is **{channel}**." in memory


def test_words_missing_from_the_history_fall_back_to_filling():
    case = next(c for c in conversation_cases() if c.kind == "paraphrase")
    result = prepare_context(case.history, case.task, 4096, adaptive=True).compilation
    assert result.diagnostics["adaptive"] == "filled"
    assert "absent from the history" in result.diagnostics["adaptive_reason"]
    fill = prepare_context(case.history, case.task, 4096, adaptive=False).compilation
    assert result.compiled_memory == fill.compiled_memory


def test_repeated_claims_with_changing_values_fall_back_to_filling():
    case = trap_cases()[3]
    _, units = normalize(case.history)
    kept, reason = adaptive_selection(units, case.task, 4096, COUNTER)
    assert kept is None and "repeat one claim" in reason


def test_cjk_tasks_fill_for_now():
    _, units = normalize(note_cases()[0].history)
    kept, reason = adaptive_selection(units, "报告 Aurora 当前的发布渠道", 4096, COUNTER)
    assert kept is None and "CJK" in reason


def test_typed_records_are_compiled_exactly_as_before():
    history = "\n".join(
        [f"Filler line {i} about routine maintenance work." for i in range(400)]
        + ["timeout = 30", "timeout = 45", "timeout = 30"]
    )
    task = "What is the current timeout?"
    fill = prepare_context(history, task, 256, adaptive=False).compilation
    adaptive = prepare_context(history, task, 256, adaptive=True).compilation
    fill_rows = [r for r in fill.ledger if r.included]
    assert [(r.key, r.value) for r in fill_rows] == [
        (r.key, r.value) for r in adaptive.ledger if r.included
    ]


def test_no_fact_that_filling_recalls_is_lost_on_the_quick_suite():
    cases = note_cases() + [c for c in conversation_cases() if "conv300" in c.id]
    cases += [c for c in trap_cases() if c.id.startswith("trap300")]
    for case in cases:
        for budget in (4096, None):
            fill = prepare_context(
                case.history, case.task, budget, adaptive=False
            ).compilation.compiled_memory
            adaptive = prepare_context(
                case.history, case.task, budget, adaptive=True
            ).compilation.compiled_memory
            for fact in case.facts:
                if all(text in fill for text in fact):
                    assert all(text in adaptive for text in fact), (case.id, budget, fact)


def test_a_kept_line_brings_the_lines_that_share_its_rare_names():
    case = two_hop_cases()[0]
    owner, manager = case.facts[0]
    assert not content_terms(case.task) & set(words(manager))
    fill = prepare_context(case.history, case.task, 4096, adaptive=False).compilation
    adaptive = prepare_context(case.history, case.task, 4096, adaptive=True).compilation
    assert adaptive.diagnostics["adaptive"] == "shrunk"
    assert "sharing their names" in adaptive.diagnostics["adaptive_reason"]
    assert owner in adaptive.compiled_memory and manager in adaptive.compiled_memory
    assert adaptive.stats.output_tokens <= 0.3 * fill.stats.output_tokens


def transcript(messages):
    return "\n".join(f"{m['role'].title()}: {m['content']}" for m in messages)


def test_notes_are_adaptive_by_default_while_conversations_keep_the_full_budget():
    notes = note_cases()[0]
    default = prepare_context(notes.history, notes.task, 4096).compilation
    assert default.diagnostics["adaptive"] == "shrunk"
    chat = next(c for c in conversation_cases() if c.kind == "direct")
    for history in (chat.history, transcript(chat.history)):
        for budget in (4096, None):
            default = prepare_context(history, chat.task, budget).compilation
            fill = prepare_context(history, chat.task, budget, adaptive=False).compilation
            assert "adaptive" not in default.diagnostics
            assert default.compiled_memory == fill.compiled_memory


def test_notebook_recall_keeps_the_full_budget(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    notes = note_cases()[0]
    store.remember("notes", notes.history)
    recalled = store.recall("notes", notes.task, 4096).compilation
    assert "adaptive" not in recalled.diagnostics
