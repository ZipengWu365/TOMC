"""Redaction, retention, erasure, owner-only files and the first-run notice. All keys are fakes."""

import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tomc import prepare_context
from tomc.anthropic_request import AnthropicAdapter
from tomc.context_library import ContextLibrary
from tomc.privacy import (
    PRIVACY_NOTICE,
    REDACTED,
    erase_all,
    redact,
    redact_value,
    take_privacy_notice,
)
from tomc.request_activity import RequestActivity
from tomc.session_store import SessionStore
from tomc.store import MemoryStore

# Split literals keep these fakes out of the release secret scan (make security-scan).
FAKE_KEYS = (
    "sk-" + "FAKE-secret-0000aaaabbbbcccc",
    "sk-" + "ant-api03-FAKEFAKEFAKEFAKEFAKE",
    "sk_live_FAKE0000",
    "ghp_" + "FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE12",
    "hf_" + "FAKEFAKEFAKEFAKEFAKEFAKEFAKE",
    "AKIAFAKEFAKEFAKEFAKE",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlLXVzZXIifQ.ZmFrZS1zaWduYXR1cmUtdmFsdWU",
)


@pytest.mark.parametrize("key", FAKE_KEYS)
def test_known_token_shapes_are_replaced(key):
    text = f"The tool printed {key} while listing the environment."
    cleaned = redact(text)
    assert key not in cleaned and REDACTED in cleaned
    assert cleaned.startswith("The tool printed ") and cleaned.endswith("environment.")


@pytest.mark.parametrize(
    "line,secret",
    [
        ("OPENAI_API_KEY=abc123def456ghi", "abc123def456ghi"),
        ("export DB_PASSWORD='hunter2-FAKE'", "hunter2-FAKE"),
        ("GITHUB_TOKEN: q1w2e3r4t5y6", "q1w2e3r4t5y6"),
        ('{"api_key": "FAKEvalue123456"}', "FAKEvalue123456"),
        ('{\\"client_secret\\": \\"FAKEvalue987654\\"}', "FAKEvalue987654"),
        ("Authorization: Bear" + "er abcdefghijklmnopqrstuvwxyz012345", "abcdefghijklmnopqr"),
        ("postgres://admin:FAKEpass99@db.internal/app", "FAKEpass99"),
        ("password = correcthorsebattery", "correcthorsebattery"),
    ],
)
def test_env_lines_assignments_bearer_and_url_credentials_are_replaced(line, secret):
    cleaned = redact(line)
    assert secret not in cleaned and REDACTED in cleaned


def test_private_key_blocks_are_removed_even_without_an_end_line():
    kind = "OPENSSH PRIV" + "ATE KEY"
    block = f"-----BEGIN {kind}-----\nAAAAFAKEKEYDATA\nMOREFAKE\n"
    text = f"before\n{block}-----END {kind}-----\nafter"
    assert redact(text) == f"before\n{REDACTED}\nafter"
    cut = redact(f"before\n{block}\nunrelated paragraph")
    assert "AAAAFAKEKEYDATA" not in cut and "unrelated paragraph" in cut


def test_ordinary_text_and_token_counts_are_unchanged():
    text = (
        '{"max_tokens": 2000, "input_tokens": 750, "token_budget": 500}\n'
        "The author asked for a password reset page. task-runner keeps the tokens small.\n"
        "secret_santa = true\nexport DEBUG=1\n"
    )
    assert redact(text) == text


def test_redaction_keeps_json_structure_and_is_fast():
    value = {"messages": [{"role": "user", "content": f"key {FAKE_KEYS[0]}"}], "count": 3}
    cleaned = redact_value(value)
    assert cleaned["count"] == 3 and FAKE_KEYS[0] not in json.dumps(cleaned)
    large = ("Ordinary project notes about capacity and design decisions. " * 30000)[:2_000_000]
    started = time.perf_counter()
    assert redact(large) == large
    assert time.perf_counter() - started < 3


def _snapshot(library, *, preparation_id=None, history="framework = FastAPI", task="continue"):
    return library.save(
        prepare_context(history, task),
        task=task,
        host="codex",
        session_id="chat",
        preparation_id=preparation_id or uuid.uuid4().hex,
    )


def _age(path, table, column, key, value, days):
    old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE {table} SET {column}=? WHERE {key}=?", (old, value))


