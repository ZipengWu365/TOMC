# TOMC Memory 0.3.0 release notes

**English** | [简体中文](release_notes_0.3.0_zh.md) · 2026-10-30 · release tag `v0.3.0-preview.1`

0.3.0 is about trust: it saves less by default, can erase everything, keeps the latest value more reliably and is easier to try. The paper's compiler kernel is unchanged.

## What changes for you

### Privacy defaults

- **MCP results are no longer saved by default.** `prepare_context` and `recall_memory` used to save each result and its task as a local snapshot (0.2.0–0.2.1). Now they save nothing unless you opt in with `tomc settings --save-mcp-results on`; the "Save context records" switch must also be on. The response says `context_record.status = "disabled"` when nothing was saved.
- **Saved contexts hide keys.** API keys, bearer tokens, private keys, passwords in URLs and `KEY=value` secrets are replaced with `[REDACTED]` before a context is written.
- **Saved contexts expire.** They are deleted after 30 days by default (`tomc settings --retention-days N`, 1–3650). Snapshots made by 0.2.x are redacted once and pruned by age the next time the MCP server or gateway starts.
- **Recording off means nothing written.** With "Save context records" off, the Claude path of the Windows gateway keeps its replay data in memory only.
- **Owner-only files.** Databases and installer backups are created readable by you only (0600 files, 0700 folders), and deleted rows are overwritten on disk.
- The desktop companion shows a one-time privacy notice.

### Erase and restore

- `forget_memory` now also deletes the contexts prepared from that notebook.
- Erase everything: MCP tool `erase_all_memory` (needs `confirm="ERASE ALL"`), `tomc erase-all --yes`, or **Erase all records…** in the context library.
- `tomc restore-direct` points Codex and Claude Code back at their own providers. It works with TOMC Memory stopped and only removes TOMC's own keys. The same is available as `--restore-direct` on `scripts/install_request_gateway.py` and `scripts/install_windows_companion.py`, and as the Windows Start-menu shortcut **TOMC Memory - Restore direct connection**.
- Restore and uninstall no longer fail after Codex edits `config.toml`, and running them twice is safe.

### The latest value comes back more often

- When a later line may have changed a value, the record is shown as `[STATE?] key = value (later: uN)` (or `PATH?`), followed by that later line, so you or the model can check it.
- The parser reads more forms: `key: value`, list items, `Update:` and speaker prefixes, several `;`-separated assignments, full-width `＝`/`：` and Unicode keys. It skips code blocks, front matter, comparisons and hypothetical examples.
- For current-value and count questions, ties go to the later line, and part of the budget is reserved for the latest lines that mention the question's words or announce a change.
- Very long lines are split into sentence pieces (`u12.1`, `u12.2` …), so one paragraph no longer eats the budget.
- Routing fixes: "account", "discount", "country" are no longer counts; "concurrent" is not "current"; Chinese state words such as 现在、目前、改成 are recognised; "… now?" asks for the current state.
- Offline stale-value benchmark (`python benchmarks/stale/run.py`, 144 questions per budget, no model calls), share of questions whose prepared context holds the latest value:

| budget | 10% | 20% | 40% | 60% | 80% | default |
|---|---|---|---|---|---|---|
| v0.2.1 | 51% | 51% | 51% | 53% | 59% | 58% |
| v0.3.0 | 85% | 88% | 98% | 100% | 100% | 100% |

Remaining misses are reworded updates that don't name what changed, at 10–40% budgets. [Full table and caveats](evidence.md#stale-benchmark)

### Try TOMC Memory

Say **"Try TOMC Memory"** (or "试一下 TOMC Memory") in your assistant, run `/tomc-memory:try` in Claude Code, or `tomc try` in a terminal. It prepares a built-in 120-day project chat in memory and shows a short card: before and after token counts, the values it found with their line numbers, and next steps. Nothing is saved. New MCP tool `try_tomc` and MCP prompt `quickstart`; the Codex plugin offers the same as its first suggested prompt.

### `tomc doctor`

`tomc doctor` (or `--json`) checks Python, MCP support, the database, uv, a live server start with a throwaway database and the tool count, and which clients are set up. Each failed check prints a fix.

