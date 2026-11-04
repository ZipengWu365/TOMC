"""Configure this extracted TOMC Memory package and install it with the Codex CLI.

Runs on any Python 3, including the Python 3.9 that ships with macOS: uv supplies
the Python 3.12 that TOMC Memory itself runs on.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# The installer and the server use the same Python, so uv downloads only one.
RUNTIME_PYTHON = "3.12"
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
PYTHON_MIRROR = "https://registry.npmmirror.com/-/binary/python-build-standalone"
UV_GUIDE = "https://docs.astral.sh/uv/getting-started/installation/"
FIRST_START_SECONDS = 300


class Problem(ValueError):
    """A missing prerequisite, with the commands that fix it."""

    def __init__(self, message: str, fix: str = ""):
        super().__init__(message)
        self.fix = fix


def uv_fix() -> str:
    python = "py" if os.name == "nt" else "python3"
    if os.name == "nt":
        mirror = (
            f'    $env:UV_DEFAULT_INDEX="{PIP_MIRROR}"\n'
            f'    $env:UV_PYTHON_INSTALL_MIRROR="{PYTHON_MIRROR}"\n'
        )
    else:
        mirror = (
            f"    export UV_DEFAULT_INDEX={PIP_MIRROR}\n"
            f"    export UV_PYTHON_INSTALL_MIRROR={PYTHON_MIRROR}\n"
        )
    return (
        "Install uv with one of these, then rerun this installer:\n"
        + ("" if os.name == "nt" else "    curl -LsSf https://astral.sh/uv/install.sh | sh\n")
        + f"    {python} -m pip install --user uv\n"
        + "  In mainland China, use mirrors for uv, Python and packages:\n"
        + f"    {python} -m pip install --user uv -i {PIP_MIRROR}\n"
        + mirror
        + "  If uv is not on PATH afterwards, run the installer as\n"
        + f"    {python} -m uv run --no-project --python {RUNTIME_PYTHON} install.py\n"
        + f"  or pass --uv /absolute/path/to/uv. Guide: {UV_GUIDE}"
    )


CODEX_FIX = (
    "Install a current Codex CLI with plugin support (for example "
    "`npm install -g @openai/codex`), or pass --codex /absolute/path/to/codex. A desktop "
    "Codex app often bundles one. Without plugin support, use the direct MCP setup in README.md."
)


def runtime_directory(root: Path) -> Path:
    """Reject incomplete bundles before writing paths or registering a marketplace."""
    root = root.resolve()
    runtime = (root / "plugins" / "tomc-memory").resolve()
    required = [
        root / ".agents/plugins/marketplace.json",
        runtime / ".codex-plugin/plugin.json",
        runtime / "skills/tomc-memory/SKILL.md",
        *(runtime / name for name in ("src/server.py", "pyproject.toml", "uv.lock")),
    ]
    for path in required:
        if not path.is_file():
            raise Problem(
                f"Incomplete TOMC installation: missing {path.relative_to(root.resolve())}",
                "Extract the whole ZIP again into an empty folder; it contains hidden "
                "folders such as .agents.",
            )
    return runtime


def executable_path(command: str, label: str, option: str) -> str:
    """Accept a command on PATH or an explicitly supplied executable path."""
    located = shutil.which(os.path.expanduser(command))
    if not located and label == "UV" and command == "uv":
        # `python3 -m uv run install.py` puts uv's own path in UV, not on PATH.
        candidate = os.environ.get("UV", "")
        located = shutil.which(candidate) if candidate else None
    if not located:
        raise Problem(
            f"{label} executable not found or not executable: {command}. "
            f"Add it to PATH or pass {option} /absolute/path/to/executable.",
            uv_fix() if label == "UV" else CODEX_FIX,
        )
    return str(Path(located).resolve())


def check_codex(codex: str) -> None:
    """Probe the commands used by installation without registering anything."""
    for args in (("plugin", "marketplace", "add", "--help"), ("plugin", "add", "--help")):
        try:
            subprocess.run([codex, *args], check=True, capture_output=True, text=True, timeout=30)
        except subprocess.CalledProcessError as exc:
            raise Problem(
                "Codex CLI does not support the required plugin installation commands.",
                CODEX_FIX,
            ) from exc


def server_args(runtime: Path) -> list[str]:
    return [
        "run",
        "--locked",
        "--python",
        RUNTIME_PYTHON,
        "--directory",
        str(runtime),
        "src/server.py",
    ]


def configure(root: Path, uv: str, store: Path | None = None) -> dict:
    """Generate user-machine paths; never edit personal Codex configuration."""
    runtime = runtime_directory(root)
    executable = executable_path(uv, "UV", "--uv")
    config = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {
            "tomc": {
                "type": "stdio",
                "command": executable,
                "args": server_args(runtime),
                "startup_timeout_sec": 120,
            }
        },
    }
    if store is not None:
        config["mcpServers"]["tomc"]["env"] = {
            "TOMC_MEMORY_PATH": str(store.expanduser().resolve())
        }
    destination = runtime / "mcp.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return config


def list_server_tools(command: list[str], timeout: float = FIRST_START_SECONDS) -> list[str]:
    """Start the configured MCP server with a throwaway database and list its tools."""
    with tempfile.TemporaryDirectory(prefix="tomc-install-check-") as folder:
        env = {**os.environ, "TOMC_MEMORY_PATH": str(Path(folder) / "check.sqlite3")}
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
                    detail = b"".join(errors).decode("utf-8", "replace").strip().splitlines()
                    raise RuntimeError(detail[-1] if detail else "the server stopped")
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if message.get("id") == identifier:
                    return message.get("result", {})

        try:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "tomc-installer", "version": "1"},
                    },
                }
            )
            receive(1)
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            return [tool["name"] for tool in receive(2).get("tools", [])]
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


def verify(uv: str, runtime: Path) -> bool:
    print(
        "Checking that the TOMC Memory server starts. The first start downloads Python "
        f"{RUNTIME_PYTHON} and the pinned packages; this can take a minute...",
        flush=True,
    )
    try:
        tools = list_server_tools([uv, *server_args(runtime)])
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f"✗ The TOMC Memory server did not start: {exc}")
        print(
            "  If downloads are slow or blocked, set the mirrors shown below and rerun:\n"
            + "\n".join(line for line in uv_fix().splitlines() if "UV_" in line)
        )
        return False
    print(f"✓ The TOMC Memory server started with {len(tools)} tools.")
    return True


def display(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def report(problems: list[Problem]) -> None:
    print(
        "Installation stopped. Fix these first:" if len(problems) > 1 else "Installation stopped:"
    )
    for problem in problems:
        print(f"- {problem}")
        if problem.fix:
            print("  " + problem.fix.replace("\n", "\n  "))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--configure-only",
        action="store_true",
        help="Write local paths without registering in Codex.",
    )
    mode.add_argument(
        "--check", action="store_true", help="Check prerequisites without writing or installing."
    )
    parser.add_argument("--uv", default="uv", help="UV command or executable path (default: PATH).")
    parser.add_argument("--codex", help="Codex CLI command or executable path (default: PATH).")
    parser.add_argument("--store", type=Path, help="Optional separate notebook database path.")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the server start check after installation (for offline installs).",
    )
    parser.add_argument(
        "--no-support-message",
        action="store_true",
        help="Hide the optional GitHub Star invitation.",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    if sys.version_info < (3, 10):
        print(
            f"Note: this is Python {sys.version_info[0]}.{sys.version_info[1]}. That is fine for "
            f"the installer; TOMC Memory runs on Python {RUNTIME_PYTHON}, which uv provides."
        )
    try:
        runtime = runtime_directory(root)
    except Problem as problem:
        report([problem])
        return 1
    # Report every missing prerequisite at once instead of one per run.
    problems: list[Problem] = []
    uv = codex = None
    try:
        uv = executable_path(args.uv, "UV", "--uv")
    except Problem as problem:
        problems.append(problem)
    if args.codex or not args.configure_only:
        try:
            codex = executable_path(args.codex or "codex", "Codex CLI", "--codex")
        except Problem as problem:
            problems.append(problem)
    if not problems:
        try:
            subprocess.run(
                [uv, "--version"], check=True, capture_output=True, text=True, timeout=30
            )
        except (OSError, subprocess.SubprocessError) as exc:
            problems.append(Problem(f"UV did not run: {exc}", uv_fix()))
        if codex and not args.configure_only:
            try:
                check_codex(codex)
            except Problem as problem:
                problems.append(problem)
            except (OSError, subprocess.SubprocessError) as exc:
                problems.append(Problem(f"Codex CLI did not run: {exc}", CODEX_FIX))
    if problems:
        report(problems)
        return 1
    codex = codex or "codex"
    try:
        if args.check:
            print("TOMC prerequisites passed; no TOMC files or Codex settings changed.")
            print(f"UV: {uv}\nCodex CLI: {codex}")
            print(
                f"The first MCP startup still needs network access for Python {RUNTIME_PYTHON} "
                "and the pinned packages."
            )
            return 0
        commands = [
            [codex, "plugin", "marketplace", "add", str(root)],
            [codex, "plugin", "add", "tomc-memory@tomc-local"],
        ]
        configure(root, uv, args.store)
        print("TOMC runtime paths configured for this computer.", flush=True)
        if args.configure_only:
            print("To install, run:\n" + "\n".join(display(command) for command in commands))
        else:
            for command in commands:
                subprocess.run(command, check=True)
            print("TOMC Memory installed in Codex.")
            working = args.no_verify or verify(uv, runtime)
            print(
                "To uninstall, run:\n"
                + display([codex, "plugin", "remove", "tomc-memory@tomc-local"])
                + "\n"
                + display([codex, "plugin", "marketplace", "remove", "tomc-local"])
            )
            print(
                "Uninstalling leaves notebooks intact; remove only disposable test data yourself."
            )
            if not working:
                print(
                    "Keep this directory in place, fix the problem above and rerun the installer."
                )
                return 1
            print(
                'Next: start a new Codex session and say "Try TOMC Memory" '
                '(or "试一下 TOMC Memory").'
            )
            if not args.no_support_message:
                print(
                    "If TOMC helps with your work, consider a Star on GitHub: "
                    "https://github.com/ZipengWu365/TOMC (optional)."
                )
        print("Keep this directory in place. Rerun the installer after moving it.")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Installation stopped: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
