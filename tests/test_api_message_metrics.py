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


def test_default_api_demo_compiles_current_state_and_measures_whole_message_text():
    history, task = quick_example(API_EXAMPLE)
    default_size = next(iter(SIZES))
    assert default_size == "Small request" and SIZES[default_size] == 64
    prompt, status, _, audit, messages = prepare_view(history, task, default_size)

    assert audit["diagnostics"]["selected_strategy"] == "tomc_raw"
    assert "[STATE] framework = FastAPI" in prompt
    assert "[STATE] backup_framework = Flask" in prompt
    assert audit["stats"]["input_tokens"] == 93
    assert audit["stats"]["output_tokens"] == 45

    raw = compile_memory(history, task, 64, "raw")
    before, after = message_content_counts(raw.reader_messages(task), messages)
    assert (before, after) == (138, 90)
    # The task and instructions contribute to both inputs; memory-only savings
    # have a different percentage denominator from the request-text comparison.
    assert before > raw.stats.input_tokens
    assert after > audit["stats"]["output_tokens"]
    counter = get_counter("regex")
    assert after == sum(counter.count(m["content"]) for m in messages)
    assert "138 → 90" in status and "+48 tokens (+34.8%)" in status
    assert "Memory only:" in status and "93 → 45" in status
    assert "not measured API usage or a bill" in status


@pytest.mark.parametrize(
    "history",
    [
        "The migration tests still need to run.",
        '{"role":"user","content":"The migration tests still need to run."}',
    ],
)
def test_fitting_plain_text_and_json_histories_report_zero_input_reduction(history):
    _, status, _, audit, messages = prepare_view(history, "What remains?", "Balanced")
    assert audit["diagnostics"]["selected_strategy"] == "raw"
    assert "0 tokens (0.0%)" in status
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
    assert f"{before - after:,} tokens (-" in display
    assert "Input increased." in display
    assert "not defined" in input_reduction(0, 0)


def test_empty_memory_is_unusable_and_has_no_input_reduction_pitch():
    paragraph = "migration notes " * 150
    prompt, status, _, audit, _ = prepare_view(paragraph, "What remains?", "Small request")
    assert not prompt and not audit["compiled_memory"]
    assert "No complete record fits" in status and "Unusable request" in status
    assert "Estimated input reduction:" not in status
