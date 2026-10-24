"""Later preparations in one conversation send only what changed."""

import sys
from pathlib import Path

from tomc.incremental import ContextUpdates
from tomc.tokenization import get_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "adaptive"))
from suite import note_cases  # noqa: E402

CASE = note_cases()[0]
NOTES, TASK = CASE.history, CASE.task
COUNTER = get_counter("regex")


def with_channel(channel):
    return NOTES.replace("**amber**", f"**{channel}**", 1)


def test_first_context_is_full_and_an_unchanged_source_is_a_short_note():
    updates = ContextUpdates(4096)
    first = updates.prepare(NOTES, TASK)
    assert first.kind == "full" and "The current release channel is **amber**." in first.text
    again = updates.prepare(NOTES, TASK)
    assert again.kind == "unchanged" and COUNTER.count(again.text) < 40
    assert "has not changed" in again.text


def test_a_changed_decision_and_its_reversion_are_sent_as_changes_with_headings():
    updates = ContextUpdates(4096)
    full = updates.prepare(NOTES, TASK)
    changed = updates.prepare(with_channel("jade"), TASK)
    assert changed.kind == "update"
    assert changed.changed == [
        (
            "# Aurora > ## Current decisions",
            "The current release channel is **amber**.",
            "The current release channel is **jade**.",
        )
    ]
    assert "was: The current release channel is **amber**." in changed.text
    assert "now: The current release channel is **jade**." in changed.text
    assert COUNTER.count(changed.text) < 0.2 * COUNTER.count(full.text)
    assert updates.prepare(with_channel("jade"), TASK).kind == "unchanged"
    reverted = updates.prepare(NOTES, TASK)
    assert reverted.kind == "update"
    assert reverted.changed[0][1:] == (
        "The current release channel is **jade**.",
        "The current release channel is **amber**.",
    )


def test_a_deleted_line_is_reported_as_removed():
    updates = ContextUpdates(4096)
    updates.prepare(NOTES, TASK)
    shown_line = "The current release reviewer is **Priya**."
    gone = updates.prepare(NOTES.replace(shown_line + "\n", "", 1), TASK)
    # Deleting a line shifts the lines after it; either way the reader must learn of it.
    assert gone.kind == "full" or any(old == shown_line for _, old in gone.removed)


def test_a_large_change_sends_a_full_replacement():
    updates = ContextUpdates(4096)
    updates.prepare(NOTES, TASK)
    rewritten = "\n".join("Rewritten: " + line for line in NOTES.splitlines())
    result = updates.prepare(rewritten, TASK)
    assert result.kind == "full" and result.text.startswith("TOMC context (replaces")


def test_compiled_records_that_change_send_a_full_context():
    filler = "\n".join(f"Routine note {i} about maintenance work." for i in range(400))
    updates = ContextUpdates(256)
    first = updates.prepare(filler + "\ntimeout = 30", "What is the current timeout?")
    assert first.kind == "full"
    result = updates.prepare(filler + "\ntimeout = 45", "What is the current timeout?")
    assert result.kind == "full"


def test_a_new_task_adds_only_newly_relevant_lines():
    updates = ContextUpdates(4096)
    updates.prepare(NOTES, "For Aurora, report the current release reviewer.")
    result = updates.prepare(NOTES, TASK)
    assert result.kind in {"update", "full"}
    if result.kind == "update":
        assert not result.changed and not result.removed
        assert any("release blocker" in text for _, text in result.added)
