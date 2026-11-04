# Install TOMC in your assistant

TOMC prepares task-specific context that you can send in place of a long history. Supply the history, the next task and a memory budget. It selects source text, computes supported state, relation or count records, and returns text for your existing assistant. Preparation runs on CPU without training. The plugin itself needs no extra model API key, GPU or model service.

After installation, start a new chat and say **Try TOMC Memory** (or run `tomc try` in a terminal). It runs a built-in sample and saves nothing. Then call `prepare_context` on your own history, inspect the result and hand it to a new chat or an application request. Short histories can stay unchanged; records and prompt overhead can sometimes increase input. In 0.3.0 the MCP server does not save `prepare_context` or `recall_memory` results unless you turn that on. Notes you save with `remember_memory` are stored locally. For direct request integration, see the [Python API](api_reference.md#prepare-context-before-your-api-call).

The host owns active-chat compaction. Do not proactively use TOMC to recompact that same conversation when native compaction is active or unknown. External-history preparation and explicit notebook workflows remain available. This is the plugin's assistant policy; optional lifecycle hooks register session metadata and enforce TOMC controls, not automatic model-request replacement. [Context ownership](context_ownership.md).

<a id="current-version"></a>

## Current version: 0.3.0

The 0.3.0 packages have twelve MCP tools: `try_tomc`, `prepare_context`, `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`, `erase_all_memory`, `get_status`, `get_usage_stats`, `list_contexts`, `get_context` and `make_handoff`. Every result starts with a one-line `summary`; diagnostics such as the selected method, token estimates and warnings are under `details`. Tool arguments are checked strictly: unknown arguments are rejected and `budget` must be a positive whole number. The server exits when the client closes the connection or its parent process ends.

**Saving changed in 0.3.0.** Versions 0.2.0 and 0.2.1 saved every successful preparation and recall by default. 0.3.0 saves them only when both switches are on: **Save context records** and **Save MCP results** (`tomc settings --save-mcp-results on`; off by default). Saved contexts have common secrets replaced with `[REDACTED]` and are deleted after 30 days (`tomc settings --retention-days N`). `forget_memory` also deletes contexts prepared from that notebook. `erase_all_memory` (with `confirm="ERASE ALL"`), `tomc erase-all --yes` or **Erase all records…** in the companion delete all saved records. Notebooks you save with `remember_memory` are kept as written in `~/.tomc/memory.sqlite3` (or `TOMC_MEMORY_PATH`) until you forget or erase them. Old statistics that hold numbers only cannot rebuild past chat text. [Security and privacy](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md)

Processing defaults to on globally and for newly registered sessions. User-level setup makes tools available across projects. Session-specific pause and registration require installed, loaded hooks; Codex also requires review and trust in `/hooks`. New or changed configuration may require a new session or supported reload. The activity card follows session/prompt events, not every UI tab switch. The hooks do not replace the native client's model requests, and configuration alone does not prove a live connection or input savings. [Validation and limits](host_integration_validation_20261022.md).

The management window can copy a self-contained continuation prompt or export a portable text package for another Agent or computer. The recipient can read the package without TOMC. You may place it in Git, but TOMC does not automatically commit or push. `make_handoff` only returns the selected snapshot's prompt; it does not send a message or write the clipboard.

The dated host tests below were run with earlier packages (0.1.x previews and 0.2.x). None of them was repeated on 0.3.0.

If TOMC proves useful after your first successful tool call, you can [Star the main TOMC repository](https://github.com/ZipengWu365/TOMC) to support the project. This is optional. The Codex installer prints this invitation once per successful install; `--no-support-message` hides it.

## Choose an installation

| Client | Installation | Current scope |
|---|---|---|
| Claude Desktop | Install the `.mcpb` file, or `tomc setup --client claude-desktop --write` | UV runtime package; desktop GUI installation not yet verified |
| Claude Code | Install the plugin from this repository's marketplace, or `tomc setup --client claude-code --write` | Real model calls tested in the VS Code extension with 0.1.x previews; interactive panel use is untested |
| Cursor | `tomc setup --client cursor --write`, an Add to Cursor link, or [manual configuration](cursor_trae.md) | Tool calls not yet verified on a real machine |
| TRAE (International / CN) | `tomc setup --client trae --write --config <file>` or [manual configuration](cursor_trae.md#trae) | Tool calls not yet verified on a real machine |
| Tencent WorkBuddy | `tomc setup --client workbuddy --write` or [manual configuration](workbuddy.md) | Tool calls not yet verified on a real machine |
| Codex | Run the ZIP's installation helper, or `tomc setup --client codex --write` | Native installation and real model calls passed on Windows (preview.4) and macOS (preview.2), both 0.1.x |

Download the 0.3.0 packages from the [release page](https://github.com/ZipengWu365/TOMC/releases/tag/v0.3.0-preview.1): [Claude `.mcpb`](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.0-preview.1/tomc-memory-0.3.0.mcpb) ([checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.0-preview.1/tomc-memory-0.3.0.mcpb.sha256)) or [Codex ZIP](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.0-preview.1/tomc-memory-codex-0.3.0.zip) ([checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.0-preview.1/tomc-memory-codex-0.3.0.zip.sha256)). Older 0.1.x packages are kept in [`plugins/downloads`](https://github.com/ZipengWu365/TOMC/tree/main/plugins/downloads); 0.2.x and 0.3.x are only on the Releases page. Dated host and model checks keep their historical scope.

<a id="setup-write"></a>

### Add TOMC Memory to a client from a checkout

From an environment with `.[mcp]` installed (Python 3.10 or newer):

```bash
python -m tomc setup --client cursor --write   # or claude-desktop, claude-code, codex, workbuddy
python -m tomc doctor
```

`--write` merges a `tomc` entry into the client's own configuration file and keeps every other server and setting. It first saves a timestamped, owner-only backup next to the file (`<file>.tomc-backup-<time>`). Running it again changes nothing. The files are `~/.cursor/mcp.json`, `~/.workbuddy/mcp.json`, `~/.claude.json` (Claude Code), `~/.codex/config.toml` and Claude Desktop's `claude_desktop_config.json`. For TRAE or a project file, pass `--config PATH`. Without `--write`, `setup` prints the configuration; for `claude-code` it prints a `claude mcp add` command. `tomc doctor` checks Python, the MCP extra, the database, `uv`, a live server start with a throwaway database and which clients are set up, and prints a fix for each failure. Running `tomc mcp` by hand in a terminal prints a one-line hint and exits: the assistant starts that command itself.

There is no published PyPI package or public marketplace listing. Updates must be installed manually. [Claude's installation and private distribution guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

## Claude Desktop

The 0.3.0 download is built from this source as `outputs/plugins/tomc-memory-0.3.0.mcpb`. It contains TOMC's source and uses the official MCPB UV runtime: a supported host downloads Python and installs dependencies in an isolated environment. The first installation needs network access; it is not an offline bundle. [Official UV bundle example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv)

Maintainers can build and check the package from the checkout:

```bash
python scripts/build_plugin.py
python scripts/plugin_smoke.py outputs/plugins/tomc-memory-0.3.0.mcpb
```

The second command needs `uv` and the MCP test client (`.[mcp]`). It extracts the archive outside the checkout and launches its locked runtime; it does not install into or alter your assistant. Share the `.mcpb` file and its `.sha256` checksum file with collaborators. A Cursor link containing your own local paths is not a portable installation package.

1. Update Claude Desktop and obtain the `.mcpb` file.
2. Open **Settings → Extensions → Advanced settings → Install Extension…**.
3. Select the file, review its information and follow the installation prompts.
4. Start a chat and check the TOMC tools: the 0.3.0 runtime exposes twelve. Then say **Try TOMC Memory**.

These are the [official custom-extension installation steps](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). Bundle construction and MCP protocol checks do not establish that the desktop installation works on every platform. Claude Desktop GUI installation remains to be tested on macOS and Windows.

## Claude Code

### Install as a plugin (recommended)

Install [UV](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH. Then run in Claude Code:

```
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

Start a new session, or reload the VS Code window, and run `/mcp`: the server appears as `plugin:tomc-memory:tomc` with twelve tools. Then run `/tomc-memory:try` or say **Try TOMC Memory**. The plugin folder is [`plugins/claude-code`](https://github.com/ZipengWu365/TOMC/tree/main/plugins/claude-code); the first start downloads Python, if needed, and the locked `mcp` dependency. To update, run `claude plugin marketplace update tomc` and then `claude plugin update tomc-memory@tomc`; to remove, run `claude plugin uninstall tomc-memory@tomc`. If you registered TOMC manually before, remove that entry with `claude mcp remove tomc-memory --scope user` to avoid two copies of the tools.

### Register the MCP runtime manually

Claude Code does not install `.mcpb` files, but it can launch the same locked runtime as a local stdio MCP server.

1. Download `tomc-memory-0.3.0.mcpb`, check its SHA-256 and extract it (it is a ZIP archive) to a directory you will keep.
2. Install [UV](https://docs.astral.sh/uv/getting-started/installation/) and make `uv` available on PATH before running the commands below. Replace the example path with your actual extracted directory; keep paths quoted when they contain spaces.
3. Install the locked dependencies with `uv sync --locked --directory "/absolute/path/to/extracted"`.
4. Register the server for all your projects:

   ```bash
   claude mcp add tomc-memory --scope user -- uv run --locked --directory "/absolute/path/to/extracted" src/server.py
   ```

   Add `-e TOMC_MEMORY_PATH="/absolute/path/to/memory.sqlite3"` before `--` to keep notebooks in a separate database. `claude mcp get tomc-memory` should report **Connected**.
5. Start a new Claude Code session, or reload the VS Code window, and run `/mcp`. Claude Code asks for permission the first time each tool is used.

Remove the server with `claude mcp remove tomc-memory --scope user`. Keep the extracted directory in place, and register again after moving it.

### VS Code extension notes

These notes apply on every operating system; only the file paths differ.

- The Claude Code panel in VS Code runs the same Claude Code as the `claude` command, so a server registered with `--scope user` is available in the panel too. Reload the VS Code window, or start a new session, after registering it.
- If `claude` is not on PATH, the extension bundles the CLI in `~/.vscode/extensions/anthropic.claude-code-<version>-<platform>/resources/native-binary/`. On Windows this is `%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<version>-win32-x64\resources\native-binary\claude.exe`. Call it by its full path.
- Virtual-environment executables are in `.venv/Scripts/` on Windows and `.venv/bin/` on macOS and Linux.
- When a conda or other virtual environment is active, uv prints a `VIRTUAL_ENV ... will be ignored` warning. It is harmless: `--directory` selects the bundle's own environment.
- A server added during a session becomes available only in the next session.

### Usage tips

- **Name the tool.** When the history is already in the conversation, Claude may answer directly: a tool call cannot shrink context the host already holds. Ask explicitly, for example *"Use tomc-memory prepare_context on this history with task … and budget 200, then answer from the returned memory."*
- **Use it across sessions or before an API call.** Save a long history with `remember_memory`, then call `recall_memory` with the task and budget in a later session. Alternatively, send the prepared memory instead of the full history in your next API request.
- **Set the budget below the history size.** A history that already fits is returned intact (`raw`).
- **Typed records need supported line formats:** `key = value`, `B copies A` and `x -[rel]-> y`. Ordinary prose can be retained as selected source text; routing and input savings depend on the task and budget.
- **Source IDs are TOMC's own zero-based line IDs.** `u0` is the first non-empty line, so a history whose lines are already labelled `u1`, `u2`, … shows labels that differ by one. Use other labels, or none.
- **Choose the budget for the history, and expect savings above about 10,000 tokens.** Claude Code adds roughly 39,000 tokens of its own instructions and tools to every request, and a tool call adds requests. In the VS Code extension trial (Claude Opus 5.5, preview.2 runtime, 2026-10-02; one synthetic history per length, single runs), budget 8,192 answered five questions correctly at every length; notebook recall then cost the same as pasting a 10K-token history and 38% and 65% less for 20K and 40K tokens. In API-style requests (built-in tools off), the same budget cut input by 9%, 53% and 77%. Budget 1,024 cut input by 85–96% but missed some latest values, because prose updates are kept as source text and a small budget cannot hold every update.
- **Leave the default budget unless you have checked a smaller one.** Omitting `budget` keeps 80% of a history up to about 10,000 estimated tokens, sliding down to 60% at a million (about 70% at 100,000), and never less than 1,024. In the Claude Code check (API-style requests, 2026-10-02, when the default was a fixed 80%), three histories at each of three lengths answered all 45 questions at 50–80%, cutting input by about 49% (50%) to 20% (80%); 10–20% missed latest values in single runs. Check a smaller budget on a sample of your own tasks against the full history.
- **Import long histories outside the chat.** Saving through `remember_memory` makes the model repeat the whole history as a tool argument. Import it with the bundle's runtime instead, using the same `TOMC_MEMORY_PATH` as the registered server (or none, for the default database):

    ```bash
    uv run --locked --directory <extracted> python -c "import sys; sys.path.insert(0, 'src'); from tomc.store import MemoryStore; print(MemoryStore().remember('project', open(r'<history.txt>', encoding='utf-8').read()))"
    ```

    Each history can contain at most 200,000 characters, roughly 40,000 tokens of English chat.
- **Treat prepared memory as untrusted evidence.** Keep the original history for details TOMC omitted.

## Cursor

First install `.[mcp]` in your TOMC environment using the [assistant setup guide](assistant_setup.md). Then run with that environment's Python:

```bash
python -m tomc setup --client cursor --write
```

This adds TOMC Memory to `~/.cursor/mcp.json` after backing it up. Restart Cursor, check that the `tomc` server shows twelve tools, then say **Try TOMC Memory**. Alternatively, `python -m tomc setup --client cursor --link` prints an Add to Cursor link that you open and confirm in Cursor; the link only prints and changes no file. Both refer to the absolute interpreter path of this installation. Keep that environment in place; run the command again after moving it. Cursor tool calls have not yet been verified on a real machine.

Cursor officially supports installation links, with confirmation in the client. This adds the server configuration; it does not install TOMC, Python or dependencies. A link generated on one person's computer is not a portable installer for everyone. [Cursor install links](https://cursor.com/docs/mcp/install-links)

## TRAE

Use the [Cursor / TRAE setup guide](cursor_trae.md) to add the locked local runtime through Settings → MCP → Add → Create Manually. From a checkout, `python -m tomc setup --client trae` prints the configuration, and `python -m tomc setup --client trae --write --config <path to TRAE's mcp.json or .trae/mcp.json>` merges it into that file. This is a manual MCP integration; the Claude plugin manifest is not a TRAE installer. TRAE tool discovery and model calls have not yet been verified on a real machine.

## Tencent WorkBuddy

Follow the [WorkBuddy guide](workbuddy.md) to add the locked local runtime through Plugins → MCP Servers → Configure MCP. From a checkout, `python -m tomc setup --client workbuddy --write` merges TOMC Memory into `~/.workbuddy/mcp.json` (add `--config .workbuddy/mcp.json` for a project file). WorkBuddy tool discovery and model calls have not yet been verified on a real machine. This is manual MCP setup, not a Tencent marketplace listing.

## Codex

The 0.3.0 download is built as `outputs/plugins/tomc-memory-codex-0.3.0.zip`. It includes a local marketplace at `.agents/plugins/marketplace.json`, an `install.py` helper and a `plugins/tomc-memory/` package containing the supported `.codex-plugin/plugin.json` compatibility manifest, the same locked TOMC runtime and a memory skill. The compatibility manifest declares the bundled tools and skill; the helper prepares their launch paths for your installation. You can share the original ZIP privately; this does not list TOMC in the public plugin directory. [Official plugin packaging and local marketplaces](https://developers.openai.com/plugins/build/plugins)

Maintainers can build the candidate from the checkout with `python scripts/build_codex_plugin.py`; share the resulting ZIP and its `.sha256` checksum file.

Use a current Codex CLI with plugin support and [install UV](https://docs.astral.sh/uv/getting-started/installation/). Unlike Claude Desktop's managed UV extension, this package requires an existing UV executable. TOMC needs Python 3.10 or later; macOS's system Python 3.9 is fine for running the installer, because UV provides Python 3.12 for both the installer and the server (one download). The first launch requires network access.

If `uv` is missing, the installer lists every missing prerequisite at once and prints these fixes:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
python3 -m pip install --user uv
```

In mainland China, use mirrors for uv, Python and packages:

```bash
python3 -m pip install --user uv -i https://pypi.tuna.tsinghua.edu.cn/simple
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_PYTHON_INSTALL_MIRROR=https://registry.npmmirror.com/-/binary/python-build-standalone
python3 -m uv run --no-project --python 3.12 install.py
```

On Windows PowerShell use `py -m pip install --user uv -i …` and `$env:UV_DEFAULT_INDEX="…"`, `$env:UV_PYTHON_INSTALL_MIRROR="…"` with the same addresses.

1. Extract the ZIP to a directory you will keep.
2. Open a terminal in the extracted directory containing `install.py`, then run:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

After installing, the helper starts the configured server once with a throwaway database and lists its tools (`--no-verify` skips this, for offline installs).

3. Start a new Codex session, check that the TOMC tools are available, then say **Try TOMC Memory**.

The `--check` command validates package files, executable paths and Codex plugin support without writing configuration or registering anything. For executables outside PATH, replace the placeholders with the paths on your computer:

```bash
"/absolute/path/to/uv" run --no-project --python 3.12 install.py \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"
```

The helper resolves this computer's absolute UV and runtime paths, updates the extracted candidate's launch configuration, then uses the official Codex marketplace and plugin commands. It does not replace your existing Codex configuration file wholesale. The generated paths are local to this installation; moving the extracted directory requires running the helper again. Share the original ZIP, not a configured copy containing your machine's paths.

For separate notebooks, add `--store /path/to/notebooks.sqlite3` to the installer command. This explicitly sets the database path for Codex's MCP process; the default remains `~/.tomc/memory.sqlite3`.

### Windows: check which Codex you are installing into

In PowerShell, inspect the executable selected by your terminal:

```powershell
Get-Command codex | Select-Object Source
codex --version
Get-Command uv | Select-Object Source
uv --version
```

The CLI on PATH can differ from the engine bundled with a desktop application. The installer uses the CLI on PATH unless you pass `--codex`. To select a different executable, replace the placeholder below with its real path:

```powershell
uv run --no-project install.py --codex 'C:\path\to\codex.exe'
```

Use a host that supports both plugin commands and your model account. A successful installer message establishes registration, not a successful model request. In a new session, first check the TOMC tools (twelve in 0.3.0), say **Try TOMC Memory**, then try the [preparation example](#prepare-context). Ask for `prepare_context` explicitly and check the tool result. The [Windows feedback](windows_installation_feedback.md) records installation, runtime and real model results separately.

To prepare the local launch configuration and print the follow-up installation commands without registering a marketplace or installing a plugin, use:

```bash
uv run --no-project --python 3.12 install.py --configure-only
```

Once the marketplace is registered, you can also use `/plugins` in a supported Codex CLI to browse it and install TOMC. [Official plugin commands](https://learn.chatgpt.com/docs/developer-commands), [plugin browser](https://developers.openai.com/codex/plugins)

The Codex IDE extension does not currently support native plugins. For the IDE or a CLI without plugin commands, install `.[mcp]` using the [assistant setup guide](assistant_setup.md), then generate configuration using that environment's Python:

```bash
python -m tomc setup --client codex --write
```

This merges a `[mcp_servers.tomc]` table into `~/.codex/config.toml` after a backup; without `--write` it prints the entry for you to add. Alternatively, register the installed interpreter directly with the CLI, replacing the placeholder path:

```bash
codex mcp add tomc -- /absolute/path/to/installed/python -m tomc mcp
```

Codex CLI and the IDE support this direct MCP path. Use either the native plugin or a separately registered TOMC server in the same client to avoid duplicate tools. [Official MCP setup](https://developers.openai.com/codex/mcp)

On 2026-10-04, the published preview.4 ZIP was permanently installed as a native plugin in the owner's Windows Codex profile using the desktop-bundled CLI 0.160.0. The original `gpt-6.1-sol` model, OpenAI provider and login completed two model turns and four TOMC calls: preparation, saving and recall in the first chat, then recall in a separate new chat that received only the notebook name and task. Preparation and recall omitted the budget argument and used the new default. Both answers gave the correct FastAPI current value and Flask copy snapshot. No configuration, feature, MCP-server or tool-namespace override was used; other plugins stayed enabled. The stable installation is kept at `~/.codex/tomc/assistant-preview.4`, with UV at `~/.codex/tomc/tools/Scripts/uv.exe`.

The synthetic notebook was saved in the default `~/.tomc/memory.sqlite3`, recalled after a complete host restart and precisely deleted. The host list was empty before saving and after deletion; a read-only SQLite check confirmed zero final entries. Database metadata changed during normal storage use. The post-install configuration and authentication metadata stayed unchanged. Desktop GUI installation still has not been clicked through. The [Windows feedback](windows_installation_feedback.md) and [preview.4 validation](validation.md#windows-codex-preview4) give the conditions and evidence. Removing the plugin does not delete saved notebooks.

The archived 2026-10-02 checks have a narrower scope: preview.2 and preview.3 passed complete installation and actual-host tool checks in isolated Windows CLI 0.146.0 and 0.159.2 profiles without model calls. Preview.1 model preparation and fresh-chat recall used temporary MCP settings and direct TOMC tool exposure. These older conditions are retained in the dated record; they do not describe the preview.4 installation above. Claude Desktop and Cursor still have runtime checks only.

Fresh downloads of preview.2 passed [Linux verification](linux_validation.md): actual Codex CLI `0.159.0-alpha.12.1` installed the native plugin, discovered all five tools of that version and reconnected after the installation directory moved. The Claude MCPB's extracted runtime also passed persistence and notebook-isolation checks. These Linux checks used temporary settings and stores without model calls; Claude/Cursor GUI installation and model-driven tool choice were not exercised.

On 2026-10-02, the downloaded preview.2 ZIP installed and enabled as a native plugin on macOS 26.3 arm64 with Codex CLI 0.159.2. A real model called its `prepare_context` tool and correctly answered the current FastAPI value and earlier Flask snapshot. The installed host exposed all five tools of that version and passed Chinese-note persistence after a process restart and deletion checks using an isolated database. The machine initially had no UV and Python 3.9.6, so prerequisites required setup. Codex, Claude Desktop and Cursor GUI installation remain unvalidated. [macOS setup and usage tips](macos_usage.md) · [Validation record](validation.md).

In the archived Windows preview.1 diagnostics, npm Codex CLI 0.146.0 could install the plugin but returned HTTP 400 for the original default model. The desktop-bundled CLI 0.159.2 supported that model and login. Use the intended executable rather than assuming that the CLI on PATH matches the desktop engine.

### Remove the native plugin after testing

Use the same Codex executable that installed it:

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

Stop TOMC sessions before deleting the extracted trial directory. If you used `--store`, optionally delete that isolated test database after checking that its notes are no longer needed. Uninstall leaves the default `~/.tomc/memory.sqlite3` intact; do not remove existing notebooks simply to uninstall the plugin. Use `forget_memory` for a specific notebook, or `tomc erase-all --yes` for everything, before uninstalling if needed.

## Prepare context

For everyday use, see the [usage tips](usage_tips.md): specific tasks, update order, source inspection and notebook prompts.

Start with **Try TOMC Memory**: it runs a 120-day sample project chat and shows the latest values TOMC found, with their line numbers. To try the tool on text you supply, ask your assistant to call TOMC's `prepare_context` tool. Pass the text below as `history`, set `task` to `"What are the current framework and backup_framework values?"` and `budget` to `64`, then ask the assistant to answer using the returned memory.

```text
framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available.
```

This example uses explicit assignments and a snapshot copy. TOMC prepares `framework = FastAPI` and `backup_framework = Flask`, with source links. The host controls tool use; your existing model generates the answer.

This short example fits easily, so it shows the records rather than a saving. In 0.3.0 the MCP `prepare_context` tool saves nothing unless you turn on **Save MCP results**; when it does save, histories that already fit can remain intact in the saved result. Longer prose can use retrieval instead of typed records. When a later line may have changed a value without saying it plainly, the record is marked `STATE?` and that later line is included. The `budget` covers memory under the lexical counter; task text and tool framing add overhead.

The 64-token budget above is an explicit small example. For the current default, omit `budget`: TOMC keeps 80% of the history's lexical-estimate length up to about 10,000 tokens, sliding to 60% at a million, with a minimum budget of 1,024. Histories that fit that budget remain intact; this is not a guaranteed saving rate.

Each MCP result fits one tool output. Clients cut long tool results, so TOMC keeps the most relevant memory within about 20,000 characters (50,000 when Claude Code identifies itself through the host hook); set `TOMC_MCP_MAX_CHARS` to change it. For notes and documents, the result may also stop below the budget when the question's evidence is unambiguous. When the assistant prepares the same source again in the same chat, it can pass the previous `delivery.id` as `since_delivery_id`: TOMC then returns only the changed, removed or newly relevant lines, or a short note that nothing changed. A new chat, a restarted server or an outdated ID gets the full context.

### Use a smaller context for the next call

In an application, send `prepared.messages` instead of the original history. In an assistant, you can use the prepared text in a new chat. Calling TOMC inside an existing long chat does not remove messages already held by that host, so the tool call alone does not establish token savings. The plugin does not globally intercept API requests. Check the complete input with the model's tokenizer when measuring savings, and keep the original history for details omitted from the result.

## Tools

| Tool | Purpose |
|---|---|
| `try_tomc` | Run a built-in sample and show what TOMC Memory finds; saves nothing |
| `prepare_context` | Prepare supplied history; saved only when Save MCP results is on |
| `remember_memory` | Append supplied notes to a named notebook |
| `recall_memory` | Prepare that notebook for the next task |
| `list_memories` | List notebook names without their contents |
| `forget_memory` | Delete one named notebook and the contexts prepared from it |
| `erase_all_memory` | Delete all saved notebooks, contexts and conversation records; requires `confirm="ERASE ALL"` |
| `get_usage_stats` | View local estimated context reduction for all, today, or 7d (UTC) |
| `get_status` | Read settings, configuration evidence and the latest preparation status |
| `list_contexts` | List saved context snapshots without their bodies |
| `get_context` | Read one selected snapshot as possibly incomplete historical evidence |
| `make_handoff` | Return a self-contained continuation prompt without sending it |

<details markdown="1">
<summary>Optional: keep history across chats</summary>

The notebook stores supplied text in its original form. `recall_memory` prepares it for the requested task. `prepare_context` needs no notebook. In 0.3.0 neither route saves its prepared result unless **Save MCP results** is on (0.2.0 and 0.2.1 saved them by default).

## Try two chats

In the first chat:

> Use TOMC to remember this as workshop: there are now 28 attendees. Room B is available but not booked. Accessibility still needs confirmation.

In a new chat:

> Recall workshop from TOMC and tell me what still needs confirmation.

The host chooses whether to call tools and applies its own permission settings. Saving notes does not book a room or confirm an unresolved fact.

## Storage and capability

To continue from Codex in Claude Code, or the reverse, point both TOMC servers at the same database and use the same notebook name. [Shared-path setup and two handoff prompts](usage_tips.md#reuse-notebooks).

The default database is `~/.tomc/memory.sqlite3`, outside the installation bundle. Clients using the same database share notebooks; separate paths keep notebooks separate. The database stores submitted notes as local plaintext in an owner-only file. Erase one notebook with `forget_memory`, or everything with `tomc erase-all --yes`. Recalled notes enter the assistant's context and follow that host's data policy. Uninstalling the plugin does not itself delete this database.

The plugin sees only content passed to its tools. It does not read every chat, automatically intercept API requests or replace the host's context window. This assistant helper uses the demo's task routing and local notebook interface; it is not the exact BEAM evaluation configuration from the paper. The paper's results should not be treated as measured guarantees for this plugin workflow.

</details>

[Chinese guide](assistant_plugin_zh.md)

## Context reduction statistics

Preparation and recall return a per-call estimated context reduction for the assistant to display. Ask for `get_usage_stats` with `period="all"`, `"today"`, or `"7d"` (UTC) to view cumulative totals. These are context-text estimates, not actual API or billing savings. Repeated preparations count separately; empty outputs are excluded and negative reductions retained. Numeric statistics contain no history, task text or notebook names. Prepared-context bodies and tasks are saved separately only when Save MCP results is on (off by default since 0.3.0). No telemetry is uploaded. Statistics survive notebook deletion; old numeric-only records cannot restore historical content. Existing clients need the new runtime and a new session or supported reload; desktop rendering depends on the host.
