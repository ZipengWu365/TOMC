"""Configure this extracted TOMC package and install it with the Codex CLI."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path


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
            raise ValueError(
                f"Incomplete TOMC installation: missing {path.relative_to(root.resolve())}"
            )
    return runtime


def executable_path(command: str, label: str, option: str) -> str:
    """Accept a command on PATH or an explicitly supplied executable path."""
    located = shutil.which(os.path.expanduser(command))
    if not located:
        hint = (
            "Install uv: https://docs.astral.sh/uv/getting-started/installation/"
            if label == "UV"
            else "Use a current Codex CLI with plugin support, or the direct MCP setup in README.md."
        )
        raise ValueError(
            f"{label} executable not found or not executable: {command}. "
            f"Add it to PATH or pass {option} /absolute/path/to/executable. {hint}"
        )
    return str(Path(located).resolve())


def check_codex(codex: str) -> None:
    """Probe the commands used by installation without registering anything."""
    for args in (("plugin", "marketplace", "add", "--help"), ("plugin", "add", "--help")):
        try:
            subprocess.run([codex, *args], check=True, capture_output=True, text=True, timeout=30)
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                "Codex CLI does not support the required plugin installation commands. "
                "Use a current Codex CLI or the direct MCP setup in README.md."
            ) from exc


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
                "args": ["run", "--locked", "--directory", str(runtime), "src/server.py"],
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


def display(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


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
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    try:
        runtime_directory(root)
        uv = executable_path(args.uv, "UV", "--uv")
        subprocess.run([uv, "--version"], check=True, capture_output=True, text=True, timeout=30)
        codex = "codex"
        if args.codex or not args.configure_only:
            codex = executable_path(args.codex or "codex", "Codex CLI", "--codex")
        if not args.configure_only:
            check_codex(codex)
        if args.check:
            print("TOMC prerequisites passed; no TOMC files or Codex settings changed.")
            print(f"UV: {uv}\nCodex CLI: {codex}")
            print("The first MCP startup still needs network access for Python and dependencies.")
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
            print("TOMC Memory installed. Start a new Codex session to use its tools.")
            print(
                "To uninstall, run:\n"
                + display([codex, "plugin", "remove", "tomc-memory@tomc-local"])
                + "\n"
                + display([codex, "plugin", "marketplace", "remove", "tomc-local"])
            )
            print(
                "Uninstalling leaves notebooks intact; remove only disposable test data yourself."
            )
        print("Keep this directory in place. Rerun the installer after moving it.")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Installation stopped: {exc}")
        print("Use a current Codex CLI with plugin commands, or the direct MCP setup in README.md.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