def test_saved_snapshots_are_redacted_before_writing(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    saved = _snapshot(
        library,
        history=f"deploy = blue\nOPENAI_API_KEY={FAKE_KEYS[0]}\nnote = {FAKE_KEYS[2]}",
        task=f"Use {FAKE_KEYS[1]} to continue the deploy",
    )
    assert FAKE_KEYS[1] not in saved["task"] and REDACTED in saved["task"]
    raw = library.path.read_bytes()
    assert all(key.encode() not in raw for key in FAKE_KEYS[:3])
    assert b"deploy = blue" in raw


def test_snapshots_saved_by_older_versions_are_redacted_once(tmp_path):
    from tomc.context_library import _FIELDS, _canonical, _hash

    library = ContextLibrary(tmp_path / "memory.sqlite3")
    saved = _snapshot(library, history="deploy = blue")
    payload = {key: saved[key] for key in _FIELDS}
    payload["memory"] += f"\nOPENAI_API_KEY={FAKE_KEYS[0]}"
    with sqlite3.connect(library.path) as db:  # As TOMC Memory 0.2.x stored it.
        db.execute(
            "UPDATE tomc_context_snapshots SET payload=?,content_hash=? WHERE id=?",
            (_canonical(payload), _hash(payload), saved["id"]),
        )
    assert library.redact_saved() == 1
    assert library.redact_saved() == 0
    record = library.get(saved["id"])
    assert REDACTED in record["memory"] and "deploy = blue" in record["memory"]
    assert FAKE_KEYS[0].encode() not in library.path.read_bytes()


def test_retention_prunes_old_snapshots_on_save_and_on_request_but_keeps_imports(tmp_path):
    path = tmp_path / "memory.sqlite3"
    library = ContextLibrary(path)
    old = _snapshot(library, history="old fact = expired evidence")
    _age(path, "tomc_context_snapshots", "created_utc", "id", old["id"], 31)
    bundle = library.export(old["id"], tmp_path / "exports")
    imported_into = ContextLibrary(tmp_path / "other.sqlite3")
    imported = imported_into.import_bundle(bundle)
    _age(imported_into.path, "tomc_context_snapshots", "created_utc", "id", imported["id"], 400)
    assert imported_into.prune() == 0  # The user chose to import it.
    fresh = _snapshot(library, history="new fact = current")  # Saving prunes too.
    assert [row["id"] for row in library.list()] == [fresh["id"]]
    assert b"expired evidence" not in path.read_bytes()
    SessionStore(path).update_settings(retention_days=7)
    _age(path, "tomc_context_snapshots", "created_utc", "id", fresh["id"], 8)
    assert library.prune() == 1 and library.list() == []


def test_claude_replay_rows_follow_retention_and_old_rows_are_redacted(tmp_path):
    path = tmp_path / "memory.sqlite3"
    adapter = AnthropicAdapter(path)
    adapter.prune()  # Creates nothing when there is no database.
    assert not path.exists()
    replacement = json.dumps({"format": 2, "compiled_messages": [{"content": FAKE_KEYS[0]}]})
    with sqlite3.connect(path) as db:  # Rows as TOMC Memory 0.2.x saved them.
        AnthropicAdapter._schema(db)
        for session in ("legacy", "expired"):
            db.execute(
                "INSERT INTO tomc_anthropic_prefixes VALUES (?,?,?,?,?,?,?)",
                (session, "hash", 1, replacement, 0, "turn", f"task {FAKE_KEYS[1]}"),
            )
    adapter.prune()
    _age(path, "tomc_anthropic_prefix_times", "saved_utc", "session_id", "expired", 31)
    assert adapter.prune() == 1
    with sqlite3.connect(path) as db:
        rows = db.execute(
            "SELECT session_id,replacement_json,task FROM tomc_anthropic_prefixes"
        ).fetchall()
    assert [row[0] for row in rows] == ["legacy"]
    assert FAKE_KEYS[0] not in rows[0][1] and FAKE_KEYS[1] not in rows[0][2]
    assert REDACTED in rows[0][1]


def test_forget_deletes_the_notebook_and_snapshots_derived_from_it(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    library = ContextLibrary(store.path)
    store.remember("proj", f"Marker sentence about the parser. token={FAKE_KEYS[0]}")
    store.remember("other", "Other notebook stays.")
    prepared = store.recall("proj", "continue")
    library.save(prepared, task="continue", source="recall", notebook_name="proj")
    kept = library.save(store.recall("other", "go"), task="go", notebook_name="other")
    assert store.forget("proj") == {"name": "proj", "deleted_entries": 1, "deleted_snapshots": 1}
    assert [row["id"] for row in library.list()] == [kept["id"]]
    raw = store.path.read_bytes()
    assert b"Marker sentence" not in raw and FAKE_KEYS[0].encode() not in raw


def test_erase_all_removes_every_conversation_record_but_keeps_switches(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    store.remember("proj", "Erase-me sentence one.")
    _snapshot(ContextLibrary(path), history="Erase-me sentence two = yes")
    sessions = SessionStore(path)
    sessions.register("claude", "paused", title="Private title", project="/secret/project")
    sessions.set_enabled("claude", "paused", False)
    sessions.register("codex", "open", title="Another private title")
    sessions.update_settings(save_contexts=False, retention_days=9)
    RequestActivity(path).start("request-1", "codex", "open")
    with sqlite3.connect(path) as db:
        AnthropicAdapter._schema(db)
        db.execute(
            "INSERT INTO tomc_anthropic_prefixes VALUES (?,?,?,?,?,?,?)",
            ("open", "h", 1, '["Erase-me sentence three"]', 0, "t", "task"),
        )
    before = sessions.erase_generation()
    result = erase_all(path)
    assert result["erased"] and result["deleted"]["entries"] == 1
    raw = path.read_bytes()
    for text in (b"Erase-me", b"Private title", b"/secret/project", b"request-1"):
        assert text not in raw
    assert sessions.get("claude", "paused")["enabled"] is False  # The off switch survives.
    assert sessions.get("codex", "open") is None
    assert sessions.settings()["save_contexts"] is False
    assert sessions.settings()["retention_days"] == 9
    assert sessions.erase_generation() == before + 1
    assert store.list() == [] and ContextLibrary(path).list() == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_database_files_are_owner_only_whoever_creates_them(tmp_path):
    old = os.umask(0o022)
    try:
        for index, create in enumerate(
            (
                lambda p: SessionStore(p).register("codex", "chat"),
                lambda p: RequestActivity(p).start("r", "codex", "chat"),
                lambda p: _snapshot(ContextLibrary(p)),
                lambda p: MemoryStore(p),
            )
        ):
            path = tmp_path / str(index) / "memory.sqlite3"
            create(path)
            assert path.stat().st_mode & 0o777 == 0o600
            assert path.parent.stat().st_mode & 0o777 == 0o700
        loose = tmp_path / "loose.sqlite3"
        loose.write_bytes(b"")
        loose.chmod(0o644)
        MemoryStore(loose)  # Opening an older, world-readable file tightens it.
        assert loose.stat().st_mode & 0o777 == 0o600
    finally:
        os.umask(old)


def test_privacy_notice_is_short_bilingual_and_shown_once(tmp_path):
    assert len(PRIVACY_NOTICE["en"].split()) <= 80
    assert len(PRIVACY_NOTICE["zh"]) <= 200
    for text in PRIVACY_NOTICE.values():
        assert "TOMC Memory" in text and "30" in text
    assert take_privacy_notice(tmp_path, "zh") == PRIVACY_NOTICE["zh"]
    assert take_privacy_notice(tmp_path, "zh") is None
    assert take_privacy_notice(tmp_path / "other", "fr") == PRIVACY_NOTICE["en"]


def _cli(*arguments, home):
    return subprocess.run(
        [sys.executable, "-m", "tomc", *arguments],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home), "USERPROFILE": str(home)},
        timeout=60,
    )


def test_command_line_settings_erase_and_restore_direct(tmp_path):
    store = tmp_path / "memory.sqlite3"
    result = _cli(
        "settings",
        "--store",
        str(store),
        "--save-mcp-results",
        "on",
        "--retention-days",
        "14",
        home=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["save_mcp_results"] is True
    assert SessionStore(store).settings()["retention_days"] == 14
    MemoryStore(store).remember("proj", "Command line erase marker.")
    refused = _cli("erase-all", "--store", str(store), home=tmp_path)
    assert refused.returncode == 2 and "Nothing was deleted" in refused.stderr
    assert MemoryStore(store).list()
    erased = _cli("erase-all", "--store", str(store), "--yes", home=tmp_path)
    assert erased.returncode == 0 and json.loads(erased.stdout)["erased"]
    assert b"Command line erase marker" not in store.read_bytes()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex/config.toml").write_text(
        'model = "m"\nopenai_base_url = "http://127.0.0.1:43187/codex"\n[projects."/x"]\n'
    )
    direct = _cli("restore-direct", "--home", str(tmp_path), home=tmp_path)
    assert direct.returncode == 0 and json.loads(direct.stdout)["status"] == "restored"
    assert (tmp_path / ".codex/config.toml").read_text() == 'model = "m"\n[projects."/x"]\n'
    again = _cli("restore-direct", "--home", str(tmp_path), home=tmp_path)
    assert json.loads(again.stdout)["status"] == "already_restored"
