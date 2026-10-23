"""Acceptance evidence is explicitly scoped and never writes or emits chat data."""

import importlib.util
import json
import sqlite3
from pathlib import Path

from tomc.request_activity import RequestActivity
from tomc.session_store import SessionStore

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_session_gateway.py"
_SPEC = importlib.util.spec_from_file_location("audit_session_gateway_test", _SCRIPT)
audit_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(audit_script)


def test_missing_store_does_not_create_it_and_default_on_is_not_observed(tmp_path):
    path = tmp_path / "missing" / "memory.sqlite3"
    report = audit_script.audit(path, [("codex", "new-chat")])
    row = report["sessions"][0]
    assert report["store_status"] == "missing" and not path.parent.exists()
    assert not row["observed"] and not row["registered"]
    assert row["switch"]["effective_enabled"] and row["switch"]["session_source"] == "default"
    assert row["last_request"] is None and row["prepared_event_count"] is None


def test_registration_observation_dispatch_and_preparation_are_separate_and_read_only(tmp_path):
    path = tmp_path / "fixture.sqlite3"
    sessions, activity = SessionStore(path), RequestActivity(path)
    sessions.register("codex", "registered-only", title="PRIVATE_TITLE_DO_NOT_EMIT")
    sessions.register("codex", "selected")
    sessions.set_enabled("codex", "selected", False)
    activity.start("prepared", "codex", "selected")
    activity.finish(
        "prepared",
        state="prepared",
        reason="optimized",
        context_input_tokens=15000,
        before_tokens=50000,
        after_tokens=10000,
    )
    activity.sent("prepared")
    activity.usage("prepared", provider_input_tokens=20000, provider_cached_tokens=5000)
    activity.start("off", "codex", "selected")
    activity.finish("off", state="passthrough", reason="session_disabled")
    activity.sent("off")
    activity.start("other-request", "claude", "unselected-chat")
    activity.finish("other-request", state="prepared", context_input_tokens=999999)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE private_chat_content (body TEXT)")
        db.execute("INSERT INTO private_chat_content VALUES ('PRIVATE_BODY_DO_NOT_EMIT')")
    before = {item.name: item.read_bytes() for item in tmp_path.iterdir() if item.is_file()}
    report = audit_script.audit(path, [("codex", "registered-only"), ("codex", "selected")])
    after = {item.name: item.read_bytes() for item in tmp_path.iterdir() if item.is_file()}
    assert before == after
    registered, selected = report["sessions"]
    assert registered["registered"] and not registered["observed"]
    assert selected["observed"] and selected["request_count"] == selected["sent_request_count"] == 2
    assert not selected["switch"]["effective_enabled"]
    assert selected["switch"]["session_source"] == "registered"
    assert selected["last_request"]["request_id"] == "off"
    assert selected["last_request"]["context_input_tokens"] is None
    assert selected["prepared_event_count"] == 1
    assert selected["prepared_events"][0]["context_input_tokens"] == 15000
    encoded = json.dumps(report)
    for forbidden in ("PRIVATE_TITLE", "PRIVATE_BODY", "unselected-chat", "other-request"):
        assert forbidden not in encoded


def test_legacy_schema_marks_prepared_evidence_unavailable_and_does_not_use_json_length(tmp_path):
    path = tmp_path / "old.sqlite3"
    activity = RequestActivity(path)
    activity.start("old", "codex", "legacy")
    activity.finish("old", state="forwarded", before_tokens=2000000, after_tokens=1000000)
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE tomc_context_prepared_events")
        db.execute("ALTER TABLE tomc_request_activity DROP COLUMN context_input_tokens")
    before = path.read_bytes()
    row = audit_script.audit(path, [("codex", "legacy")])["sessions"][0]
    assert row["observed"] and not row["registered"]
    assert row["switch"]["session_source"] == "default"
    assert row["last_request"]["context_input_tokens"] is None
    assert not row["prepared_event_stream_available"] and row["prepared_event_count"] is None
    assert path.read_bytes() == before


def test_manifest_cli_deduplication_limits_and_global_pause(tmp_path, capsys):
    path = tmp_path / "fixture.sqlite3"
    sessions, activity = SessionStore(path), RequestActivity(path)
    sessions.update_settings(enabled=False)
    for index in range(3):
        activity.start(f"r{index}", "claude", "a")
        activity.finish(f"r{index}", state="prepared", context_input_tokens=10000 + index)
    manifest = tmp_path / "selected.json"
    manifest.write_text(
        json.dumps({"sessions": [{"host": "claude", "session_id": "a"}, "b"]}), "utf-8"
    )
    exit_code = audit_script.main(
        [
            "--store",
            str(path),
            "--sessions-json",
            str(manifest),
            "--session-id",
            "b",
            "--event-limit",
            "2",
        ]
    )
    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert len(report["sessions"]) == 2
    row = next(item for item in report["sessions"] if item["host"] == "claude")
    assert row["observed"] and not row["switch"]["effective_enabled"]
    assert row["switch"]["global_source"] == "stored"
    assert row["prepared_event_count"] == 3 and row["prepared_events_truncated"]
    assert [item["context_input_tokens"] for item in row["prepared_events"]] == [10001, 10002]


def test_unreadable_store_is_unknown_and_errors_never_echo_contents(tmp_path, capsys):
    path = tmp_path / "corrupt.sqlite3"
    path.write_text("PRIVATE_BODY_DO_NOT_EMIT", "utf-8")
    assert audit_script.main(["--store", str(path), "--session-id", "chosen"]) == 2
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["store_status"] == "unavailable"
    assert report["sessions"][0]["observed"] is None
    assert report["sessions"][0]["switch"]["effective_enabled"] is None
    assert "PRIVATE_BODY" not in output
    assert audit_script.main(["--store", str(path), "--session-id", "private malformed body"]) == 2
    assert "private malformed body" not in capsys.readouterr().out