### `tomc setup --write`

`tomc setup --client <claude-desktop|claude-code|cursor|codex|workbuddy> --write` adds TOMC Memory to that client's config file. It makes a timestamped backup first, keeps your other servers and the file's permissions, and can be run again safely. Use `--config PATH` for TRAE or a project file. `--client claude-code` without `--write` prints the `claude mcp add …` command. Cursor's JSON now includes `"type": "stdio"`.

The Codex installer now reports all missing prerequisites at once, prints uv install options including a mainland China mirror, pins the runtime to Python 3.12 and starts the server once after installing to check it (`--no-verify` skips this).

### Stricter tools, clearer answers

- 12 tools: `try_tomc`, `prepare_context`, `remember_memory`, `recall_memory`, `get_status`, `list_contexts`, `get_context`, `make_handoff`, `get_usage_stats`, `list_memories`, `forget_memory`, `erase_all_memory`.
- Tool schemas are strict: `budget` must be a positive integer, host and period are fixed choices, `limit` is 1–1000, and unknown arguments are rejected.
- Every response starts with a one-line `summary`. Diagnostics moved under `details`. Short input now says "Short enough to use as is" instead of "saving 0 tokens".
- The server instructions are about half as long and no longer tell the model to skip TOMC for histories under 10,000 tokens.

### Server lifecycle

MCP servers exit when the client closes the connection or the parent process dies, so no orphaned servers are left behind. Running `tomc mcp` by hand in a terminal prints a one-line hint and exits.

## What did not change

- The paper's compiler kernel (`src/tomc/_vendor/`) is untouched. BEAM and RULER numbers are the same archived results.
- The Codex and Claude Code numbers were measured on 0.1.0 previews and were **not** re-run with a model on 0.3.0. v0.3.0 prepares different contexts, so treat them as earlier results. [Evidence](evidence.md#assistant-trials)
- The core package still needs Python 3.10+ and has no dependencies. There is still no PyPI package.
- The plugins still do not shrink the chat your assistant is already having.

## Upgrade notes

- **Old MCP snapshots.** If you used 0.2.0 or 0.2.1 through MCP, each prepare/recall result was saved. After upgrading they are redacted once and those older than 30 days are deleted. To remove them all now: `tomc erase-all --yes` (this also deletes notebooks). To keep saving new results as before: `tomc settings --save-mcp-results on`.
- **Settings.** `tomc settings` shows the current values. Change them with `--save-mcp-results on|off`, `--save-contexts on|off` and `--retention-days N`.
- **Scripts that read MCP responses.** `selected_method`, token estimates, `warnings`, `usage`, `preparation_id`, `host`, `session_id` and similar fields are now under `details`. `memory`, `status`, `context_reduction`, `context_record`, `delivery`, `budget` and `max_chars` stay at the top. Unknown arguments now raise an error.
- **Output size.** The adaptive minimum (768 tokens or 25% of the budget) is now always filled, so adaptive output can be larger than in 0.2.1. Japanese and Korean text is counted per character, which changes their budgets and reported savings.
- **Notebook names** match case-insensitively: `Proj` adds to an existing `proj`.
- **Plugins.** Claude Code: update the plugin with `/plugin` and start a new session. Codex: download the 0.3.0 ZIP and rerun its installer. Claude Desktop: install the 0.3.0 `.mcpb`. Then say "Try TOMC Memory".

## Known limits

- Updates written as ordinary prose are kept as source text, never turned into state records, and can still be lost at small budgets.
- A relation negated in prose ("Alice no longer owns repo1") is flagged `PATH?` rather than removed.
- The count tokenizer is English-only (Chinese terms named in the question are counted directly); Chinese tasks skip adaptive shrinking.
- Notebooks saved with `remember_memory` and imported bundles are stored as you wrote them, without redaction.
- The Windows gateway has no client authentication yet. See [SECURITY.md](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md#known-limits).

## Checks for this release

`python -m pytest -q`: 1109 passed, 2 skipped. `ruff check` and `ruff format --check`: clean. `make reproduce`: all offline checks pass and leave `git status` unchanged. [Reproducibility](reproducibility.md)
