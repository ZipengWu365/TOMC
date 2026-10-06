"""Print exact client configuration without modifying existing client settings."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

from .store import default_store_path


def client_config(client: str, store: Path | None = None) -> str:
    """Use this installation's absolute interpreter, preserving its virtualenv path."""
    command = os.path.abspath(sys.executable)
    args = [
        "-m",
        "tomc",
        "mcp",
        "--store",
        str((store or default_store_path()).expanduser().absolute()),
    ]
    if client == "codex":
        return f"[mcp_servers.tomc]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
    if client not in ("cursor", "claude", "json"):
        raise ValueError("Choose codex, cursor, claude, or json.")
    return json.dumps({"mcpServers": {"tomc": {"command": command, "args": args}}}, indent=2) + "\n"


def client_link(client: str, store: Path | None = None) -> str:
    """Print a Cursor install link for this environment, without opening or changing it."""
    if client != "cursor":
        raise ValueError("Install links require --client cursor.")
    # Cursor's install-link schema uses the named server object without mcpServers.
    config = json.loads(client_config(client, store))["mcpServers"]
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = quote(base64.b64encode(payload).decode("ascii"), safe="")
    return f"cursor://anysphere.cursor-deeplink/mcp/install?name=tomc&config={encoded}\n"
