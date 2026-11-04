"""`tomc doctor`: check this installation end to end and say how to fix what fails.

The server check starts a real MCP server with a temporary database, so it never
touches the user's notebooks or statistics.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from importlib.util import find_spec
from pathlib import Path

from .setup import NAMES, config_path
from .store import default_store_path

PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
SAMPLE = "framework = Flask\nbackup_framework copies framework\nframework = FastAPI"


def probe_server(command: list[str], env: dict | None = None, timeout: float = 60.0) -> dict:
    """Start an MCP stdio server, list its tools and run one tiny prepare_context.

    Plain JSON-RPC lines, so it works without the MCP client library.
    """
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    lines: queue.Queue = queue.Queue()
    errors: list[bytes] = []

    def pump():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()
    threading.Thread(target=lambda: errors.extend(process.stderr), daemon=True).start()
    deadline = time.monotonic() + timeout

    def send(message):
        process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        process.stdin.flush()

    def receive(identifier):
        while True:
            try:
                line = lines.get(timeout=max(0.1, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError(f"no answer within {timeout:.0f} s") from None
            if line is None:
                raise RuntimeError("the server stopped: " + _last_error(errors))
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == identifier:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "error"))
                return message["result"]

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "tomc-doctor", "version": "1"},
                },
            }
        )
        receive(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = [tool["name"] for tool in receive(2)["tools"]]
        seconds = time.perf_counter() - started
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "prepare_context",
                    "arguments": {"history": SAMPLE, "task": "What is the current framework?"},
                },
            }
        )
        call = receive(3)
        text = "".join(part.get("text", "") for part in call.get("content", []))
        return {
            "tools": tools,
            "seconds": seconds,
            "prepare_ok": not call.get("isError") and "FastAPI" in text,
            "prepare_text": text,
        }
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _last_error(errors: list[bytes]) -> str:
    text = b"".join(errors).decode("utf-8", "replace").strip().splitlines()
    return text[-1] if text else "no error output"


def _writable(path: Path) -> bool:
    """Whether TOMC Memory could create or update the database, without creating it."""
    if path.exists():
        return os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)
    folder = path.parent
    while not folder.exists() and folder != folder.parent:
        folder = folder.parent
    return folder.is_dir() and os.access(folder, os.W_OK | os.X_OK)


def _configured(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return False
    if path.suffix == ".toml":
        return "[mcp_servers.tomc]" in text
    try:
        servers = json.loads(text).get("mcpServers", {})
    except (ValueError, AttributeError):
        return False
    return isinstance(servers, dict) and "tomc" in servers


def check(store: Path | None = None, home: Path | None = None, timeout: float = 60.0) -> list[dict]:
    """Each result: ok (True, False, or None for optional), message and an optional fix."""
    results = []

    def add(ok, message, fix=None, optional=False):
        results.append({"ok": ok, "optional": optional, "message": message, "fix": fix})

    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info >= (3, 10):
        add(True, f"Python {version}")
    else:
        add(
            False,
            f"Python {version} is too old; TOMC Memory needs 3.10 or newer",
            "Install Python 3.12 (python.org, `brew install python@3.12` or "
            "`uv python install 3.12`), then rerun with it.",
        )
    has_mcp = find_spec("mcp") is not None
    if has_mcp:
        add(True, "MCP support installed")
    else:
        add(
            False,
            "MCP support is not installed in this Python",
            f"{sys.executable} -m pip install 'tomc-memory[mcp]' (from a checkout: "
            f"-e '.[mcp]'; in mainland China add -i {PIP_MIRROR})",
        )
    database = Path(store).expanduser().absolute() if store else default_store_path()
    if _writable(database):
        add(True, f"Memory database writable: {database}")
    else:
        add(
            False,
            f"Cannot write the memory database: {database}",
            "Fix the folder's permissions, or set TOMC_MEMORY_PATH to a writable file.",
        )
    uv = shutil.which("uv")
    if uv:
        add(True, f"uv found: {uv}", optional=True)
    else:
        add(
            False,
            "uv not found (needed only for the Claude Code and Codex plugins and the Claude "
            "Desktop bundle)",
            f"python3 -m pip install uv   (mainland China: python3 -m pip install uv -i "
            f"{PIP_MIRROR})",
            optional=True,
        )
    if has_mcp:
        with tempfile.TemporaryDirectory(prefix="tomc-doctor-") as folder:
            env = dict(os.environ)
            package_root = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = os.pathsep.join(
                [package_root, *filter(None, [env.get("PYTHONPATH")])]
            )
            command = [
                sys.executable,
                "-m",
                "tomc",
                "mcp",
                "--store",
                str(Path(folder) / "doctor.sqlite3"),
            ]
            try:
                probe = probe_server(command, env=env, timeout=timeout)
            except (RuntimeError, TimeoutError) as exc:
                add(
                    False,
                    f"The MCP server did not start: {exc}",
                    f"Run `{sys.executable} -m tomc mcp` to see the full error.",
                )
            else:
                add(
                    True,
                    f"MCP server started in {probe['seconds']:.1f} s with "
                    f"{len(probe['tools'])} tools",
                )
                if probe["prepare_ok"]:
                    add(True, "prepare_context works on a 3-line sample")
                else:
                    add(
                        False,
                        "prepare_context did not return the expected result",
                        "Reinstall TOMC Memory; then report the output of `tomc doctor`.",
                    )
    clients = [name for client, name in NAMES.items() if _configured(config_path(client, home))]
    if clients:
        add(True, "Set up in: " + ", ".join(clients), optional=True)
    else:
        add(
            False,
            "No assistant is set up yet",
            "tomc setup --client <claude-desktop|claude-code|cursor|codex|workbuddy> --write",
            optional=True,
        )
    return results


def render(results: list[dict]) -> str:
    lines = []
    for result in results:
        mark = "✓" if result["ok"] else "✗"
        optional = " (optional)" if result["optional"] and not result["ok"] else ""
        lines.append(f"{mark} {result['message']}{optional}")
        if result["fix"] and not result["ok"]:
            lines.append(f"    fix: {result['fix']}")
    failed = [r for r in results if not r["ok"] and not r["optional"]]
    lines.append(
        'All required checks passed. Next: say "Try TOMC Memory" in your assistant, or run '
        "`tomc try` here."
        if not failed
        else f"{len(failed)} required check{'s' if len(failed) != 1 else ''} failed."
    )
    return "\n".join(lines) + "\n"


def passed(results: list[dict]) -> bool:
    return all(result["ok"] or result["optional"] for result in results)
