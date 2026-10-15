# Configure TOMC in Cursor or TRAE

[中文](cursor_trae_zh.md) · [Assistant setup](assistant_setup.md) · [Validation record](validation.md)

Use TOMC's local stdio MCP server with either client. Earlier checks cover the TOMC backend and Cursor configuration generation; **Cursor and TRAE GUI installation and model-selected tool calls remain unverified**. This update adds configuration guidance, not a new client test.

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

Merge `mcpServers.tomc` into the project's `.cursor/mcp.json` or your personal `~/.cursor/mcp.json`, preserving existing servers. Restart Cursor and check **Customize → MCPs** for the `tomc` server and its five tools. [Official MCP configuration](https://cursor.com/docs/mcp).

For an existing Python environment installed from current TOMC source with `.[mcp]`, the alternative `python -m tomc setup --client cursor --link` prints an [Add to Cursor link](https://cursor.com/docs/mcp/install-links). It registers that environment; it does not install TOMC or dependencies on another computer.

## TRAE

In the international client, open **Settings → MCP**, choose the local runtime where a local/cloud choice appears, and add the template through manual JSON configuration. A project configuration uses `.trae/mcp.json`; first enable project MCP in Settings → MCP. Preserve other server entries. Official references: [international manual/project configuration](https://docs.trae.ai/ide/add-mcp-servers?_lang=en) and [Chinese configuration](https://docs.trae.cn/ide_add-mcp-servers). Menu labels can vary by client edition/version.

With `.[mcp]` installed from current TOMC source, `python -m tomc setup --client trae` prints an alternative JSON configuration using that environment's absolute Python path. The `trae` alias is an addition to current source; older ZIP/MCPB previews may not contain it. If this option is unavailable, update the source checkout or use the UV template above. A Python executable path containing spaces conflicts with TRAE's documented command restriction; use the UV template with `uv` on PATH instead. `--link` remains Cursor-only.

## Notebooks and feedback

Notebooks default to local plaintext SQLite at `~/.tomc/memory.sqlite3`. To choose a different file, add `env` alongside `command` and `args`:

```json
{
  "env": {"TOMC_MEMORY_PATH": "/absolute/path/to/tomc-memory.sqlite3"}
}
```

Clients sharing that path share explicitly saved notes. TOMC does not collect other chats or provide cloud synchronization. The five tools are `prepare_context`, `remember_memory`, `recall_memory`, `list_memories` and `forget_memory`; storage and deletion require explicit requests. Returned memory enters the host assistant's context and follows its data policy. A tool call does not remove history already held by the host.

Please report setup feedback through [GitHub issues](https://github.com/ZipengWu365/TOMC/issues), including the client/edition, version, OS, configuration route and error message. Omit API keys, private history and notebook contents.
