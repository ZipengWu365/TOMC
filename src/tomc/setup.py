"""Client configuration: print it, or merge it into the client's file with a backup."""

from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .store import default_store_path

CLIENTS = (
    "codex",
    "cursor",
    "trae",
    "workbuddy",
    "claude",
    "claude-desktop",
    "claude-code",
    "deepseek",
    "json",
)
# "claude" has always meant Claude Desktop; keep it working.
ALIASES = {"claude-desktop": "claude"}
NAMES = {
    "codex": "Codex",
    "cursor": "Cursor",
    "trae": "TRAE",
    "workbuddy": "WorkBuddy",
    "claude": "Claude Desktop",
    "claude-code": "Claude Code",
    "deepseek": "DeepSeek Harness",
    "json": "your MCP client",
}


def canonical(client: str) -> str:
    return ALIASES.get(client, client)


def _launch(store: Path | None) -> tuple[str, list[str]]:
    """Use this installation's absolute interpreter, preserving its virtualenv path."""
    command = os.path.abspath(sys.executable)
    args = [
        "-m",
        "tomc",
        "mcp",
        "--store",
        str((store or default_store_path()).expanduser().absolute()),
    ]
    return command, args


def server_entry(client: str, store: Path | None = None) -> dict:
    """The ``mcpServers.tomc`` object for a JSON-configured client."""
    client = canonical(client)
    command, args = _launch(store)
    if client == "trae" and any(char.isspace() for char in command):
        raise ValueError(
            "TRAE requires a command path without spaces. Use a TOMC environment "
            "at a path without spaces, or the UV template in docs/cursor_trae.md."
        )
    server = {"command": command, "args": args}
    if client in ("cursor", "workbuddy", "claude-code"):
        server = {"type": "stdio", **server}
    return server


def client_config(client: str, store: Path | None = None) -> str:
    """Configuration text to paste into the client."""
    client = canonical(client)
    command, args = _launch(store)
    if client == "codex":
        return f"[mcp_servers.tomc]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
    if client == "claude-code":
        return (
            _join(["claude", "mcp", "add", "--scope", "user", "tomc", "--", command, *args]) + "\n"
        )
    if client == "deepseek":
        # JSON is a YAML subset. DSH reads this as an additive Cordis overlay.
        return (
            json.dumps(
                [
                    {
                        "insert": [
                            {
                                "id": "mcp-tomc",
                                "name": "@deepseek-ai/dsh-mcp-client",
                                "config": {
                                    "serverName": "tomc",
                                    "transport": "stdio",
                                    "command": command,
                                    "args": args,
                                    "failOnStartupError": True,
                                },
                            }
                        ]
                    }
                ],
                indent=2,
            )
            + "\n"
        )
    if client not in CLIENTS:
        raise ValueError("Choose one of: " + ", ".join(CLIENTS) + ".")
    return json.dumps({"mcpServers": {"tomc": server_entry(client, store)}}, indent=2) + "\n"


def client_link(client: str, store: Path | None = None) -> str:
    """Print a Cursor install link for this environment, without opening or changing it."""
    if client != "cursor":
        raise ValueError("Install links require --client cursor.")
    # Cursor's install-link schema uses the named server object without mcpServers.
    config = json.loads(client_config(client, store))["mcpServers"]
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = quote(base64.b64encode(payload).decode("ascii"), safe="")
    return f"cursor://anysphere.cursor-deeplink/mcp/install?name=tomc&config={encoded}\n"


