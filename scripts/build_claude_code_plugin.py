"""Write the self-contained Claude Code plugin folder (plugins/claude-code) from tracked sources.

Claude Code copies only the plugin folder into its cache, so the folder carries the same locked
runtime as the MCPB: the plugins/claude template, the root LICENSE and the allowlisted core source.
The marketplace at .claude-plugin/marketplace.json points to this folder.

    python scripts/build_claude_code_plugin.py          # rewrite plugins/claude-code
    python scripts/build_claude_code_plugin.py --check  # fail if the folder is out of date
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "plugins" / "claude"
OUT = ROOT / "plugins" / "claude-code"
DESCRIPTION = (
    "Prepare task-specific context from supplied history on CPU, with optional local notebooks, "
    "for your existing assistant."
)
PLUGIN = {
    "name": "tomc-memory",
    # Same version as the MCPB; bump it for each release so installed copies update.
    "version": json.loads((TEMPLATE / "manifest.json").read_text(encoding="utf-8"))["version"],
    "description": DESCRIPTION,
    "author": {"name": "Zipeng Wu"},
    "homepage": "https://github.com/ZipengWu365/TOMC",
    "repository": "https://github.com/ZipengWu365/TOMC",
    "license": "MIT",
    "keywords": ["context", "compression", "memory", "cpu", "mcp"],
}
MCP = {
    "mcpServers": {
        "tomc": {
            "command": "uv",
            "args": ["run", "--locked", "--directory", "${CLAUDE_PLUGIN_ROOT}", "src/server.py"],
        }
    }
}
README = """# TOMC for Claude Code

TOMC prepares task-specific context from history that you supply. Give it a history, the next task and an optional memory budget. It selects source text and computes supported state, relation or count records on your CPU, then returns plain text for Claude to use. It needs no extra model, API key or GPU.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH, then run in Claude Code:

```
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

Start a new session and run `/mcp` to check that the `tomc` server is connected. Claude Code asks for permission the first time each tool is used.

## Host-managed conversations

The host owns active-chat compaction when enabled or unknown. Do not proactively use TOMC to recompact that same chat. Prepare separately supplied external material or explicitly saved notebooks instead. This is an assistant workflow policy, not an internal compaction detector or automatic request hook. See [context ownership](https://github.com/ZipengWu365/TOMC/blob/main/docs/context_ownership.md).

## Tools

- `prepare_context`: prepare supplied history for the next task. Successful prepared context and its task are saved to the local library by default; recording can be disabled independently. Omit `budget` to keep 60-80% of the history (80% when short, 60% from a million estimated tokens; at least 1,024).
- `get_status`, `list_contexts`, `get_context`, `make_handoff`: inspect configuration, browse saved context, and create a self-contained continuation prompt without sending it.
- `get_usage_stats`: view local cumulative estimated context reduction (`all`, `today`, or `7d`, UTC). Preparation and recall return a per-call summary for the assistant to display. These are context-text estimates, not API or billing savings; repeated preparations count separately.
- `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`: optional named notebooks for reusing supplied notes in later sessions.

For a long history, import it into a notebook from a file and call `recall_memory`, instead of pasting it into the chat: a tool call cannot shrink history the session already holds. Usage tips and measured results are in the [project README](https://github.com/ZipengWu365/TOMC).

## What it runs, stores and fetches

- **Runs:** the MCP server `src/server.py` in this folder, started with `uv run --locked`. On first start, uv downloads a compatible Python if needed and the locked `mcp` dependency from PyPI; later starts reuse them.
- **Stores:** local plaintext SQLite in `~/.tomc/memory.sqlite3` (or `TOMC_MEMORY_PATH`). Named notebooks are saved only when requested. Successful preparation/recall saves prepared context and its task to the context library by default. Short input can remain intact; this is not an anonymizer. The cat's context window controls processing, recording, per-session settings, portable export/import and snapshot deletion. Separate numeric statistics survive snapshot or notebook deletion and uninstall. Use `forget_memory` for a named notebook.
- **Sends:** nothing. The server makes no network requests and sees only the arguments Claude passes to its tools. Returned memory enters Claude's context like any other tool result.

Optional metadata-only session hooks register startup/activity and enforce per-session pause before TOMC preparation tools. They do not read transcripts, replace full model requests, or guarantee detection of a pure UI tab switch. Existing chats need to load the new integration; hook trust remains under the host's control. No billed savings have been measured by this integration.

## License

MIT; see [LICENSE](LICENSE). Third-party dependencies keep their own licenses.
"""


def expected() -> dict[str, bytes]:
    files = {
        ".claude-plugin/plugin.json": (json.dumps(PLUGIN, indent=2) + "\n").encode(),
        ".mcp.json": (json.dumps(MCP, indent=2) + "\n").encode(),
        "README.md": README.encode(),
        "LICENSE": (ROOT / "LICENSE").read_bytes(),
        "pyproject.toml": (TEMPLATE / "pyproject.toml").read_bytes(),
        "uv.lock": (TEMPLATE / "uv.lock").read_bytes(),
        "src/server.py": (TEMPLATE / "src/server.py").read_bytes(),
    }
    core = ROOT / "src" / "tomc"
    for path in sorted(core.rglob("*")):
        if (
            path.suffix == ".py"
            or (path.suffix == ".json" and path.parent == core / "data")
            or (
                path.parent == core / "data"
                and path.name in {f"tomc-expression-{i}.png" for i in range(1, 5)}
            )
        ):
            files["src/tomc/" + path.relative_to(core).as_posix()] = path.read_bytes()
    return files


def main() -> None:
    check = "--check" in sys.argv
    want = expected()
    have = (
        {
            p.relative_to(OUT).as_posix(): p.read_bytes()
            for p in OUT.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and ".venv" not in p.parts
        }
        if OUT.exists()
        else {}
    )
    stale = sorted(set(want) ^ set(have) | {k for k in want if k in have and want[k] != have[k]})
    if check:
        if stale:
            sys.exit(
                f"plugins/claude-code is out of date ({len(stale)} files); run python {Path(__file__).name}"
            )
        print(f"Claude Code plugin checked: {len(want)} files")
        return
    for name in set(have) - set(want):
        (OUT / name).unlink()
    for name, data in want.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(f"Claude Code plugin written: {len(want)} files ({len(stale)} changed)")


if __name__ == "__main__":
    main()
