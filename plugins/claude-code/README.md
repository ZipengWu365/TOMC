# TOMC for Claude Code

TOMC prepares task-specific context from history that you supply. Give it a history, the next task and an optional memory budget. It selects source text and computes supported state, relation or count records on your CPU, then returns plain text for Claude to use. It needs no extra model, API key or GPU.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH, then run in Claude Code:

```
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

Start a new session and run `/mcp` to check that the `tomc` server is connected. Claude Code asks for permission the first time each tool is used.

## Tools

- `prepare_context`: prepare supplied history for the next task without saving it. Omit `budget` to keep about 80% of the history (at least 1,024 estimated tokens).
- `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`: optional named notebooks for reusing supplied notes in later sessions.

For a long history, import it into a notebook from a file and call `recall_memory`, instead of pasting it into the chat: a tool call cannot shrink history the session already holds. Usage tips and measured results are in the [project README](https://github.com/ZipengWu365/TOMC).

## What it runs, stores and fetches

- **Runs:** the MCP server `src/server.py` in this folder, started with `uv run --locked`. On first start, uv downloads a compatible Python if needed and the locked `mcp` dependency from PyPI; later starts reuse them.
- **Stores:** notebooks only when you call `remember_memory`, as local plaintext SQLite in `~/.tomc/memory.sqlite3` (or `TOMC_MEMORY_PATH`). Preparation itself writes nothing. Uninstalling does not delete notebooks; use `forget_memory` for a specific notebook.
- **Sends:** nothing. The server makes no network requests and sees only the arguments Claude passes to its tools. Returned memory enters Claude's context like any other tool result.

## License

MIT; see [LICENSE](LICENSE). Third-party dependencies keep their own licenses.
