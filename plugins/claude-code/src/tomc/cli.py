"""Command-line entry point; compilation never calls a reader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import STRATEGIES, compile_memory
from .easy import prepare_context

TTY_HINT = (
    "This starts the MCP server for an assistant, which talks to it over stdin. "
    "To set one up run `tomc setup`; to try TOMC Memory here run `tomc try`.\n"
)
OLD_PYTHON = (
    "TOMC Memory needs Python 3.10 or newer; this is Python {version}. Install Python 3.12 "
    "(python.org, `brew install python@3.12` or `uv python install 3.12`) and rerun with it, "
    "for example `python3.12 -m tomc {command}`.\n"
)


def main(argv: list[str] | None = None) -> int:
    """Compile text or JSON input and write a complete JSON audit result."""
    parser = argparse.ArgumentParser(
        prog="tomc", description="Offline task-oriented memory compiler"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    comp = commands.add_parser("compile", help="Compile a conversation JSON or plain-text file")
    comp.add_argument("conversation", type=Path)
    comp.add_argument("--query", required=True)
    comp.add_argument("--strategy", choices=STRATEGIES, default="tomc_raw")
    comp.add_argument("--budget", type=int, default=4096)
    comp.add_argument("--output", type=Path)
    comp.add_argument("--tokenizer", default="regex")
    comp.add_argument("--input-price-per-million", type=float)
    easy = commands.add_parser(
        "prepare", help="Make a ready-to-paste prompt; chooses the method automatically"
    )
    easy.add_argument("conversation", help="Text, JSON or JSONL file; use - for stdin")
    easy.add_argument("--task", required=True)
    easy.add_argument(
        "--budget",
        type=int,
        default=None,
        help="Memory budget in estimated tokens; default keeps 80%% of a short history, "
        "falling to 60%% from a million tokens (at least 1,024)",
    )
    easy.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Keep the memory within this many characters, for an agent that reads the "
        "output as one tool result (for example 20000 in Codex)",
    )
    easy.add_argument("--output", type=Path)
    easy.add_argument(
        "--messages", action="store_true", help="Output provider-neutral messages JSON"
    )
    mcp = commands.add_parser("mcp", help="Run the optional local MCP memory tools over stdio")
    mcp.add_argument("--store", type=Path)
    trial = commands.add_parser(
        "try", help="Try TOMC Memory on a built-in sample; nothing is saved"
    )
    trial.add_argument(
        "--language", choices=("en", "zh"), help="Card language (default: terminal locale)"
    )
    trial.add_argument("--json", action="store_true", help="Print the full result as JSON")
    doctor = commands.add_parser(
        "doctor", help="Check Python, MCP support, the database and a live server start"
    )
    doctor.add_argument("--store", type=Path)
    doctor.add_argument("--json", action="store_true", help="Print the checks as JSON")
    switch = {"on": True, "off": False}
    settings = commands.add_parser(
        "settings", help="Show or change TOMC Memory's saving and retention settings"
    )
    settings.add_argument("--store", type=Path)
    settings.add_argument(
        "--save-mcp-results",
        choices=switch,
        help="Save prepare_context/recall_memory results to the context library (default off)",
    )
    settings.add_argument(
        "--save-contexts",
        choices=switch,
        help="The 'Save context records' switch, also used by the request gateway",
    )
    settings.add_argument(
        "--retention-days", type=int, help="Days saved contexts are kept (default 30)"
    )
    erase = commands.add_parser(
        "erase-all", help="Delete all saved notebooks, contexts and conversation records"
    )
    erase.add_argument("--store", type=Path)
    erase.add_argument("--yes", action="store_true", help="Confirm; nothing is deleted without it")
    direct = commands.add_parser(
        "restore-direct",
        help="Point Codex and Claude Code back at their providers; works with TOMC Memory stopped",
    )
    direct.add_argument("--home", type=Path, default=None, help=argparse.SUPPRESS)
    from .setup import CLIENTS

    setup = commands.add_parser(
        "setup", help="Print client configuration, or add it to the client with --write"
    )
    setup.add_argument(
        "--client",
        choices=CLIENTS,
        default="json",
        help="claude means Claude Desktop (same as claude-desktop)",
    )
    setup.add_argument("--store", type=Path)
    setup.add_argument(
        "--link", action="store_true", help="Print a Cursor install link; requires --client cursor"
    )
    setup.add_argument(
        "--write",
        action="store_true",
        help="Add TOMC Memory to the client's configuration file (backed up first)",
    )
    setup.add_argument(
        "--config", type=Path, help="With --write: the configuration file to update instead"
    )
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.exit(
            2,
            OLD_PYTHON.format(
                version=".".join(map(str, sys.version_info[:3])), command=args.command
            ),
        )
    if args.command == "setup" and args.link and args.client != "cursor":
        parser.error(
            "--link requires --client cursor; other clients use their configuration output."
        )
    if args.command == "setup" and args.link and args.write:
        parser.error("Choose either --link or --write.")
    if args.command == "setup" and args.config and not args.write:
        parser.error("--config is used with --write.")
    try:
        if args.command == "mcp":
            if sys.stdin is not None and sys.stdin.isatty():
                # A person ran this in a terminal; an assistant would connect through a pipe.
                sys.stderr.write(TTY_HINT)
                return 0
            try:
                from .mcp_server import serve

                serve(args.store)
            except ImportError:
                parser.exit(
                    2,
                    "Install MCP support first: python -m pip install -e '.[mcp]' (from the TOMC checkout).\n",
                )
            return 0
        if args.command == "restore-direct":
            from .direct_connection import restore_direct

            sys.stdout.write(json.dumps(restore_direct(args.home), indent=2) + "\n")
            return 0
        if args.command in ("settings", "erase-all"):
            from .privacy import erase_all
            from .session_store import SessionStore
            from .store import default_store_path

            path = Path(args.store).expanduser() if args.store else default_store_path()
            if args.command == "erase-all":
                if not args.yes:
                    parser.exit(
                        2, "Nothing was deleted. Add --yes to erase all TOMC Memory data.\n"
                    )
                result = erase_all(path)
            else:
                if args.retention_days is not None and not 1 <= args.retention_days <= 3650:
                    parser.error("--retention-days must be from 1 to 3650.")
                result = SessionStore(path).update_settings(
                    save_contexts=switch.get(args.save_contexts),
                    save_mcp_results=switch.get(args.save_mcp_results),
                    retention_days=args.retention_days,
                )
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
            return 0
        if args.command == "try":
            from .tryout import run_sample, system_language

            result = run_sample(args.language or system_language())
            sys.stdout.write(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
                if args.json
                else result["card"] + "\n"
            )
            return 0
        if args.command == "doctor":
            from .doctor import check, passed, render

            results = check(args.store)
            sys.stdout.write(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n"
                if args.json
                else render(results)
            )
            return 0 if passed(results) else 1
        if args.command == "setup" and args.write:
            from importlib.util import find_spec

            from .setup import write_config

            try:
                result = write_config(args.client, args.store, args.config)
            except ValueError as exc:
                parser.exit(2, f"tomc setup: {exc}\n")
            if result["changed"]:
                backup = f" (backup: {result['backup']})" if result["backup"] else ""
                sys.stdout.write(f"Added TOMC Memory to {result['path']}{backup}.\n")
            else:
                sys.stdout.write(f"TOMC Memory is already set up in {result['path']}.\n")
            if find_spec("mcp") is None:
                sys.stdout.write(
                    "MCP support is not installed in this Python yet: "
                    f"{sys.executable} -m pip install 'tomc-memory[mcp]'\n"
                )
            sys.stdout.write(result["next_step"] + "\n")
            return 0
        if args.command == "setup":
            from .setup import client_config, client_link

            render = client_link if args.link else client_config
            try:
                configuration = render(args.client, args.store)
            except ValueError as exc:
                parser.error(str(exc))
            sys.stdout.write(configuration)
            return 0
        if args.command == "prepare":
            source = (
                sys.stdin.read()
                if args.conversation == "-"
                else Path(args.conversation).read_text(encoding="utf-8")
            )
            if args.conversation != "-" and Path(args.conversation).suffix.lower() == ".json":
                source = json.loads(source)
            prepared = prepare_context(source, args.task, args.budget, max_chars=args.max_chars)
            if not prepared.prompt:
                raise ValueError("No complete record fits. Increase --budget.")
            payload = (
                json.dumps(prepared.messages, ensure_ascii=False, indent=2)
                if args.messages
                else prepared.prompt
            )
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(payload + "\n", encoding="utf-8")
            else:
                sys.stdout.write(payload + "\n")
            return 0
        source = args.conversation.read_text(encoding="utf-8")
        if args.conversation.suffix.lower() == ".json":
            source = json.loads(source)
            if isinstance(source, dict):
                source = source["messages"]
        result = compile_memory(
            source,
            args.query,
            args.budget,
            args.strategy,
            tokenizer=args.tokenizer,
            input_price_per_million=args.input_price_per_million,
        )
        payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        parser.exit(
            2,
            f"tomc: {type(exc).__name__}: invalid input or unavailable tokenizer; "
            "check the file, text-message schema, budget, and installation.\n",
        )
    return 0
