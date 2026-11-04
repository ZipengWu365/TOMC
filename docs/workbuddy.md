# Configure TOMC in WorkBuddy

[中文](workbuddy_zh.md) · [Assistant setup](assistant_setup.md) · [Validation record](validation.md)

This guide provides manual local MCP configuration for Tencent WorkBuddy. **WorkBuddy installation and TOMC tool calls have not yet been verified on a real machine.** Earlier TOMC server checks keep their own scope. TOMC has no Tencent official marketplace listing or endorsement.

The quickest route, from a checkout with `.[mcp]` installed (Python 3.10 or newer), is `python -m tomc setup --client workbuddy --write`, then `python -m tomc doctor`. The manual route below uses the locked runtime.

## Use the locked runtime

Install [UV](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH, then clone the public repository:

```bash
git clone https://github.com/ZipengWu365/TOMC.git
```

The repository's `plugins/claude-code` directory contains the shared TOMC source, `pyproject.toml`, `uv.lock` and `src/server.py`. WorkBuddy can launch that runtime as a local stdio server; installing Claude Code is unnecessary. First startup can download compatible Python and locked dependencies through UV. TOMC itself needs no extra model API key or GPU.

Before connecting, download the locked dependencies with your actual runtime directory:

```bash
uv sync --locked --directory "/absolute/path/to/TOMC/plugins/claude-code"
```

Copy [the WorkBuddy template](https://github.com/ZipengWu365/TOMC/blob/main/plugins/mcp/tomc.workbuddy.json) and replace **both** absolute-path placeholders: the runtime directory and its `src/server.py` file. Windows JSON paths can use forward slashes, such as `C:/Tools/TOMC/plugins/claude-code`. If UV is outside PATH, replace `command` with its actual executable path. Keep the checkout in place and update the two paths after moving it.

## Add the server

Open the sidebar **插件 → MCP 服务器 → 配置 MCP** (Plugins → MCP servers → Configure MCP), and merge `mcpServers.tomc` into the JSON while preserving other servers. The [official WorkBuddy guide](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide) also documents these file locations:

| Scope | Configuration file |
|---|---|
| Personal, across projects | `~/.workbuddy/mcp.json` |
| Current project | `<project>/.workbuddy/mcp.json` |

Here `~` means your home directory. After saving, inspect the server status; the guide uses green for a successful connection and red for a configuration or launch error. The template explicitly selects `stdio`, supported in the [official connector reference](https://open.workbuddy.cn/docs/connector).

As an alternative, install `.[mcp]` from TOMC source and run `python -m tomc setup --client workbuddy --write`. It merges the entry for that Python environment into `~/.workbuddy/mcp.json` after saving a timestamped backup, keeps other servers and changes nothing when run again; add `--config <project>/.workbuddy/mcp.json` for a project file. Without `--write` it only prints the configuration. Add `--store /absolute/path/to/tomc-memory.sqlite3` to select a database. `--link` remains Cursor-only. After restarting WorkBuddy, check for twelve tools and say **Try TOMC Memory**.

## Tools, storage and feedback

0.3.1 has twelve tools. `try_tomc` runs a built-in sample. `prepare_context` prepares supplied history; neither it nor `recall_memory` saves its result unless you run `tomc settings --save-mcp-results on`. The notebook tools are `remember_memory`, `recall_memory`, `list_memories` and `forget_memory`; `erase_all_memory` deletes everything after confirmation. The status and library tools are `get_status`, `get_usage_stats`, `list_contexts`, `get_context` and `make_handoff`. Save only explicitly authorized text and delete only the requested notebook.

Notebooks default to plaintext SQLite at `~/.tomc/memory.sqlite3`. For the UV template, merge this field alongside `command` and `args` to choose a different file:

```json
{
  "env": {"TOMC_MEMORY_PATH": "/absolute/path/to/tomc-memory.sqlite3"}
}
```

Clients using the same file can share explicitly saved notes. TOMC does not collect other chats, remove host history or provide cloud synchronization. Returned memory enters WorkBuddy's context and follows its data policy.

Please report setup feedback through [GitHub issues](https://github.com/ZipengWu365/TOMC/issues), including WorkBuddy version, OS, configuration route and error message. Omit credentials, private history and notebook contents.
