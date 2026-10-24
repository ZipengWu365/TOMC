import argparse
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_codex_gateway.py"
spec = importlib.util.spec_from_file_location("validate_codex_gateway", SCRIPT)
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


def test_recoverable_error_then_success_is_not_terminal_and_raw_error_is_not_recorded():
    events = [
        {"type": "thread.started", "thread_id": "test-thread"},
        {"type": "error", "message": "raw private error data"},
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "exit_code": 0,
                "command": "private command",
                "aggregated_output": "TOMC_FIXTURE_OK_47",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 5}},
    ]
    result = validation.selected_events("\n".join(map(json.dumps, events)))
    assert result["completed"] and not result["error_seen"]
    assert result["recovery_error_events"] == 1
    assert result["tools"] == [
        {"type": "command_execution", "exit_code": 0, "fixture_marker_seen": True}
    ]
    assert "private" not in json.dumps(result)
    assert "cumulative" in result["usage_scope"]


def test_terminal_failure_is_retained():
    result = validation.selected_events(json.dumps({"type": "turn.failed", "error": "private"}))
    assert result["error_seen"] and not result["completed"]
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/codex",
        "http://127.0.0.1:1/v1",
        "http://secret@127.0.0.1:1/codex",
        "http://127.0.0.1:1/codex?key=secret",
    ],
)
def test_only_credential_free_loopback_base_url_is_allowed(url):
    with pytest.raises(argparse.ArgumentTypeError):
        validation.gateway_url(url)


def test_command_only_overrides_base_url_and_inherits_model_permissions():
    result = validation.command(
        "codex.exe", "http://127.0.0.1:18739/codex", Path("fixture"), "thread-123", None
    )
    assert result == [
        "codex.exe",
        "exec",
        "-c",
        'openai_base_url="http://127.0.0.1:18739/codex"',
        "--json",
        "resume",
        "thread-123",
        "-",
    ]
