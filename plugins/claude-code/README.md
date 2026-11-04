# TOMC for Claude Code

TOMC prepares task-specific context from history that you supply. Give it a history, the next task and an optional memory budget. It selects source text and computes supported state, relation or count records on your CPU, then returns plain text for Claude to use. It needs no extra model, API key or GPU.

## Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH, then run in Claude Code:

```
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

Start a new session and run `/mcp` to check that the `tomc` server is connected with twelve tools. Claude Code asks for permission the first time each tool is used.

Then type `/tomc-memory:try` or say **Try TOMC Memory** (试一下 TOMC Memory). It runs a built-in sample, shows real before/after numbers and saves nothing.

## Host-managed conversations

The host owns active-chat compaction when enabled or unknown. Do not proactively use TOMC to recompact that same chat. Prepare separately supplied external material or explicitly saved notebooks instead. This is an assistant workflow policy, not an internal compaction detector or automatic request hook. See [context ownership](https://github.com/ZipengWu365/TOMC/blob/main/docs/context_ownership.md).

## Tools

- `try_tomc`: run a built-in 120-day sample project chat and show what TOMC finds; saves nothing.
- `prepare_context`: prepare supplied history for the next task. Nothing is saved unless you turn on saving MCP results (`tomc settings --save-mcp-results on`). When a later line may have changed a value, the record is marked `STATE?` and that line is included. Omit `budget` to keep 60-80% of the history (80% when short, 60% from a million estimated tokens; at least 1,024). Each result fits one tool output (about 50,000 characters in Claude Code, 20,000 elsewhere; `TOMC_MCP_MAX_CHARS` overrides). On a repeat call for the same source in the same chat, pass the previous `delivery.id` as `since_delivery_id` to receive only what changed.
- `get_status`, `list_contexts`, `get_context`, `make_handoff`: inspect configuration, browse saved context, and create a self-contained continuation prompt without sending it.
- `get_usage_stats`: view local cumulative estimated context reduction (`all`, `today`, or `7d`, UTC). Preparation and recall return a per-call summary for the assistant to display. These are context-text estimates, not API or billing savings; repeated preparations count separately.
- `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`: optional named notebooks for reusing supplied notes in later sessions. `forget_memory` also deletes contexts prepared from that notebook.
- `erase_all_memory`: delete all TOMC Memory data on this computer; requires `confirm="ERASE ALL"`.

Every result starts with a one-line `summary`; diagnostics are under `details`.

For a long history, import it into a notebook from a file and call `recall_memory`, instead of pasting it into the chat: a tool call cannot shrink history the session already holds. Usage tips and measured results are in the [project README](https://github.com/ZipengWu365/TOMC).

## What it runs, stores and fetches

- **Runs:** the MCP server `src/server.py` in this folder, started with `uv run --locked`. On first start, uv downloads a compatible Python if needed and the locked `mcp` dependency from PyPI; later starts reuse them.
- **Stores:** local plaintext SQLite in `~/.tomc/memory.sqlite3` (or `TOMC_MEMORY_PATH`). Named notebooks are saved only when requested. Prepared context from `prepare_context` / `recall_memory` is saved only when both Save context records and Save MCP results are on (the second is off by default); saved contexts have common secrets replaced with `[REDACTED]` and are deleted after 30 days. Redaction is a pattern pass, not an anonymizer. The cat's context window controls processing, recording, per-session settings, portable export/import and snapshot deletion. Separate numeric statistics survive snapshot or notebook deletion and uninstall. Use `forget_memory` for a named notebook, or `erase_all_memory` / `tomc erase-all --yes` for everything. The server exits when Claude Code closes the connection.
- **Sends:** nothing. The server makes no network requests and sees only the arguments Claude passes to its tools. Returned memory enters Claude's context like any other tool result.

Optional metadata-only session hooks register startup/activity and enforce per-session pause before TOMC preparation tools. They do not read transcripts, replace full model requests, or guarantee detection of a pure UI tab switch. Existing chats need to load the new integration; hook trust remains under the host's control. No billed savings have been measured by this integration.

## License

MIT; see [LICENSE](LICENSE). Third-party dependencies keep their own licenses.
