import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "claude_settings_refresh", SCRIPTS / "refresh_claude_gateway_settings.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def settings(home, *, port=43187, hint="1", raw=None):
    path = home / ".claude/settings.json"
    path.parent.mkdir(parents=True)
    value = {
        "env": {
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}/claude",
            "CLAUDE_CODE_GATEWAY_HINT_HEADERS": hint,
            "PRIVATE_FIXTURE_TOKEN": "do-not-display-fixture",
        },
        "model": "existing-model",
        "permissions": {"allow": ["Read(fixture)"], "deny": []},
        "unknown": {"nested": [True, 1, None, "原文"]},
    }
    path.write_bytes(raw if raw is not None else json.dumps(value, ensure_ascii=False).encode())
    return path, value


def test_matching_values_preserve_bytes_and_timestamp_without_archive(tmp_path, capsys):
    path, _ = settings(tmp_path)
    before, mtime = path.read_bytes(), path.stat().st_mtime_ns
    assert module.plan_refresh(tmp_path).changes == ()
    assert module.main(["--home", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry-run" and output["status"] == "unchanged"
    assert path.read_bytes() == before and path.stat().st_mtime_ns == mtime
    assert not (tmp_path / ".codex").exists()
    assert "do-not-display-fixture" not in str(output)


def test_preview_changes_only_existing_tomc_values(tmp_path):
    path, original = settings(tmp_path, port=18740, hint="0")
    before = path.read_bytes()
    plan = module.plan_refresh(tmp_path)
    assert len(plan.changes) == 1 and plan.changes[0].relative == ".claude/settings.json"
    updated = json.loads(plan.changes[0].after)
    expected = json.loads(json.dumps(original))
    expected["env"]["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:43187/claude"
    expected["env"]["CLAUDE_CODE_GATEWAY_HINT_HEADERS"] = "1"
    assert updated == expected
    assert path.read_bytes() == before
    assert not (tmp_path / ".codex").exists()


def test_apply_keeps_exact_backup_and_utf8_bom(tmp_path, capsys):
    path, _ = settings(tmp_path, hint="0")
    before = b"\xef\xbb\xbf" + path.read_bytes() + b"\r\n"
    path.write_bytes(before)
    assert module.main(["--home", str(tmp_path), "--apply"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "installed"
    assert output["changed_keys"] == ["CLAUDE_CODE_GATEWAY_HINT_HEADERS"]
    assert "do-not-display-fixture" not in str(output)
    receipt_path = Path(output["receipt"])
    receipt = json.loads(receipt_path.read_text())
    assert (receipt_path.parent / receipt["changes"][0]["backup"]).read_bytes() == before
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert receipt["processes_restarted"] is False


def test_concurrent_user_edit_is_not_overwritten(tmp_path):
    path, _ = settings(tmp_path, hint="0")
    plan = module.plan_refresh(tmp_path)
    path.write_bytes(b'{"user":"concurrent edit"}')
    with pytest.raises(ValueError, match="changed since validation"):
        module.install(plan)
    assert path.read_bytes() == b'{"user":"concurrent edit"}'
    assert not (tmp_path / ".codex").exists()


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b'{"env":{}}',
        b"[]",
        b'{"env":{},"env":{}}',
        b'{"env":{},"unknown":NaN}',
        b"{broken-private-fixture",
    ],
)
def test_missing_or_ambiguous_settings_refused_without_data_disclosure(tmp_path, capsys, raw):
    path, _ = settings(tmp_path, raw=raw)
    assert module.main(["--home", str(tmp_path)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output == {"status": "refused", "error_type": "ValueError"}
    assert path.read_bytes() == raw
    assert not (tmp_path / ".codex").exists()


@pytest.mark.parametrize(
    "url",
    [
        "https://api.anthropic.com",
        "http://127.0.0.1:43187/other",
        "http://user:private@127.0.0.1:43187/claude",
        "http://127.0.0.1:43187/claude?key=private",
    ],
)
def test_foreign_or_credential_url_refused(tmp_path, url):
    path, value = settings(tmp_path)
    value["env"]["ANTHROPIC_BASE_URL"] = url
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="non-TOMC"):
        module.plan_refresh(tmp_path)


@pytest.mark.parametrize("port", [True, 80, 65536, "43187"])
def test_invalid_port_refused(tmp_path, port):
    with pytest.raises(ValueError, match="Port"):
        module.plan_refresh(tmp_path, port)
