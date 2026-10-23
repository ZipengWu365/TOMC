"""Animation receipts: request-ID evidence only, bounded, crash-aware, never raising."""

import json

from tomc.animation_receipts import FILENAME, AnimationReceipts


def test_receipt_lines_hold_ids_stage_counts_and_codes_only(tmp_path):
    receipts = AnimationReceipts(tmp_path)
    assert receipts.record("queued", "req-1", context_input_tokens=15000)
    assert receipts.record("started", "req-1", stage=2, context_input_tokens=15000)
    assert receipts.record("completed", "req-1", stage=2)
    assert receipts.record("skipped", "req-1", stage=2, reason="already_animated")
    # Unknown events, malformed IDs and non-code reasons never reach the file.
    assert not receipts.record("played", "req-1")
    assert not receipts.record("started", "bad id with spaces")
    assert not receipts.record("started", None)
    assert receipts.record(
        "skipped", "req-2", reason="Free text, not a code", stage=9, context_input_tokens=-1
    )
    rows = receipts.read()
    assert [row["event"] for row in rows] == [
        "queued",
        "started",
        "completed",
        "skipped",
        "skipped",
    ]
    assert rows[1]["stage"] == 2 and rows[1]["context_input_tokens"] == 15000
    assert set(rows[-1]) == {"utc", "event", "request_id", "ui"}
    assert all(row["ui"] == receipts.instance and "demo" not in row for row in rows)
    assert receipts.read(["req-2"]) == rows[-1:]


def test_demo_receipts_are_marked(tmp_path):
    receipts = AnimationReceipts(tmp_path, demo=True)
    receipts.record("started", "demo-1", stage=1)
    assert receipts.read()[0]["demo"] is True


def test_rotation_keeps_one_previous_file_and_reads_oldest_first(tmp_path):
    receipts = AnimationReceipts(tmp_path, max_bytes=400)
    for index in range(12):
        receipts.record("queued", f"req-{index}", context_input_tokens=index)
    assert (tmp_path / (FILENAME + ".1")).exists()
    ids = [row["request_id"] for row in receipts.read()]
    assert ids == sorted(ids, key=lambda value: int(value.split("-")[1]))
    assert ids[-1] == "req-11"
    # Each file stays within the limit plus the one line that crossed it.
    for name in (FILENAME, FILENAME + ".1"):
        assert (tmp_path / name).stat().st_size < 400 + 200


def test_restart_marks_unfinished_animation_interrupted_once_and_never_replays(tmp_path):
    first = AnimationReceipts(tmp_path)
    first.record("started", "finished", stage=1)
    first.record("completed", "finished", stage=1)
    first.record("started", "cut-short", stage=3, context_input_tokens=250000)
    with (tmp_path / FILENAME).open("a", encoding="utf-8") as handle:
        handle.write('{"event":"started","request_id":"tor')  # Crash mid-write: no newline.
    second = AnimationReceipts(tmp_path)
    second.instance = "later-instance"
    assert second.recover_interrupted() == 1
    interrupted = [row for row in second.read() if row["event"] == "interrupted"]
    assert len(interrupted) == 1
    assert interrupted[0]["request_id"] == "cut-short" and interrupted[0]["stage"] == 3
    assert interrupted[0]["reason"] == "ui_exited_before_completion"
    assert second.recover_interrupted() == 0
    # The current instance's own in-progress animation is not closed early.
    second.record("started", "current", stage=2)
    assert second.recover_interrupted() == 0


def test_unwritable_location_reports_false_instead_of_raising(tmp_path):
    blocked = tmp_path / "file-not-directory"
    blocked.write_text("x", encoding="utf-8")
    receipts = AnimationReceipts(blocked)
    assert receipts.record("queued", "req") is False
    assert receipts.read() == [] and receipts.recover_interrupted() == 0


def test_receipt_file_is_plain_json_lines(tmp_path):
    receipts = AnimationReceipts(tmp_path)
    receipts.record("started", "req", stage=4, context_input_tokens=1_200_000)
    line = (tmp_path / FILENAME).read_text(encoding="utf-8").strip()
    assert json.loads(line)["stage"] == 4
