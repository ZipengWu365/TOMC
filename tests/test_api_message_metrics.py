"""Honest offline input comparisons for the first-use API demo."""

import pytest

pytest.importorskip("gradio")

from demo.easy import (  # noqa: E402
    API_EXAMPLE,
    SIZES,
    input_reduction,
    message_content_counts,
    prepare_view,
    quick_example,
)
from tomc import compile_memory  # noqa: E402
from tomc.tokenization import get_counter  # noqa: E402


def test_api_demo_compiles_current_state_and_measures_whole_message_text():
    history, task = quick_example(API_EXAMPLE)
    assert next(iter(SIZES)) == "Small request" and SIZES["Small request"] == 200
    # This short history fits every size, so it is sent whole: nothing to save.
    _, status, _, audit, _, _ = prepare_view(history, task, "Small request")
    assert audit["diagnostics"]["selected_strategy"] == "raw"
    assert "No change (0%)" in status

    # Under a tighter budget the update records are compiled and the request shrinks.
    raw = compile_memory(history, task, 64, "raw")
    structured = compile_memory(history, task, 64, "tomc_raw")
    assert "[STATE] framework = FastAPI" in structured.compiled_memory
    assert "[STATE] backup_framework = Flask" in structured.compiled_memory
    before, after = message_content_counts(
        raw.reader_messages(task), structured.reader_messages(task)
    )
    assert (before, after) == (138, 90)
    # The task and instructions contribute to both inputs; memory-only savings
    # have a different percentage denominator from the request-text comparison.
    assert before > raw.stats.input_tokens
    counter = get_counter("regex")
    assert after == sum(counter.count(m["content"]) for m in structured.reader_messages(task))
    display = input_reduction(before, after)
    assert display == "48 fewer tokens (\u221235%)"
    assert "+" not in display


def test_default_sample_matches_tomc_try_and_measures_whole_message_text():
    history, task = quick_example("120-day project chat", "en")
    prompt, status, _, audit, messages, strip = prepare_view(history, task, next(iter(SIZES)))
    stats = audit["stats"]
    assert stats["token_budget"] == 200
    assert stats["input_tokens"] > 6000 and stats["output_tokens"] <= 200
    raw = compile_memory(history, task, 200, "raw")
    before, after = message_content_counts(raw.reader_messages(task), messages)
    assert f"{before - after:,} fewer tokens (\u2212" in status
    assert f"Whole request {before:,} \u2192 {after:,} tokens" in status
    assert "Memory only:" in status and "not measured API usage or a bill" in status
    assert "framework = Litestar" in prompt and "db = postgres" in prompt
    assert "framework = Litestar" in strip


@pytest.mark.parametrize(
    "history",
    [
        "The migration tests still need to run.",
        '{"role":"user","content":"The migration tests still need to run."}',
    ],
)
def test_fitting_plain_text_and_json_histories_report_zero_input_reduction(history):
    _, status, _, audit, messages, _ = prepare_view(history, "What remains?", "Balanced")
    assert audit["diagnostics"]["selected_strategy"] == "raw"
    assert "No change (0%)" in status
    assert "no compression was needed" in status
    assert messages[1]["content"].endswith("TASK\nWhat remains?")


def test_signed_comparison_reports_structure_that_increases_a_short_input():
    history, task = "framework = Flask", "What is the current framework?"
    raw = compile_memory(history, task, 64, "raw")
    structured = compile_memory(history, task, 64, "tomc_raw")
    before, after = message_content_counts(
        raw.reader_messages(task), structured.reader_messages(task)
    )
    assert after > before
    display = input_reduction(before, after)
    assert display.startswith(f"Context grew by {after - before:,} tokens (+")
    assert input_reduction(before, after, "zh").startswith(
        f"上下文增加了 {after - before:,} token（+"
    )
    assert "not defined" in input_reduction(0, 0)


def test_empty_memory_is_unusable_and_has_no_input_reduction_pitch():
    paragraph = "migration notes " * 150
    prompt, status, _, audit, _, strip = prepare_view(paragraph, "What remains?", "Small request")
    assert not prompt and not audit["compiled_memory"]
    assert "No complete record fits" in status and "Unusable request" in status
    assert "fewer tokens" not in status and not strip
