import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from tomc.request_activity import RequestActivity
from tomc.usage import UsageStore


def test_read_only_empty_store_and_unknown_usage(tmp_path):
    path = tmp_path / "missing" / "requests.sqlite3"
    activity = RequestActivity(path)
    assert activity.active() is None and activity.last() is None
    summary = activity.summary()
    assert summary["total_requests"] == 0
    assert summary["provider_input_tokens"] is None
    assert summary["provider_cached_tokens"] is None
    assert not path.exists() and not path.parent.exists()


def test_cpu_end_dispatch_and_provider_usage_are_three_separate_observations(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    started = activity.start("r1", "codex", "s1")
    assert activity.active()["request_id"] == "r1" and not started["sent"]
    assert started["context_input_tokens"] is None
    activity.finish("r1", state="prepared", reason="optimized", before_tokens=1000, after_tokens=600,
                    context_input_tokens=700)
    assert activity.active() is None
    assert not activity.last()["sent"]
    assert activity.last()["provider_input_tokens"] is None
    assert activity.last()["context_input_tokens"] == 700
    with pytest.raises(ValueError, match="dispatch"):
        activity.usage("r1", provider_input_tokens=800)
    activity.sent("r1")
    assert activity.last()["state"] == "forwarded"
    activity.usage("r1", provider_input_tokens=800, provider_cached_tokens=200)
    assert activity.active() is None
    assert activity.last()["estimated_reduced_tokens"] == 400
    assert activity.last()["provider_input_tokens"] == 800
    assert activity.last()["context_input_tokens"] == 700
    summary = activity.summary()
    assert summary["provider_input_tokens"] == 800 and summary["provider_cached_tokens"] == 200
    assert "actual_saved_tokens" not in summary
    assert UsageStore(activity.path).summary()["preparations"] == 0


def test_passthrough_and_failure_do_not_claim_compression_or_usage(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("disabled", "claude", "s1")
    activity.finish("disabled", state="passthrough", reason="session_disabled",
                    before_tokens=100, after_tokens=100)
    activity.sent("disabled")
    assert activity.last()["state"] == "passthrough" and activity.last()["sent"]
    activity.start("failed", "codex", "s2")
    activity.finish("failed", state="failed", reason="upstream_connection_error")
    assert activity.active() is None
    summary = activity.summary()
    assert summary["counts"]["failed"] == summary["counts"]["passthrough"] == 1
    assert summary["provider_usage_requests"] == 0 and summary["provider_input_tokens"] is None


def test_request_identity_and_concurrent_active_requests(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("a", "codex", "session-a")
    activity.start("b", "claude", "session-b")
    assert activity.active()["active_count"] == 2
    activity.finish("b", state="passthrough", reason="short_input")
    assert activity.active()["request_id"] == "a"
    activity.finish("a", state="failed", reason="compilation_failed")
    activity.start("a", "codex", "session-a")
    assert activity.active() is None
    with pytest.raises(ValueError, match="different identity"):
        activity.start("a", "codex", "other-session")
    with pytest.raises(ValueError):
        activity.finish("a", state="prepared", reason="optimized")


def test_late_usage_does_not_reorder_new_request_or_report_old_work_as_busy(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("old", "codex", "s")
    activity.finish("old", state="forwarded", reason="optimized", before_tokens=200, after_tokens=100)
    activity.start("new", "codex", "s")
    activity.usage("old", provider_input_tokens=150)
    assert activity.last()["request_id"] == "new"
    old_stamp = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with sqlite3.connect(activity.path) as db:
        db.execute("UPDATE tomc_request_activity SET updated_utc=? WHERE request_id='new'", (old_stamp,))
    assert activity.active() is None
    assert activity.last()["state"] == "preparing"  # No invented completion after a crash.


@pytest.mark.parametrize("value", [-1, True, 1.5, "10"])
def test_reject_invalid_provider_usage(tmp_path, value):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("r", "codex")
    activity.finish("r", state="forwarded", reason="optimized")
    with pytest.raises(ValueError):
        activity.usage("r", provider_input_tokens=value)


def test_reason_codes_cannot_store_exception_content(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("r", "codex")
    with pytest.raises(ValueError, match="short code"):
        activity.finish("r", state="failed", reason="Bearer secret-token failed in https://example.test")


def test_usage_migration_request_id_animation_link_and_idempotency(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE context_usage_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "recorded_at TEXT, counter TEXT, input_tokens INTEGER, memory_tokens INTEGER, usable INTEGER)")
        db.execute("INSERT INTO context_usage_events VALUES (1,'2026-01-01','legacy',100,50,1)")
    store = UsageStore(path)
    assert store.recent_events()[0]["request_id"] is None
    report = {"counter": "lexical", "usable": True, "input_tokens": 1000,
              "memory_tokens": 600, "reduced_tokens": 400, "request_id": "unique-request"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: UsageStore(path).record(report), range(8)))
    assert store.summary()["preparations"] == 1
    assert store.recent_events()[-1]["request_id"] == "unique-request"
    # A long event sequence must not let a repeated request grow counters again.
    for number in range(66):
        store.record({**report, "request_id": f"another-{number}"})
    store.record(report)
    assert store.summary()["preparations"] == 67


def test_context_length_read_only_legacy_migration_and_old_writer_compatibility(tmp_path):
    path = tmp_path / "legacy-activity.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE tomc_request_activity (request_id TEXT PRIMARY KEY, host TEXT NOT NULL, "
                   "session_id TEXT, state TEXT NOT NULL, reason TEXT, started_utc TEXT NOT NULL, "
                   "updated_utc TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0, before_tokens INTEGER, "
                   "after_tokens INTEGER, provider_input_tokens INTEGER, provider_cached_tokens INTEGER)")
        db.execute("INSERT INTO tomc_request_activity VALUES "
                   "('old','claude','s','forwarded','optimized','2026-01-01','2026-01-01',1,9000,5000,8000,1000)")
    original = path.read_bytes()
    activity = RequestActivity(path)
    assert activity.last()["context_input_tokens"] is None
    assert activity.last()["before_tokens"] == 9000
    assert path.read_bytes() == original
    activity.start("new", "claude", "s")
    activity.finish("new", state="prepared", before_tokens=9000, after_tokens=5000, context_input_tokens=6000)
    assert activity.last()["context_input_tokens"] == 6000
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT context_input_tokens FROM tomc_request_activity WHERE request_id='old'").fetchone()[0] is None
        # Old start/finish/sent statements all use explicit columns.
        db.execute("INSERT INTO tomc_request_activity "
                   "(request_id,host,session_id,state,started_utc,updated_utc) "
                   "VALUES ('old-writer','codex','s','preparing','9999','9999')")
        db.execute("UPDATE tomc_request_activity SET state='forwarded',sent=1,before_tokens=1000 WHERE request_id='old-writer'")
    assert activity.last()["context_input_tokens"] is None
    assert activity.last()["before_tokens"] == 1000


@pytest.mark.parametrize("value", [-1, True, 1.5, "10"])
def test_invalid_context_length_does_not_finish_preparation(tmp_path, value):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("r", "codex")
    with pytest.raises(ValueError, match="context_input_tokens"):
        activity.finish("r", state="prepared", context_input_tokens=value)
    assert activity.active()["request_id"] == "r"
    assert activity.last()["context_input_tokens"] is None


def test_prepared_stream_keeps_concurrent_compilations_once_before_provider_completion(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    assert activity.prepared_cursor() == 0 and activity.prepared_events() == []
    assert not activity.path.exists()
    activity.start("historical", "claude")
    activity.finish("historical", state="prepared", context_input_tokens=100)
    cursor = activity.prepared_cursor()

    def compile_one(index):
        request_id = f"compilation-{index}"
        activity.start(request_id, "codex")
        activity.finish(request_id, state="prepared", context_input_tokens=1000 + index)
        activity.finish(request_id, state="prepared", context_input_tokens=1000 + index)
        activity.sent(request_id)
        activity.finish(request_id, state="forwarded", context_input_tokens=1000 + index)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(compile_one, range(12)))
    events = activity.prepared_events(cursor, limit=5)
    events += activity.prepared_events(events[-1]["seq"], limit=5)
    events += activity.prepared_events(events[-1]["seq"], limit=5)
    assert len(events) == 12
    assert len({e["request_id"] for e in events}) == 12
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert {e["context_input_tokens"] for e in events} == set(range(1000, 1012))
    assert all(e["prepared_utc"] for e in events)
    assert activity.prepared_cursor() == events[-1]["seq"]
    assert activity.summary()["provider_usage_requests"] == 0
    # Replays and failures without a new successful compilation cannot animate.
    for request_id, state, context in [("replay", "prepared", None), ("failed", "failed", 10),
                                       ("bypass", "passthrough", None)]:
        activity.start(request_id, "claude")
        activity.finish(request_id, state=state, context_input_tokens=context)
    assert activity.prepared_events(events[-1]["seq"]) == []


def test_prepared_stream_never_backfills_old_activity(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("old", "claude")
    activity.finish("old", state="prepared", context_input_tokens=100)
    with sqlite3.connect(activity.path) as db:
        db.execute("DROP TABLE tomc_context_prepared_events")
    original = activity.path.read_bytes()
    assert activity.prepared_cursor() == 0 and activity.prepared_events() == []
    assert activity.path.read_bytes() == original
    activity.start("new", "claude")
    assert activity.prepared_cursor() == 0 and activity.prepared_events() == []
    activity.finish("new", state="prepared", context_input_tokens=200)
    assert [e["request_id"] for e in activity.prepared_events()] == ["new"]


@pytest.mark.parametrize("options", [{"after_seq": -1}, {"after_seq": True}, {"limit": 0}, {"limit": "2"}])
def test_prepared_stream_rejects_invalid_cursor_options(tmp_path, options):
    with pytest.raises(ValueError):
        RequestActivity(tmp_path / "missing.sqlite3").prepared_events(**options)


def test_protocol_detail_keeps_structural_codes_and_drops_content(tmp_path):
    activity = RequestActivity(tmp_path / "requests.sqlite3")
    activity.start("r", "codex", "s")
    record = activity.finish("r", state="passthrough", reason="native_compaction_state", detail={
        "compaction_items": 2, "window": 4, "request_kind": "turn", "agent": "root",
        "compaction_trigger_item": False, "prompt": "PRIVATE prompt text",
        "compaction_trigger": "two words", "window_id": "thread:4", "history_initialization": "x" * 41})
    assert record["protocol_detail"] == {"agent": "root", "compaction_items": 2,
                                         "compaction_trigger_item": False, "request_kind": "turn", "window": 4}
    assert activity.last()["protocol_detail"] == record["protocol_detail"]
    database = activity.path.read_bytes()
    assert b"PRIVATE" not in database and b"thread:4" not in database and b"two words" not in database
    # A later stage keeps the recorded detail; a non-dict detail is simply absent.
    activity.sent("r")
    assert activity.finish("r", state="failed", reason="client_disconnected",
                           detail="not a dict")["protocol_detail"] == record["protocol_detail"]


def test_protocol_detail_column_is_added_on_first_write_only(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE tomc_request_activity (request_id TEXT PRIMARY KEY, host TEXT NOT NULL, "
                   "session_id TEXT, state TEXT NOT NULL, reason TEXT, started_utc TEXT NOT NULL, "
                   "updated_utc TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0, before_tokens INTEGER, "
                   "after_tokens INTEGER, provider_input_tokens INTEGER, provider_cached_tokens INTEGER, "
                   "context_input_tokens INTEGER)")
        db.execute("INSERT INTO tomc_request_activity VALUES "
                   "('old','codex','s','passthrough','native_compaction','2026-01-01','2026-01-01',1,"
                   "NULL,NULL,10,9,NULL)")
    original = path.read_bytes()
    activity = RequestActivity(path)
    assert activity.last()["protocol_detail"] is None and path.read_bytes() == original
    activity.start("new", "codex", "s")
    activity.finish("new", state="passthrough", reason="host_compaction_request",
                    detail={"request_kind": "compaction", "compaction_trigger": "auto"})
    assert activity.last()["protocol_detail"] == {"compaction_trigger": "auto", "request_kind": "compaction"}