def _join(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def config_path(client: str, home: Path | None = None) -> Path | None:
    """The user-level configuration file a client reads, or None when it has no fixed file."""
    client = canonical(client)
    home = Path.home() if home is None else Path(home)
    if client == "claude":
        if sys.platform == "darwin":
            folder = home / "Library/Application Support/Claude"
        elif os.name == "nt":
            folder = Path(os.environ.get("APPDATA") or home / "AppData/Roaming") / "Claude"
        else:
            folder = home / ".config/Claude"
        return folder / "claude_desktop_config.json"
    return {
        "claude-code": home / ".claude.json",
        "cursor": home / ".cursor/mcp.json",
        "workbuddy": home / ".workbuddy/mcp.json",
        "codex": home / ".codex/config.toml",
    }.get(client)


def tool_count() -> int:
    from .mcp_server import TOOL_NAMES

    return len(TOOL_NAMES)


def next_step(client: str) -> str:
    client = canonical(client)
    name = NAMES.get(client, client)
    if client in ("codex", "claude-code"):
        restart = f"start a new {name} session"
        check = "run /mcp and check" if client == "claude-code" else "check"
    else:
        restart, check = f"restart {name}", "check"
    return (
        f"Next: {restart}, {check} that the tomc server shows {tool_count()} tools, then say "
        '"Try TOMC Memory" (or "试一下 TOMC Memory").'
    )


def _write_atomic(path: Path, text: str) -> None:
    """Replace a file in one step; an existing file keeps its permissions, a new one is 0600."""
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.tomc-backup-{stamp}")
    counter = 1
    while backup.exists():
        counter += 1
        backup = path.with_name(f"{path.name}.tomc-backup-{stamp}-{counter}")
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)  # Client files can hold tokens; keep the copy owner-only.
    return backup


def _merged_json(path: Path, entry: dict) -> str | None:
    """The file's text with mcpServers.tomc set, or None when it is already set."""
    data = {}
    if path.exists():
        raw = path.read_text(encoding="utf-8-sig")
        if raw.strip():
            try:
                data = json.loads(raw)
            except ValueError as exc:
                raise ValueError(
                    f"{path} is not valid JSON; fix it or move it aside, then rerun."
                ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object; nothing was changed.")
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"mcpServers in {path} is not an object; nothing was changed.")
    if servers.get("tomc") == entry:
        return None
    servers["tomc"] = entry
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _merged_toml(path: Path, command: str, args: list[str]) -> str | None:
    """Codex config.toml with [mcp_servers.tomc] set; other tables are kept as written."""
    raw = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    try:
        import tomlkit
    except ImportError:
        tomlkit = None
    if tomlkit is None:
        if "[mcp_servers.tomc]" in raw:
            raise ValueError(
                f"{path} already has [mcp_servers.tomc]. Install tomlkit "
                "(python -m pip install tomlkit) so TOMC Memory can update it, or edit it by hand."
            )
        block = f"[mcp_servers.tomc]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
        return (
            raw + ("\n" if raw and not raw.endswith("\n") else "") + ("\n" if raw else "") + block
        )
    document = tomlkit.parse(raw)
    servers = document.get("mcp_servers")
    current = servers.get("tomc") if servers is not None else None
    if current is not None and current.get("command") == command and current.get("args") == args:
        return None
    if servers is None:
        servers = tomlkit.table(is_super_table=True)
        document["mcp_servers"] = servers
    table = tomlkit.table()
    table["command"] = command
    table["args"] = args
    if current is not None:
        for key, value in current.items():
            if key not in ("command", "args"):
                table[key] = value
    servers["tomc"] = table
    return tomlkit.dumps(document)


def write_config(
    client: str, store: Path | None = None, target: Path | None = None, home: Path | None = None
) -> dict:
    """Merge TOMC Memory into the client's file: back it up first; rerunning changes nothing."""
    client = canonical(client)
    if client in ("deepseek",):
        raise ValueError(
            "For DeepSeek Harness use: python scripts/setup_deepseek.py --output <overlay file>."
        )
    path = Path(target).expanduser().absolute() if target else config_path(client, home)
    if path is None:
        raise ValueError(
            f"{NAMES.get(client, client)} has no fixed configuration file; pass --config with "
            "the file to update (for example a project's mcp.json)."
        )
    if client == "codex":
        command, args = _launch(store)
        text = _merged_toml(path, command, args)
    else:
        text = _merged_json(path, server_entry(client, store))
    result = {"client": client, "path": str(path), "changed": text is not None, "backup": None}
    if text is not None:
        if path.exists():
            result["backup"] = str(_backup(path))
        _write_atomic(path, text)
    result["next_step"] = next_step(client)
    return result
