"""Global defaults, explicit session identity, switches, and concurrent host events."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from tomc.session_store import SessionStore


def test_reads_and_empty_settings_update_do_not_create_storage(tmp_path):
    path = tmp_path / "missing" / "memory.sqlite3"
    store = SessionStore(path)
    assert store.settings() == {"enabled": True, "save_contexts": True}
    assert store.update_settings() == store.settings()
    assert store.list() == []
    assert store.active() is None
    assert store.get("codex", "unknown") is None
    assert not store.requires_identity()
    assert store.effective_enabled()
    assert store.effective_enabled("codex", "unknown")
    assert not path.parent.exists()


def test_per_session_opt_out_survives_activity_and_global_pause(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    first = store.register("codex", "thread-a", title="猫咪动画", project="example")
    assert first["enabled"] and first["effective_enabled"]
    assert not store.set_enabled("codex", "thread-a", False)["effective_enabled"]
    updated = store.register("codex", "thread-a", event="resume")
    assert updated["title"] == "猫咪动画" and updated["project"] == "example"
    assert updated["first_seen"] == first["first_seen"]
    assert updated["last_seen"] >= first["last_seen"]
    assert not updated["enabled"]
    store.register("claude", "thread-a")
    assert store.effective_enabled("claude", "thread-a")
    assert not store.effective_enabled("codex", "thread-a")
    store.update_settings(enabled=False)
    assert not store.effective_enabled("claude", "thread-a")
    assert not store.effective_enabled()
    assert all(not row["effective_enabled"] for row in store.list())
    store.update_settings(enabled=True)
    assert store.effective_enabled("claude", "thread-a")
    assert not store.effective_enabled("codex", "thread-a")


def test_active_switch_sequence_is_stable_for_activity_and_settings(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    store.register("codex", "a")
    assert store.active()["event_seq"] == 1
    store.register("codex", "a", event="activity")
    store.set_enabled("codex", "a", False)
    active = store.active()
    assert active["event_seq"] == 1 and not active["enabled"]
    store.register("claude", "background", activate=False)
    assert store.active()["session_id"] == "a"
    assert store.active()["event_seq"] == 1
    store.register("codex", "b")
    assert store.active()["event_seq"] == 2
    store.register("codex", "a")
    assert store.active()["event_seq"] == 3
    assert not store.active()["effective_enabled"]


def test_unattributed_requests_never_inherit_the_active_sessions_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "must-not-be-read")
    store = SessionStore(tmp_path / "memory.sqlite3")
    store.register("codex", "explicit")
    store.set_enabled("codex", "explicit", False)
    assert store.effective_enabled()
    assert store.effective_enabled("codex", "different")
    row = store.list()[0]
    assert row["session_id"] == "explicit"
    assert row["project"] is row["title"] is None


def test_setting_unknown_session_does_not_make_it_active(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    assert not store.set_enabled("claude", "known-id", False)["enabled"]
    assert store.active() is None
    assert not store.register("claude", "known-id")["enabled"]
    assert store.active()["event_seq"] == 1


def test_direct_session_lookup_and_identity_requirement(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    store.register("codex", "same-id", title="first chat")
    store.register("claude", "same-id", title="other host")
    assert not store.requires_identity()
    assert store.get("codex", "same-id")["title"] == "first chat"
    assert store.get("claude", "same-id")["title"] == "other host"
    assert store.get("codex", "missing") is None
    store.set_enabled("codex", "same-id", False)
    assert store.requires_identity()
    assert not store.get("codex", "same-id")["enabled"]
    assert store.get("claude", "same-id")["effective_enabled"]
    store.update_settings(enabled=False)
    assert store.requires_identity()
    assert not store.get("claude", "same-id")["effective_enabled"]
    store.set_enabled("codex", "same-id", True)
    assert not store.requires_identity()


def test_direct_lookup_is_not_limited_to_visible_list(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    store.register("codex", "older")
    store.register("codex", "newer")
    assert store.list(limit=1)[0]["session_id"] == "newer"
    assert store.get("codex", "older")["session_id"] == "older"


def test_global_settings_preserve_the_other_switch(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    assert store.update_settings(save_contexts=False) == {"enabled": True, "save_contexts": False}
    assert store.update_settings(enabled=False) == {"enabled": False, "save_contexts": False}
    assert store.update_settings(save_contexts=True) == {"enabled": False, "save_contexts": True}
    assert SessionStore(store.path).settings() == store.settings()


def test_concurrent_writers_keep_all_sessions_and_monotonic_switches(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with ThreadPoolExecutor(max_workers=8) as workers:
        rows = list(workers.map(lambda number: SessionStore(path).register(
            "codex", f"thread-{number}", title=f"任务 {number}"), range(40)))
    store = SessionStore(path)
    assert len(rows) == len(store.list()) == 40
    assert store.active()["event_seq"] == 40
    assert len(store.list(limit=3)) == 3


def test_existing_notebook_table_is_untouched(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE entries (payload TEXT)")
        db.execute("INSERT INTO entries VALUES ('existing note')")
    store = SessionStore(path)
    assert store.settings()["enabled"]
    assert store.list() == [] and store.active() is None
    assert store.get("codex", "missing") is None
    assert not store.requires_identity()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("entries",)]
    store.register("codex", "a")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM entries").fetchall() == [("existing note",)]


@pytest.mark.parametrize("bad", ["false", 0, 1, [], {}])
def test_settings_reject_non_boolean_values_before_writing(tmp_path, bad):
    store = SessionStore(tmp_path / "memory.sqlite3")
    with pytest.raises(ValueError):
        store.update_settings(enabled=bad)
    with pytest.raises(ValueError):
        store.set_enabled("codex", "a", bad)
    assert not store.path.exists()


@pytest.mark.parametrize("bad", [0, -1, True, "1", 10001])
def test_invalid_limit_is_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        SessionStore(tmp_path / "memory.sqlite3").list(bad)


def test_invalid_identity_does_not_create_a_database(tmp_path):
    store = SessionStore(tmp_path / "memory.sqlite3")
    for host, session in [("", "a"), ("codex", ""), ("../codex", "a"), ("codex", "a\nb")]:
        with pytest.raises(ValueError):
            store.register(host, session)
    assert not store.path.exists()
