"""Read user-level TOMC configuration, without launching hosts or reading chats.

These are configuration observations, never claims about loaded sessions or a
live MCP connection. Project, managed and per-session overrides are not read.
"""

import json
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10: do not guess TOML with regular expressions.
    tomllib = None


_LABELS = {
    "enabled": "配置已启用",
    "not_configured": "未配置",
    "disabled": "已禁用",
    "unknown": "未知",
}


def _tomc(name, *, plugin=False):
    return isinstance(name, str) and (
        name == "tomc-memory" or name.startswith("tomc-memory@")
        or (not plugin and name == "tomc")
    )


def _read(path, *, toml=False):
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}, False
    except (OSError, UnicodeError):
        return {}, True
    if toml and tomllib is None:
        return {}, True
    try:
        data = tomllib.loads(raw) if toml else json.loads(raw)
    except (ValueError, TypeError):
        return {}, True
    return (data, False) if isinstance(data, dict) else ({}, True)


def _summary(states, source_error=False):
    if "enabled" in states:
        state = "enabled"
    elif source_error or "unknown" in states:
        state = "unknown"
    elif "disabled" in states:
        state = "disabled"
    else:
        state = "not_configured"
    detail = {
        "enabled": "检测到用户级 TOMC 启用项；会话加载与连接尚未核验。",
        "not_configured": "未发现用户级 TOMC 配置；项目或会话配置未检查。",
        "disabled": "检测到用户级 TOMC 禁用项；项目或会话覆盖未检查。",
        "unknown": "配置无法完整读取或格式不受支持，暂不能确认。",
    }[state]
    if state == "enabled" and (source_error or "unknown" in states):
        detail += "部分配置仍无法确认。"
    return {
        "state": state, "label": _LABELS[state], "detail": detail,
        "scope": "user", "runtime_verified": False, "project_scope": "unknown",
    }


def get_integration_status(home=None):
    """Return sanitized configuration summaries for a home directory (read-only)."""
    home = Path.home() if home is None else Path(home)
    codex, codex_error = _read(home / ".codex" / "config.toml", toml=True)
    states = []
    plugins = codex.get("plugins", {})
    if isinstance(plugins, dict):
        for name, settings in plugins.items():
            if _tomc(name, plugin=True):
                enabled = settings.get("enabled") if isinstance(settings, dict) else None
                states.append("enabled" if enabled is True else
                              "disabled" if enabled is False else "unknown")
    else:
        codex_error = True
    codex_status = _summary(states, codex_error)

    claude, claude_error = _read(home / ".claude.json")
    settings, settings_error = _read(home / ".claude" / "settings.json")
    states = []
    servers = claude.get("mcpServers", {})
    disabled = claude.get("disabledMcpServers", [])
    if not isinstance(disabled, list) or any(not isinstance(x, str) for x in disabled):
        disabled = []
        claude_error = True
    if isinstance(servers, dict):
        for name, server in servers.items():
            if _tomc(name):
                if name in disabled:
                    states.append("disabled")
                elif isinstance(server, dict):
                    states.append("enabled")
                else:
                    states.append("unknown")
    else:
        claude_error = True
    if any(_tomc(name) for name in disabled):
        states.append("disabled")
    plugins = settings.get("enabledPlugins", {})
    if isinstance(plugins, dict):
        for name, enabled in plugins.items():
            if _tomc(name, plugin=True):
                states.append("enabled" if enabled is True else
                              "disabled" if enabled is False else "unknown")
    else:
        settings_error = True
    return {
        "mode": {
            "id": "on_demand_tools", "label": "按需工具",
            "detail": "全局配置使工具可用；仅在调用时准备上下文。自动全对话请求压缩尚未接入。",
            "automatic_request_compression": False,
        },
        "codex": codex_status,
        "claude_code": _summary(states, claude_error or settings_error),
    }
