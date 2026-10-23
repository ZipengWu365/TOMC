import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tomc import session_hook
from tomc.session_store import SessionStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location(
        "install_hooks", ROOT / "scripts/install_session_hooks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event(kind="PreToolUse", **updates):
    return {
        "hook_event_name": kind,
        "session_id": "session-a",
        "cwd": "/project",
        "tool_name": "mcp__tomc__prepare_context",
        "tool_input": {"history": "PRIVATE", "task": "q"},
        **updates,
    }


def test_registration_never_reads_transcript_or_stores_prompt(tmp_path):
    db = tmp_path / "sessions.sqlite3"
    payload = event("SessionStart", transcript_path="DO_NOT_OPEN", prompt="SECRET_PROMPT")
    output = session_hook.handle_event(payload, host="codex", store=db)
    rows = SessionStore(db).list()
    assert len(rows) == 1 and rows[0]["session_id"] == "session-a"
    assert "tomc_session_id" in output["hookSpecificOutput"]["additionalContext"]
    assert "SECRET_PROMPT" not in repr(rows) and "PRIVATE" not in repr(rows)
    assert "DO_NOT_OPEN" not in repr(rows)


@pytest.mark.parametrize("host,canonical", [("codex", "codex"), ("claude_code", "claude")])
def test_per_session_guard_does_not_follow_global_active(tmp_path, host, canonical):
    db = tmp_path / "sessions.sqlite3"
    store = SessionStore(db)
    store.register(canonical, "session-a")
    store.set_enabled(canonical, "session-a", False)
    store.register(canonical, "session-b")
    denied = session_hook.handle_event(event(), host=host, store=db)
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    allowed = session_hook.handle_event(event(session_id="session-b"), host=host, store=db)
    assert "permissionDecision" not in allowed.get("hookSpecificOutput", {})
    assert not store.effective_enabled(canonical, "session-a")


def test_claude_injects_only_identity_and_keeps_approval_unchanged(tmp_path):
    payload = event(tool_name="mcp__plugin_tomc-memory_tomc__recall_memory")
    payload["tool_input"] = {"name": "notes", "task": "q", "budget": 20, "tomc_session_id": "wrong"}
    output = session_hook.handle_event(payload, host="claude_code", store=tmp_path / "s.db")
    hook = output["hookSpecificOutput"]
    assert "permissionDecision" not in hook
    assert hook["updatedInput"] == {
        "name": "notes",
        "task": "q",
        "budget": 20,
        "tomc_host": "claude",
        "tomc_session_id": "session-a",
    }
    assert payload["tool_input"]["tomc_session_id"] == "wrong"


def test_codex_does_not_autoapprove_for_injection(tmp_path):
    assert session_hook.handle_event(event(), host="codex", store=tmp_path / "s.db") == {}


@pytest.mark.parametrize(
    "name",
    [
        "Bash",
        "mcp__other__prepare_context",
        "mcp__tomc__forget_memory",
        "mcp__evil_tomc__prepare_context",
    ],
)
def test_unrelated_tools_never_modified_or_registered(tmp_path, name):
    db = tmp_path / "s.db"
    assert session_hook.handle_event(event(tool_name=name), host="codex", store=db) == {}
    assert not db.exists()


def test_unknown_or_subagent_identity_cannot_bypass_guard(tmp_path):
    for updates in ({"session_id": None}, {"agent_id": "subagent"}, {"session_id": "bad\nvalue"}):
        result = session_hook.handle_event(event(**updates), host="codex", store=tmp_path / "s.db")
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_global_pause_is_enforced(tmp_path):
    db = tmp_path / "s.db"
    SessionStore(db).update_settings(enabled=False)
    assert (
        session_hook.handle_event(event(), host="claude_code", store=db)["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )


@pytest.mark.parametrize("kind", ["Stop", "PreToolUse"])
def test_background_activity_does_not_steal_selected_session(tmp_path, kind):
    db = tmp_path / "s.db"
    store = SessionStore(db)
    store.register("codex", "session-b")
    before = store.active()
    session_hook.handle_event(event(kind), host="codex", store=db)
    after = store.active()
    assert after["session_id"] == "session-b"
    assert after["event_seq"] == before["event_seq"]
    assert any(row["session_id"] == "session-a" for row in store.list())


def test_malformed_target_hook_fails_closed_without_echo(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{SECRET"))
    assert (
        session_hook.main(
            ["--host", "codex", "--event", "PreToolUse", "--store", str(tmp_path / "s.db")]
        )
        == 0
    )
    output = capsys.readouterr()
    assert json.loads(output.out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "SECRET" not in output.out + output.err


def test_dryrun_is_read_only_and_does_not_print_other_settings(tmp_path, installer, capsys):
    path = tmp_path / ".claude/settings.json"
    path.parent.mkdir()
    raw = '{"env":{"API_KEY":"PRIVATE_SECRET"}, "hooks":{}}'
    path.write_text(raw)
    assert installer.main(["--home", str(tmp_path), "--dry-run"]) == 0
    assert path.read_text() == raw
    assert not (tmp_path / ".codex").exists()
    assert not (tmp_path / ".tomc").exists()
    assert "PRIVATE_SECRET" not in capsys.readouterr().out


def test_fakehome_install_preserves_settings_and_is_idempotent(tmp_path, installer):
    path = tmp_path / ".claude/settings.json"
    path.parent.mkdir()
    old = {
        "permissions": {"defaultMode": "plan"},
        "env": {"PRIVATE": "unchanged"},
        "hooks": {
            "SessionStart": [
                {"matcher": "startup", "hooks": [{"type": "command", "command": "existing"}]}
            ]
        },
    }
    raw = json.dumps(old, indent=4)
    path.write_text(raw, encoding="utf-8")
    args = ["--home", str(tmp_path), "--install"]
    assert installer.main(args) == installer.main(args) == 0
    updated = json.loads(path.read_text(encoding="utf-8"))
    assert updated["permissions"] == old["permissions"]
    assert updated["env"] == old["env"]
    assert updated["hooks"]["SessionStart"][0] == old["hooks"]["SessionStart"][0]
    assert len(updated["hooks"]["SessionStart"]) == 2
    backups = list(path.parent.glob("settings.json.tomc-backup-*"))
    assert len(backups) == 2 and any(x.read_text(encoding="utf-8") == raw for x in backups)
    assert not (tmp_path / ".tomc").exists()


def test_bad_existing_config_prevents_both_installs(tmp_path, installer, capsys):
    path = tmp_path / ".claude/settings.json"
    path.parent.mkdir()
    path.write_text("{SECRET")
    assert installer.main(["--home", str(tmp_path), "--install"]) == 1
    assert not (tmp_path / ".codex").exists()
    assert "SECRET" not in capsys.readouterr().err


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows PowerShell pipe and quoting smoke test")
def test_windows_command_handles_unicode_spaces_and_shell_metacharacters(tmp_path, installer):
    store = tmp_path / "猫 $money; & 'test' `echo`" / "store.sqlite3"
    handler = installer.hook_definition(
        "codex",
        python=Path(sys.executable),
        script=ROOT / "src/tomc/session_hook.py",
        store=store,
        event="SessionStart",
    )
    encoded = handler["commandWindows"].split("-EncodedCommand ", 1)[1]
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-EncodedCommand",
            encoded,
        ],
        input=json.dumps(event("SessionStart", cwd="C:/项目")),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert completed.returncode == 0, completed.stderr
    assert SessionStore(store).list()[0]["project"] == "C:/项目"
    assert json.loads(completed.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"
