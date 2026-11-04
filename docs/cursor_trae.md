# Configure TOMC in Cursor or TRAE

[中文](cursor_trae_zh.md) · [Assistant setup](assistant_setup.md) · [Validation record](validation.md)

Use TOMC's local stdio MCP server with either client. Checks so far cover the TOMC server and configuration generation. **Cursor and TRAE installation and tool calls have not yet been verified on a real machine.**

The quickest route, from a checkout with `.[mcp]` installed (Python 3.10 or newer), is `python -m tomc setup --client cursor --write` (or `--client trae --write --config <file>`), then `python -m tomc doctor`. `--write` backs the file up first, keeps your other servers and can be run again safely. The manual route below uses the locked runtime and needs no Python environment of your own.

## Use the locked runtime

Install [UV](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH. Clone the public TOMC repository:

```bash
git clone https://github.com/ZipengWu365/TOMC.git
```

The `plugins/claude-code` folder contains the shared TOMC source, `pyproject.toml`, `uv.lock` and `src/server.py`. Its runtime can also be registered as a local MCP server in other clients. No Claude Code installation or extra model API key is needed for this route. First startup can download compatible Python and locked dependencies through UV.

Before connecting, download the locked dependencies with your actual runtime directory:

```bash
uv sync --locked --directory "/absolute/path/to/TOMC/plugins/claude-code"
```

Copy the template for [Cursor](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.cursor.json) or [TRAE](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.template.json). The Cursor template explicitly sets `type` to `stdio`, as required by its current configuration reference. Replace **both** absolute-path placeholders: the runtime directory and its `src/server.py` file. Use forward slashes in Windows JSON paths, for example `C:/Tools/TOMC/plugins/claude-code`. Keep the checkout in place; update both paths after moving it. If UV is outside PATH, replace `command` with its actual executable path. TRAE's documented `command` restriction excludes spaces in that executable path; directory/script paths belong in separate `args` strings.

## Cursor

Merge `mcpServers.tomc` into the project's `.cursor/mcp.json` or your personal `~/.cursor/mcp.json`, preserving existing servers. Restart Cursor and check **Customize → MCPs** for the `tomc` server and its twelve tools, then say **Try TOMC Memory**. [Official MCP configuration](https://cursor.com/docs/mcp).

For an existing Python environment installed from TOMC source with `.[mcp]`, `python -m tomc setup --client cursor --write` merges the entry into `~/.cursor/mcp.json` (with `"type": "stdio"`), and `python -m tomc setup --client cursor --link` prints an [Add to Cursor link](https://cursor.com/docs/mcp/install-links) instead. Both register that environment; they do not install TOMC or dependencies on another computer.

## TRAE

In the international client, open **Settings → MCP**, choose the local runtime where a local/cloud choice appears, and add the template through manual JSON configuration. A project configuration uses `.trae/mcp.json`; first enable project MCP in Settings → MCP. Preserve other server entries. Official references: [international manual/project configuration](https://docs.trae.ai/ide/add-mcp-servers?_lang=en) and [Chinese configuration](https://docs.trae.cn/ide_add-mcp-servers). Menu labels can vary by client edition/version.

With `.[mcp]` installed from TOMC source, `python -m tomc setup --client trae` prints an alternative JSON configuration using that environment's absolute Python path, and `python -m tomc setup --client trae --write --config <path to the file>` merges it into TRAE's settings file or a project `.trae/mcp.json` after a backup. If this option is unavailable, update the source checkout or use the UV template above. A Python executable path containing spaces conflicts with TRAE's documented command restriction; use the UV template with `uv` on PATH instead. `--link` remains Cursor-only.

## Notebooks and feedback

Notebooks default to local plaintext SQLite at `~/.tomc/memory.sqlite3`. To choose a different file, add `env` alongside `command` and `args`:

```json
{
  "env": {"TOMC_MEMORY_PATH": "/absolute/path/to/tomc-memory.sqlite3"}
}
```

Clients sharing that path share explicitly saved notes. TOMC does not collect other chats or provide cloud synchronization. The twelve tools in 0.3.0 are `try_tomc`, `prepare_context`, `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`, `erase_all_memory`, `get_status`, `get_usage_stats`, `list_contexts`, `get_context` and `make_handoff`. Notes are stored only when you ask; `prepare_context` and `recall_memory` results are not saved unless you turn that on with `tomc settings --save-mcp-results on`. Delete with `forget_memory`, or everything with `erase_all_memory` / `tomc erase-all --yes`. Returned memory enters the host assistant's context and follows its data policy. A tool call does not remove history already held by the host.

Please report setup feedback through [GitHub issues](https://github.com/ZipengWu365/TOMC/issues), including the client/edition, version, OS, configuration route and error message. Omit API keys, private history and notebook contents.
