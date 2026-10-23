"""Accounting boundaries: persistence, concurrent callers, empty/expanded context."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from tomc import prepare_context
from tomc.mcp_server import _reply
from tomc.usage import UsageStore, reduction_report


def test_zero_and_empty_context_do_not_claim_savings():
    short = reduction_report(prepare_context("Keep the original note.", "continue"))
    assert short["reduced_tokens"] == short["reduction_percent"] == 0
    empty = reduction_report(prepare_context("long indivisible text " * 100, "quote", 1))
    assert not empty["usable"]
    assert empty["reduced_tokens"] is empty["reduction_percent"] is None


def test_real_long_history_reduction_reaches_cumulative_totals(tmp_path):
    history = "\n".join(f"project_{i} = status_{i}" for i in range(300))
    prepared = prepare_context(history, "What is project_299?", 128)
    store = UsageStore(tmp_path / "usage.sqlite3")
    reply = _reply(prepared, store)
    reduction = reply["context_reduction"]
    assert reduction["recorded"] and reduction["reduced_tokens"] > 0
    assert reduction["memory_tokens"] <= 128
    totals = store.summary()["by_counter"][0]
    assert totals["reduced_tokens"] == reduction["reduced_tokens"]
    assert totals["reduction_percent"] == reduction["reduction_percent"]


def test_persistent_weighted_totals_include_expansion_and_exclude_empty(tmp_path):
    store = UsageStore(tmp_path / "usage.sqlite3")
    prepared = prepare_context("private original note", "private task")
    for before, after in [(100, 40), (10, 20), (1000, 0)]:
        prepared.compilation.stats = replace(
            prepared.compilation.stats, input_tokens=before, output_tokens=after
        )
        prepared.compilation.compiled_memory = "memory" if after else ""
        _reply(prepared, store)
    group = UsageStore(store.path).summary()["by_counter"][0]
    assert group["preparations"] == 3 and group["usable_preparations"] == 2
    assert group["increased_preparations"] == group["excluded_empty_preparations"] == 1
    assert group["input_tokens"] == 110 and group["memory_tokens"] == 60
    assert group["reduced_tokens"] == 50 and group["reduction_percent"] == 45.45
    with sqlite3.connect(store.path) as db:
        dump = "\n".join(db.iterdump())
    assert "private original" not in dump and "private task" not in dump
    assert "memory" not in dump.replace("memory_tokens", "")


def test_concurrent_calls_and_read_only_queries(tmp_path):
    path = tmp_path / "usage.sqlite3"
    store = UsageStore(path)
    assert store.summary()["preparations"] == 0
    report = reduction_report(prepare_context("short note", "continue"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: UsageStore(path).record(report), range(30)))
    assert store.summary() == store.summary()
    assert store.summary()["preparations"] == 30


def test_periods_and_separate_token_counters(tmp_path):
    store = UsageStore(tmp_path / "usage.sqlite3")
    report = reduction_report(prepare_context("short note", "continue"))
    store.record(report)
    store.record({**report, "counter": "different-encoding"})
    today = datetime.now(timezone.utc).date()
    with sqlite3.connect(store.path) as db:
        for age in (6, 7):
            db.execute(
                "INSERT INTO context_usage_daily VALUES (?,?,?,?,?,?,?)",
                (str(today - timedelta(days=age)), report["counter"], 1, 1, 0, 100, 50),
            )
    assert store.summary("today")["preparations"] == 2
    assert store.summary("7d")["preparations"] == 3
    assert store.summary("all")["preparations"] == 4
    assert len(store.summary()["by_counter"]) == 2
    with pytest.raises(ValueError):
        store.summary("anything")


def test_failed_statistics_write_does_not_drop_prepared_memory(tmp_path):
    # An invalid database must not turn successful context preparation into failure.
    path = tmp_path / "broken.sqlite3"
    path.write_text("not a SQLite database")
    reply = _reply(prepare_context("Keep this note", "continue"), UsageStore(path))
    assert reply["memory"] == "Keep this note"
    assert not reply["context_reduction"]["recorded"]
    assert "not recorded" in reply["context_reduction"]["summary"]


def test_latest_preparation_is_replaced_without_losing_totals(tmp_path):
    store = UsageStore(tmp_path / "usage.sqlite3")
    assert store.summary()["last_preparation"] is None
    assert not store.path.exists()  # A view must not initialize a new notebook DB.
    first = reduction_report(prepare_context("first private note", "continue"))
    store.record(first)
    first_time = store.summary()["last_preparation"]["recorded_at"]
    second = {**first, "input_tokens": 100, "memory_tokens": 25,
              "reduced_tokens": 75, "reduction_percent": 75}
    store.record(second)
    summary = store.summary()
    assert summary["preparations"] == 2
    assert summary["last_preparation"]["reduced_tokens"] == 75
    assert summary["last_preparation"]["recorded_at"] >= first_time
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM context_usage_latest").fetchone()[0] == 1


def test_widget_retains_negative_values_and_separates_encodings():
    from tomc.usage_widget import display_values

    summary = {"preparations": 1, "by_counter": [{"input_tokens": 10,
               "memory_tokens": 20, "reduced_tokens": -10, "reduction_percent": -100}]}
    assert display_values(summary)["total"] == "-10"
    summary["by_counter"].append(dict(summary["by_counter"][0]))
    assert display_values(summary)["total"] == "分计数器查看"


def test_context_length_is_independent_of_request_totals_and_idempotency(tmp_path):
    store = UsageStore(tmp_path / "usage.sqlite3")
    report = {"counter": "regex-request-json-v1 (estimate)", "usable": True,
              "input_tokens": 9000, "memory_tokens": 7000, "reduced_tokens": 2000,
              "context_input_tokens": 2500, "request_id": "first"}
    store.record(report)
    store.record({**report, "context_input_tokens": 8000})
    summary = store.summary()
    assert summary["preparations"] == 1
    assert summary["by_counter"][0]["input_tokens"] == 9000
    assert summary["by_counter"][0]["reduced_tokens"] == 2000
    assert summary["last_preparation"]["context_input_tokens"] == 2500
    assert store.recent_events()[0]["context_input_tokens"] == 2500
    store.record({k: v for k, v in {**report, "request_id": "replay"}.items()
                  if k != "context_input_tokens"})
    assert store.summary()["preparations"] == 2
    assert store.summary()["last_preparation"]["context_input_tokens"] is None
    assert store.recent_events()[-1]["context_input_tokens"] is None


def test_legacy_usage_read_and_old_writer_remain_compatible_after_migration(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE context_usage_latest (id INTEGER PRIMARY KEY, recorded_at TEXT, "
                   "counter TEXT, input_tokens INTEGER, memory_tokens INTEGER, usable INTEGER)")
        db.execute("CREATE TABLE context_usage_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "recorded_at TEXT, counter TEXT, input_tokens INTEGER, memory_tokens INTEGER, "
                   "usable INTEGER, request_id TEXT)")
        db.execute("INSERT INTO context_usage_latest VALUES (1,'old','regex-request-json-v1 (estimate)',1000,500,1)")
        db.execute("INSERT INTO context_usage_events VALUES (1,'old','regex-request-json-v1 (estimate)',1000,500,1,NULL)")
    original = path.read_bytes()
    store = UsageStore(path)
    assert store.summary()["last_preparation"]["context_input_tokens"] is None
    assert store.recent_events()[0]["context_input_tokens"] is None
    assert path.read_bytes() == original  # Read-only views do not migrate the DB.
    store.record({"counter": "regex-request-json-v1 (estimate)", "usable": True,
                  "input_tokens": 9000, "memory_tokens": 7000, "reduced_tokens": 2000,
                  "context_input_tokens": 2500})
    with sqlite3.connect(path) as db:
        assert len(list(db.execute("PRAGMA table_info(context_usage_latest)"))) == 6
        # Already-running old MCP/gateway modules retain these exact SQL forms.
        db.execute("INSERT OR REPLACE INTO context_usage_latest VALUES (1,'old-writer','regex',100,50,1)")
        db.execute("INSERT INTO context_usage_events "
                   "(recorded_at,counter,input_tokens,memory_tokens,usable,request_id) "
                   "VALUES ('old-writer','regex',100,50,1,NULL)")
    assert store.summary()["last_preparation"]["context_input_tokens"] is None
    assert store.recent_events()[-1]["context_input_tokens"] is None
    # Even a legacy writer with no event must not inherit the preceding length.
    with sqlite3.connect(path) as db:
        db.execute("UPDATE context_usage_events SET context_input_tokens=9999 WHERE recorded_at='old-writer'")
        db.execute("INSERT OR REPLACE INTO context_usage_latest VALUES (1,'no-event','regex',200,80,1)")
    assert store.summary()["last_preparation"]["context_input_tokens"] is None


@pytest.mark.parametrize("value", [-1, True, 1.5, "10"])
def test_invalid_context_length_does_not_create_accounting_records(tmp_path, value):
    store = UsageStore(tmp_path / "usage.sqlite3")
    with pytest.raises(ValueError, match="context_input_tokens"):
        store.record({"usable": True, "context_input_tokens": value})
    assert not store.path.exists()


def test_usage_event_cursor_and_paging_do_not_drop_bursts_larger_than_64(tmp_path):
    store = UsageStore(tmp_path / "usage.sqlite3")
    assert store.event_cursor() == 0 and not store.path.exists()
    report = {"counter": "regex", "usable": True, "input_tokens": 1000,
              "memory_tokens": 100, "reduced_tokens": 900}
    store.record({**report, "request_id": "historical"})
    cursor = store.event_cursor()
    for number in range(80):
        store.record({**report, "request_id": f"burst-{number}"})
    events = []
    while batch := store.recent_events(cursor, limit=13):
        events.extend(batch)
        cursor = batch[-1]["seq"]
    assert len(events) == 80
    assert [e["request_id"] for e in events] == [f"burst-{n}" for n in range(80)]
    assert cursor == store.event_cursor()
    assert len(store.recent_events()) == 81
    store.record({**report, "request_id": "burst-0"})
    assert store.event_cursor() == cursor  # Dedup still applies after a long burst.
