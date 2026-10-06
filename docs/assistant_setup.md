# Use TOMC with your assistant

The MCP server lets an assistant prepare supplied history for its next task. Your existing assistant writes the answer. Named notebooks optionally keep notes across chats.

This integration uses the official Python MCP SDK and clients that launch local stdio servers. It provides explicit local persistence alongside the stateless compiler. It does not automatically capture your chats.

Claude Desktop and Codex CLI have installation candidates that include a locked local runtime. Cursor users can generate an install link after installing the environment. See [Install TOMC in your assistant](assistant_plugin.md); desktop GUI acceptance is still pending. The manual setup below also supports the Codex IDE extension.

## Install

The repository is currently private, so cloning requires access. There is no published PyPI package or one-click marketplace listing.

```bash
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
```

On Linux/macOS, use [UV](https://docs.astral.sh/uv/getting-started/installation/) to install Python and seed pip. This path passed the Linux check:

```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
```

Alternatively, create the environment with `python3 -m venv .venv` and activate it as above. Debian/Ubuntu need the matching `python3-venv` package; a system without it can report that `ensurepip` is unavailable. For a partially created environment, use `uv venv --python 3.12 --allow-existing --seed .venv`.

In Windows PowerShell with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
```

On Linux/macOS, install with the activated environment's interpreter:

```bash
python -m pip install -e '.[mcp]'
```

On Windows PowerShell, use the environment's Python directly. Activation is unnecessary:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[mcp]'
.\.venv\Scripts\python.exe -m tomc setup --client cursor --link
```

Change `cursor --link` to `codex` or `claude` to print that client's configuration. A Cursor link registers the environment you just installed; it does not install dependencies on another computer.

You can also install with `uv pip install --python .venv/bin/python -e '.[mcp]'`. On Windows, use `.venv\Scripts\python.exe`. The [Linux verification report](linux_validation.md) records fresh installation, actual Codex tool discovery and packaged MCP runtime checks.

Core and MCP require Python 3.10+. The integration pins the SDK's [v1.30 maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0), which also works with the current Gradio demo on Python 3.10–3.13. SDK 2.x requires a Pydantic version that conflicts with this demo version. CI checks combined installations on Python 3.10 and 3.12; `requirements-mcp.lock` records the standalone MCP dependencies.

## Connect your client

Run these commands using the installed environment's `python`. They print configuration containing the absolute interpreter path. Merge the TOMC entry into your existing settings.

| Client | Generate configuration | Destination |
|---|---|---|
| Codex | `python -m tomc setup --client codex` | `~/.codex/config.toml` or MCP settings |
| Claude Desktop | `python -m tomc setup --client claude` | Settings → Developer → Edit Config; add `mcpServers.tomc` |
| Cursor | `python -m tomc setup --client cursor` | Project `.cursor/mcp.json` or user `~/.cursor/mcp.json`; add `mcpServers.tomc` |

Codex CLI users on macOS/Linux can also register the server directly:

```bash
codex mcp add tomc -- "$PWD/.venv/bin/python" -m tomc mcp
```

For the same direct MCP registration from the repository directory in Windows PowerShell:

```powershell
$tomcPython = (Resolve-Path .\.venv\Scripts\python.exe).Path
codex mcp add tomc -- $tomcPython -m tomc mcp
```

These commands register the server in Codex. Use this path or the native plugin in the same client, to avoid duplicate tools. The command syntax follows the [official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), checked on 2026-10-02.

Reconnect the client, open a new chat and check that five TOMC tools appear. The client launches the server. A separate `tomc mcp` terminal is unnecessary; a stdio server waiting silently in a terminal is normal.

The configuration examples follow the [Codex](https://developers.openai.com/codex/mcp), [Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers) and [Cursor](https://cursor.com/docs/mcp) guides reviewed on 2026-09-09. Subprocess tests cover tool discovery, calls and legacy initialization. Individual product GUIs were not tested end to end.

## Try two chats

Start with [usage tips](usage_tips.md) for task-specific preparation and checking the returned sources. The [Windows installation feedback](windows_installation_feedback.md) separates installation, runtime and model checks.

In the first chat:

> Use TOMC to remember this as `workshop`: the workshop now has 28 attendees. Room B is available but not booked. We still need to confirm accessibility.

In a new chat:

> Recall `workshop` from TOMC and help me continue.

The assistant uses `remember_memory` and `recall_memory`, subject to its tool-permission settings. The notebook stores the supplied notes. TOMC does not book Room B or mark accessibility as confirmed.

To find a notebook, ask “List my TOMC notebooks.” To delete one, ask “Forget the TOMC notebook workshop.” The delete tool removes only that exact name and is marked destructive.

## Storage and privacy

Each save appends the supplied text; an immediate identical retry is deduplicated. Notebook names stay separate. Recall keeps short histories intact and routes longer histories for the current task.

The default database is `~/.tomc/memory.sqlite3`. Set `TOMC_MEMORY_PATH` to change it, or generate configuration with a custom path:

```bash
python -m tomc setup --client cursor --store /absolute/path/memory.sqlite3
```

Clients using the same database share notebooks. Separate database paths keep environments separate. Each notebook accepts up to 200,000 characters; an append that exceeds the limit fails without removing existing entries.

Submitted text is stored as local plaintext. Recalled context is sent back to the assistant and follows that host's data policy. Deleting a notebook does not erase an assistant's chat or guarantee forensic erasure.

The server reads only text passed to its tools. It does not read other chats, browse files, run stored commands or call a model. It exposes no HTTP endpoint. The hosted demo has no shared notebook service, and this configuration does not connect remote-only clients such as ChatGPT web.

## Copy and paste instead

Use **Use now**, or prepare a prompt from the command line:

```bash
python -m tomc prepare demo/examples/preferences.json --task "What are the current preferences?"
```

Add `--messages` for provider-neutral message JSON, `--output outputs/context.txt` to save the prompt, or use `-` as the filename to read stdin. This path creates no notebook and calls no model.

If the client cannot find the executable, regenerate its entry from the installed environment. For an import error, install `.[mcp]` there. Regenerate configuration after moving or deleting the virtual environment.
