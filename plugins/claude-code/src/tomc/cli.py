"""Command-line entry point; compilation never calls a reader."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import STRATEGIES, compile_memory
from .easy import prepare_context


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
        help="Memory budget in estimated tokens; default keeps about 80%% of the history (at least 1,024)",
    )
    easy.add_argument("--output", type=Path)
    easy.add_argument(
        "--messages", action="store_true", help="Output provider-neutral messages JSON"
    )
    mcp = commands.add_parser("mcp", help="Run the optional local MCP memory tools over stdio")
    mcp.add_argument("--store", type=Path)
    setup = commands.add_parser("setup", help="Print client configuration for this installation")
    setup.add_argument("--client", choices=("codex", "cursor", "claude", "json"), default="json")
    setup.add_argument("--store", type=Path)
    setup.add_argument(
        "--link", action="store_true", help="Print a Cursor install link; requires --client cursor"
    )
    args = parser.parse_args(argv)
    if args.command == "setup" and args.link and args.client != "cursor":
        parser.error(
            "--link requires --client cursor; other clients use their configuration output."
        )
    try:
        if args.command == "mcp":
            try:
                from .mcp_server import serve

                serve(args.store)
            except ImportError:
                parser.exit(
                    2,
                    "Install MCP support first: python -m pip install -e '.[mcp]' (from the TOMC checkout).\n",
                )
            return 0
        if args.command == "setup":
            from .setup import client_config, client_link

            render = client_link if args.link else client_config
            sys.stdout.write(render(args.client, args.store))
            return 0
        if args.command == "prepare":
            source = (
                sys.stdin.read()
                if args.conversation == "-"
                else Path(args.conversation).read_text(encoding="utf-8")
            )
            if args.conversation != "-" and Path(args.conversation).suffix.lower() == ".json":
                source = json.loads(source)
            prepared = prepare_context(source, args.task, args.budget)
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
