import json
from pathlib import Path

import pytest

from tomc import integration_status as status

# Codex settings are TOML. Python 3.10 has no tomllib, and the reader then reports
# "unknown" by design instead of guessing (test_no_toml_parser_does_not_guess).
requires_toml = pytest.mark.skipif(
    status.tomllib is None, reason="reading Codex TOML needs Python 3.11+ tomllib"
)


def write(home, name, data):
    path = home / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_missing_home_does_not_create_anything(tmp_path):
    home = tmp_path / "not-created"
    result = status.get_integration_status(home)
    assert not home.exists()
    for name in ("codex", "claude_code"):
        assert result[name]["state"] == "not_configured"
        assert result[name]["runtime_verified"] is False
        assert result[name]["project_scope"] == "unknown"
    assert result["mode"]["automatic_request_compression"] is False


@requires_toml
@pytest.mark.parametrize("enabled,state", [("true", "enabled"), ("false", "disabled")])
def test_codex_explicit_user_plugin_state(tmp_path, enabled, state):
    write(tmp_path, ".codex/config.toml", f'[plugins."tomc-memory@tomc-local"]\nenabled={enabled}')
    assert status.get_integration_status(tmp_path)["codex"]["state"] == state


def test_only_user_scope_is_observed_and_never_secrets(tmp_path):
    write(
        tmp_path,
        ".claude.json",
        {
            "mcpServers": {"tomc-memory": {"command": "SECRET_COMMAND", "env": {"KEY": "SECRET"}}},
            "projects": {"PRIVATE_PROJECT": {"disabledMcpServers": ["tomc-memory"]}},
        },
    )
    result = status.get_integration_status(tmp_path)
    assert result["claude_code"]["state"] == "enabled"
    assert result["claude_code"]["project_scope"] == "unknown"
    assert "SECRET" not in json.dumps(result) and "PRIVATE_PROJECT" not in json.dumps(result)


def test_project_only_configuration_is_not_reported_global(tmp_path):
    write(tmp_path, ".claude.json", {"projects": {"x": {"mcpServers": {"tomc": {}}}}})
    assert status.get_integration_status(tmp_path)["claude_code"]["state"] == "not_configured"


def test_claude_disabled_server_precedes_presence(tmp_path):
    write(tmp_path, ".claude.json", {"mcpServers": {"tomc": {}}, "disabledMcpServers": ["tomc"]})
    assert status.get_integration_status(tmp_path)["claude_code"]["state"] == "disabled"


def test_independent_enabled_plugin_remains_available(tmp_path):
    write(tmp_path, ".claude.json", {"mcpServers": {"tomc": {}}, "disabledMcpServers": ["tomc"]})
    write(tmp_path, ".claude/settings.json", {"enabledPlugins": {"tomc-memory@tomc": True}})
    assert status.get_integration_status(tmp_path)["claude_code"]["state"] == "enabled"


@pytest.mark.parametrize(
    "path,raw,host",
    [
        (".codex/config.toml", "[broken", "codex"),
        (".codex/config.toml", 'plugins = "bad"', "codex"),
        (".codex/config.toml", '[plugins."tomc-memory@x"]\nenabled="false"', "codex"),
        (".claude.json", "{broken SECRET", "claude_code"),
        (".claude.json", "[]", "claude_code"),
        (".claude/settings.json", '{"enabledPlugins":{"tomc-memory@tomc":1}}', "claude_code"),
    ],
)
def test_invalid_configuration_is_unknown(tmp_path, path, raw, host):
    write(tmp_path, path, raw)
    assert status.get_integration_status(tmp_path)[host]["state"] == "unknown"


def test_read_error_is_sanitized(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("SECRET_PATH")

    monkeypatch.setattr(Path, "read_text", denied)
    result = status.get_integration_status(tmp_path)
    assert result["codex"]["state"] == result["claude_code"]["state"] == "unknown"
    assert "SECRET_PATH" not in json.dumps(result)


def test_no_toml_parser_does_not_guess(tmp_path, monkeypatch):
    write(tmp_path, ".codex/config.toml", '[plugins."tomc-memory@x"]\nenabled=true')
    monkeypatch.setattr(status, "tomllib", None)
    assert status.get_integration_status(tmp_path)["codex"]["state"] == "unknown"


def test_home_default_is_explicitly_mockable(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert status.get_integration_status() == status.get_integration_status(tmp_path)


@requires_toml
def test_gateway_marker_requires_matching_client_configuration(tmp_path):
    write(
        tmp_path, ".codex/tomc/gateway-routing.json", {"port": 43187, "hosts": ["codex", "claude"]}
    )
    assert not status.get_integration_status(tmp_path)["mode"]["automatic_request_compression"]
    write(tmp_path, ".codex/config.toml", 'openai_base_url="http://127.0.0.1:43187/codex"')
    mode = status.get_integration_status(tmp_path)["mode"]
    assert mode["configured_hosts"] == ["codex"]
    assert mode["automatic_request_compression"] is True
    assert mode["runtime_verified"] is False
    assert mode["client_reload"] == {"codex": "restart_or_new_thread_required"}


def test_old_restart_marker_does_not_override_current_claude_reload_status(tmp_path):
    write(
        tmp_path,
        ".codex/tomc/gateway-routing.json",
        {
            "port": 43187,
            "hosts": ["claude"],
            "requires_client_restart": True,
        },
    )
    write(
        tmp_path,
        ".claude/settings.json",
        {
            "env": {
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:43187/claude",
                "CLAUDE_CODE_GATEWAY_HINT_HEADERS": "1",
            }
        },
    )
    mode = status.get_integration_status(tmp_path)["mode"]
    assert mode["client_reload"] == {"claude": "settings_env_hot_reload_supported"}
    assert mode["runtime_verified"] is False
    assert "热加载" in mode["detail"] and "以后续请求活动为准" in mode["detail"]
    assert "Claude Code 用户设置支持热加载" in mode["detail"]
    assert "Codex" not in mode["detail"]
