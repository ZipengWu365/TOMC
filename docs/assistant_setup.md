# Use TOMC with your assistant

The MCP server lets an assistant prepare supplied history for its next task. Your existing assistant writes the answer. Named notebooks optionally keep notes across chats.

This integration uses the official Python MCP SDK and clients that launch local stdio servers. It provides explicit local persistence alongside the stateless compiler. It does not automatically capture your chats.

Claude Desktop and Codex CLI have packages that include a locked local runtime, and Claude Code has a plugin. See [Install TOMC in your assistant](assistant_plugin.md); Claude Desktop GUI installation is not yet verified. The setup below works for any MCP client that launches local stdio servers, including the Codex IDE extension. Python 3.10 or newer is required; check with `python3 --version` (macOS ships 3.9).

## Install

The repository is public. There is no published PyPI package or official public marketplace listing.

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
.\.venv\Scripts\python.exe -m tomc setup --client cursor --write
.\.venv\Scripts\python.exe -m tomc doctor
```

Change `cursor` to `claude-desktop`, `claude-code`, `codex` or `workbuddy` for that client. The configuration registers the environment you just installed; it does not install dependencies on another computer.

In mainland China, add `-i https://pypi.tuna.tsinghua.edu.cn/simple` to the `pip install` command.

You can also install with `uv pip install --python .venv/bin/python -e '.[mcp]'`. On Windows, use `.venv\Scripts\python.exe`. The [Linux verification report](linux_validation.md) records fresh installation, actual Codex tool discovery and packaged MCP runtime checks.

Core and MCP require Python 3.10+. The integration pins the SDK's [v1.30 maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.30.0), which also works with the current Gradio demo on Python 3.10–3.13. SDK 2.x requires a Pydantic version that conflicts with this demo version. CI checks combined installations on Python 3.10 and 3.12; `requirements-mcp.lock` records the standalone MCP dependencies.

## Connect your client

Run these commands using the installed environment's `python`. With `--write`, `setup` merges a `tomc` entry, with the absolute interpreter path, into the client's configuration file. It keeps every other server and setting, saves a timestamped owner-only backup first (`<file>.tomc-backup-<time>`), and changes nothing when run again. Without `--write` it prints the configuration for you to merge yourself. Then run `python -m tomc doctor`: it checks Python, the MCP extra, the database, `uv`, a live server start with a throwaway database and which clients are set up.

| Client | Command | File it writes |
|---|---|---|
| Codex | `python -m tomc setup --client codex --write` | `~/.codex/config.toml` (`[mcp_servers.tomc]`) |
| Claude Desktop | `python -m tomc setup --client claude-desktop --write` (`claude` is the same) | `claude_desktop_config.json` in Claude's settings folder |
| Claude Code | `python -m tomc setup --client claude-code --write`; without `--write` it prints a `claude mcp add` command | `~/.claude.json` |
| Cursor | `python -m tomc setup --client cursor --write` | `~/.cursor/mcp.json`; add `--config .cursor/mcp.json` for a project file |
| TRAE (International / CN) | `python -m tomc setup --client trae --write --config <file>` | The file you name: TRAE's MCP settings file or project `.trae/mcp.json` |
| Tencent WorkBuddy | `python -m tomc setup --client workbuddy --write` | `~/.workbuddy/mcp.json`; add `--config .workbuddy/mcp.json` for a project file |

For manually entered Cursor STDIO configuration, add `"type": "stdio"` alongside `command` and `args`, or use the client-specific template linked below.

TRAE has no fixed configuration file, so `--write` needs `--config`. TRAE requires an executable command path without spaces. For the locked UV runtime, copyable JSON and client-specific steps, see [Cursor / TRAE setup](cursor_trae.md). Cursor and TRAE tool calls have not yet been verified on a real machine.

The WorkBuddy entry declares local `stdio` and keeps the selected store path in the launch arguments. See [WorkBuddy setup](workbuddy.md) for the locked UV template. WorkBuddy tool calls have not yet been verified on a real machine.

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

Reconnect or restart the client, open a new chat and check that twelve TOMC tools appear. Then say **Try TOMC Memory**. The client launches the server; you do not need to run `tomc mcp` yourself. Started by hand in a terminal, it prints a one-line hint and exits. The server exits on its own when the client disconnects.

The configuration examples follow the [Codex](https://developers.openai.com/codex/mcp), [Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers) and [Cursor](https://cursor.com/docs/mcp) guides reviewed on 2026-09-09. Subprocess tests cover tool discovery, calls and legacy initialization. Individual product GUIs were not tested end to end.

## Try it

Say **Try TOMC Memory** (or **试一下 TOMC Memory**), or run `python -m tomc try` in a terminal. It prepares a built-in 120-day sample project chat, shows how many tokens were kept and the latest values found with their line numbers, and saves nothing.

### Two chats

Start with [usage tips](usage_tips.md) for task-specific preparation and checking the returned sources. The [Windows installation feedback](windows_installation_feedback.md) separates installation, runtime and model checks.

In the first chat:

> Use TOMC to remember this as `workshop`: the workshop now has 28 attendees. Room B is available but not booked. We still need to confirm accessibility.

In a new chat:

> Recall `workshop` from TOMC and help me continue.

The assistant uses `remember_memory` and `recall_memory`, subject to its tool-permission settings. The notebook stores the supplied notes. TOMC does not book Room B or mark accessibility as confirmed.

To find a notebook, ask “List my TOMC notebooks.” To delete one, ask “Forget the TOMC notebook workshop.” The delete tool removes only that exact name (matched case-insensitively), plus the contexts prepared from it, and is marked destructive. To delete everything, run `python -m tomc erase-all --yes`.

## Storage and privacy

Each save appends the supplied text; an immediate identical retry is deduplicated. Notebook names stay separate. Recall keeps short histories intact and routes longer histories for the current task.

The default database is `~/.tomc/memory.sqlite3`. Set `TOMC_MEMORY_PATH` to change it, or generate configuration with a custom path:

```bash
python -m tomc setup --client cursor --store /absolute/path/memory.sqlite3
```

Clients using the same database share notebooks. Separate database paths keep environments separate. Each notebook accepts up to 200,000 characters; an append that exceeds the limit fails without removing existing entries.

Notes you save are stored as local plaintext in an owner-only file. `prepare_context` and `recall_memory` results are not saved unless you run `python -m tomc settings --save-mcp-results on`; saved results are redacted and deleted after 30 days. Recalled context is sent back to the assistant and follows that host's data policy. Deleting a notebook does not erase an assistant's chat. [Security and privacy](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md)

The server reads only text passed to its tools. It does not read other chats, browse files, run stored commands or call a model. It exposes no HTTP endpoint, and this configuration does not connect remote-only clients such as ChatGPT web.

## Copy and paste instead

Use **Use now**, or prepare a prompt from the command line:

```bash
python -m tomc prepare history.txt --task "What are the current preferences?"
```

Replace `history.txt` with your own long history; a short file is returned as it is. Add `--messages` for provider-neutral message JSON, `--output outputs/context.txt` to save the prompt, or use `-` as the filename to read stdin. This path creates no notebook and calls no model.

If the client cannot find the executable, regenerate its entry from the installed environment. For an import error, install `.[mcp]` there. Regenerate configuration after moving or deleting the virtual environment.
