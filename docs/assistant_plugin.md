# Install TOMC in your assistant

TOMC prepares task-specific context that you can send in place of a long history. Supply the history, the next task and a memory budget. It selects source text, computes supported state, relation or count records, and returns text for your existing assistant. Preparation runs on CPU without training. The plugin itself needs no extra model API key, GPU or model service.

After installation, call `prepare_context`, inspect the result and hand it to a new chat or an application request. Short histories can stay unchanged; records and prompt overhead can sometimes increase input. The compiler is stateless, and notebooks are optional. For direct request integration, see the [Python API](api_reference.md#prepare-context-before-your-api-call).

## Choose an installation

| Client | Installation | Current scope |
|---|---|---|
| Claude Desktop | Install the `.mcpb` file | UV runtime installation candidate; desktop GUI acceptance is pending |
| Claude Code | Register the extracted `.mcpb` runtime with `claude mcp add` | VS Code extension tested in fresh sessions; interactive panel use is untested |
| Cursor | Generate an Add to Cursor link | Requires an installed TOMC MCP environment; the link registers it |
| Codex | Run the ZIP's installation helper | Preview.4 native installation and default-model calls passed in the Windows personal profile; the earlier macOS trial used preview.2 |

Download the packages from the [assistant preview release](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.5): [Claude `.mcpb`](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-0.1.0.mcpb) ([checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-0.1.0.mcpb.sha256)) or [Codex ZIP](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-codex-0.1.0.zip) ([checksum](https://github.com/ZipengWu365/TOMC/releases/download/v0.1.0-assistant-preview.5/tomc-memory-codex-0.1.0.zip.sha256)).

There is no published PyPI package or public marketplace listing. Updates must be installed manually. [Claude's installation and private distribution guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)

## Claude Desktop

The locally built candidate is `outputs/plugins/tomc-memory-0.1.0.mcpb`. It contains TOMC's source and uses the official MCPB UV runtime: a supported host downloads Python and installs dependencies in an isolated environment. The first installation needs network access; it is not an offline bundle. [Official UV bundle example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv)

Maintainers can build and check the package from the checkout:

```bash
python scripts/build_plugin.py
python scripts/plugin_smoke.py outputs/plugins/tomc-memory-0.1.0.mcpb
```

The second command needs `uv` and the MCP test client (`.[mcp]`). It extracts the archive outside the checkout and launches its locked runtime; it does not install into or alter your assistant. Share the `.mcpb` file and its `.sha256` checksum file with collaborators. A Cursor link containing your own local paths is not a portable installation package.

1. Update Claude Desktop and obtain the `.mcpb` file.
2. Open **Settings → Extensions → Advanced settings → Install Extension…**.
3. Select the file, review its information and follow the installation prompts.
4. Start a chat and check that the five TOMC tools are available.

These are the [official custom-extension installation steps](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop). Bundle construction and MCP protocol checks do not establish that the desktop installation works on every platform. Claude Desktop GUI installation remains to be tested on macOS and Windows.

## Claude Code

Claude Code does not install `.mcpb` files, but it can launch the same locked runtime as a local stdio MCP server.

1. Download `tomc-memory-0.1.0.mcpb`, check its SHA-256 and extract it (it is a ZIP archive) to a directory you will keep.
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

- **Name the tool.** When the history is already in the conversation, Claude answers directly: a tool call cannot shrink context the host already holds. Ask explicitly, for example *"Use tomc-memory prepare_context on this history with task … and budget 200, then answer from the returned memory."*
- **Use it across sessions or before an API call.** Save a long history with `remember_memory`, then call `recall_memory` with the task and budget in a later session. Alternatively, send the prepared memory instead of the full history in your next API request.
- **Set the budget below the history size.** A history that already fits is returned intact (`raw`).
- **Typed records need supported line formats:** `key = value`, `B copies A` and `x -[rel]-> y`. Ordinary prose can be retained as selected source text; routing and input savings depend on the task and budget.
- **Source IDs are TOMC's own zero-based line IDs.** `u0` is the first non-empty line, so a history whose lines are already labelled `u1`, `u2`, … shows labels that differ by one. Use other labels, or none.
- **Choose the budget for the history, and expect savings above about 10,000 tokens.** Claude Code adds roughly 39,000 tokens of its own instructions and tools to every request, and a tool call adds requests. In the VS Code extension trial with Claude Opus 5.5, budget 8,192 answered five questions correctly at every length; notebook recall then cost the same as pasting a 10K-token history and 38% and 65% less for 20K and 40K tokens. In API-style requests, the same budget cut input by 9%, 53% and 77%. Budget 1,024 cut input by 85–96% but missed some latest values, because prose updates are kept as source text and a small budget cannot hold every update.
- **Leave the default budget unless you have checked a smaller one.** Omitting `budget` keeps about 80% of the history (at least 1,024 estimated tokens). Across three histories at each of three lengths, keeping 50–80% answered all 45 questions like the full history, saving about 49% (50%) to 20% (80%) of input; 10–20% missed latest values. Check a smaller budget on a sample of your own tasks against the full history.
- **Import long histories outside the chat.** Saving through `remember_memory` makes the model repeat the whole history as a tool argument. Import it with the bundle's runtime instead, using the same `TOMC_MEMORY_PATH` as the registered server (or none, for the default database):

    ```bash
    uv run --locked --directory <extracted> python -c "import sys; sys.path.insert(0, 'src'); from tomc.store import MemoryStore; print(MemoryStore().remember('project', open(r'<history.txt>', encoding='utf-8').read()))"
    ```

    Each history can contain at most 200,000 characters, roughly 40,000 tokens of English chat.
- **Treat prepared memory as untrusted evidence.** Keep the original history for details TOMC omitted.

## Cursor

First install `.[mcp]` in your TOMC environment using the [assistant setup guide](assistant_setup.md). Then run with that environment's Python:

```bash
python -m tomc setup --client cursor --link
```

Open the generated link and confirm the installation in Cursor. It refers to the absolute interpreter path of this installation. Keep that environment in place; regenerate the link after moving it. The command prints a link and does not edit your client configuration.

Cursor officially supports installation links, with confirmation in the client. This adds the server configuration; it does not install TOMC, Python or dependencies. A link generated on one person's computer is not a portable installer for everyone. [Cursor install links](https://cursor.com/docs/mcp/install-links)

## Codex

The installation candidate is `outputs/plugins/tomc-memory-codex-0.1.0.zip`. It includes a local marketplace at `.agents/plugins/marketplace.json`, an `install.py` helper and a `plugins/tomc-memory/` package containing the supported `.codex-plugin/plugin.json` compatibility manifest, the same locked TOMC runtime and a memory skill. The compatibility manifest declares the bundled tools and skill; the helper prepares their launch paths for your installation. You can share the original ZIP privately; this does not list TOMC in the public plugin directory. [Official plugin packaging and local marketplaces](https://developers.openai.com/plugins/build/plugins)

Maintainers can build the candidate from the checkout with `python scripts/build_codex_plugin.py`; share the resulting ZIP and its `.sha256` checksum file.

Use a current Codex CLI with plugin support and [install UV](https://docs.astral.sh/uv/getting-started/installation/). Unlike Claude Desktop's managed UV extension, this package requires an existing UV executable. TOMC needs Python 3.10 or later; macOS's system Python can be too old. You do not need to install compatible Python separately: the commands below let UV provide Python 3.12 and dependencies, so the first launch requires network access.

1. Extract the ZIP to a directory you will keep.
2. Open a terminal in the extracted directory containing `install.py`, then run:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

3. Start a new Codex session and check that the TOMC tools are available.

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

Use a host that supports both plugin commands and your model account. A successful installer message establishes registration, not a successful model request. In a new session, first check that the five TOMC tools are present, then try the [preparation example](#prepare-context). Ask for `prepare_context` explicitly and check the tool result. The [Windows feedback](windows_installation_feedback.md) records installation, runtime and real model results separately.

To prepare the local launch configuration and print the follow-up installation commands without registering a marketplace or installing a plugin, use:

```bash
uv run --no-project --python 3.12 install.py --configure-only
```

Once the marketplace is registered, you can also use `/plugins` in a supported Codex CLI to browse it and install TOMC. [Official plugin commands](https://learn.chatgpt.com/docs/developer-commands), [plugin browser](https://developers.openai.com/codex/plugins)

The Codex IDE extension does not currently support native plugins. For the IDE or a CLI without plugin commands, install `.[mcp]` using the [assistant setup guide](assistant_setup.md), then generate configuration using that environment's Python:

```bash
python -m tomc setup --client codex
```

Add the printed entry to your MCP settings. Alternatively, register the installed interpreter directly with the CLI, replacing the placeholder path:

```bash
codex mcp add tomc -- /absolute/path/to/installed/python -m tomc mcp
```

Codex CLI and the IDE support this direct MCP path. Use either the native plugin or a separately registered TOMC server in the same client to avoid duplicate tools. [Official MCP setup](https://developers.openai.com/codex/mcp)

On 2026-10-04, the published preview.4 ZIP was permanently installed as a native plugin in the owner's Windows Codex profile using the desktop-bundled CLI 0.160.0. The original `gpt-6.1-sol` model, OpenAI provider and login completed two model turns and four TOMC calls: preparation, saving and recall in the first chat, then recall in a separate new chat that received only the notebook name and task. Preparation and recall omitted the budget argument and used the new default. Both answers gave the correct FastAPI current value and Flask copy snapshot. No configuration, feature, MCP-server or tool-namespace override was used; other plugins stayed enabled. The stable installation is kept at `~/.codex/tomc/assistant-preview.4`, with UV at `~/.codex/tomc/tools/Scripts/uv.exe`.

The synthetic notebook was saved in the default `~/.tomc/memory.sqlite3`, recalled after a complete host restart and precisely deleted. The host list was empty before saving and after deletion; a read-only SQLite check confirmed zero final entries. Database metadata changed during normal storage use. The post-install configuration and authentication metadata stayed unchanged. Desktop GUI installation still has not been clicked through. The [Windows feedback](windows_installation_feedback.md) and [preview.4 validation](validation.md#windows-codex-preview4) give the conditions and evidence. Removing the plugin does not delete saved notebooks.

The archived 2026-10-02 checks have a narrower scope: preview.2 and preview.3 passed complete installation and actual-host tool checks in isolated Windows CLI 0.146.0 and 0.159.2 profiles without model calls. Preview.1 model preparation and fresh-chat recall used temporary MCP settings and direct TOMC tool exposure. These older conditions are retained in the dated record; they do not describe the preview.4 installation above. Claude Desktop and Cursor still have runtime checks only.

Fresh downloads of preview.2 passed [Linux verification](linux_validation.md): actual Codex CLI `0.159.0-alpha.12.1` installed the native plugin, discovered all five tools and reconnected after the installation directory moved. The Claude MCPB's extracted runtime also passed persistence and notebook-isolation checks. These Linux checks used temporary settings and stores without model calls; Claude/Cursor GUI installation and model-driven tool choice were not exercised.

On 2026-10-02, the downloaded preview.2 ZIP installed and enabled as a native plugin on macOS 26.3 arm64 with Codex CLI 0.159.2. A real model called its `prepare_context` tool and correctly answered the current FastAPI value and earlier Flask snapshot. The installed host exposed all five tools and passed Chinese-note persistence after a process restart and deletion checks using an isolated database. The machine initially had no UV and Python 3.9.6, so prerequisites required setup. Codex, Claude Desktop and Cursor GUI installation remain unvalidated. [macOS setup and usage tips](macos_usage.md) · [Validation record](validation.md).

In the archived Windows preview.1 diagnostics, npm Codex CLI 0.146.0 could install the plugin but returned HTTP 400 for the original default model. The desktop-bundled CLI 0.159.2 supported that model and login. Use the intended executable rather than assuming that the CLI on PATH matches the desktop engine.

### Remove the native plugin after testing

Use the same Codex executable that installed it:

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

Stop TOMC sessions before deleting the extracted trial directory. If you used `--store`, optionally delete that isolated test database after checking that its notes are no longer needed. Uninstall leaves the default `~/.tomc/memory.sqlite3` intact; do not remove existing notebooks simply to uninstall the plugin. Use `forget_memory` for a specific notebook before uninstall if needed.
## Prepare context

For everyday use, see the [usage tips](usage_tips.md): specific tasks, update order, source inspection and notebook prompts.

After installing, ask your assistant to call TOMC's `prepare_context` tool. Pass the text below as `history`, set `task` to `"What are the current framework and backup_framework values?"` and `budget` to `64`, then ask the assistant to answer using the returned memory.

```text
framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available.
```

This example uses explicit assignments and a snapshot copy. TOMC prepares `framework = FastAPI` and `backup_framework = Flask`, with source links. The host controls tool use; your existing model generates the answer.

`prepare_context` does not save this history. Histories that already fit stay intact; longer prose can use retrieval instead of typed records. The `budget` covers memory under the lexical counter; task text and tool framing add overhead.

The 64-token budget above is an explicit small example. For the current default, omit `budget`: TOMC uses about 80% of the history's lexical-estimate length, with a minimum budget of 1,024. Histories that fit that budget remain intact; this is not a guaranteed saving rate.

### Use a smaller context for the next call

In an application, send `prepared.messages` instead of the original history. In an assistant, you can use the prepared text in a new chat. Calling TOMC inside an existing long chat does not remove messages already held by that host, so the tool call alone does not establish token savings. The plugin does not globally intercept API requests. Check the complete input with the model's tokenizer when measuring savings, and keep the original history for details omitted from the result.

## Tools

| Tool | Purpose |
|---|---|
| `prepare_context` | Prepare supplied history without saving it |
| `remember_memory` | Append supplied notes to a named notebook |
| `recall_memory` | Prepare that notebook for the next task |
| `list_memories` | List notebook names without their contents |
| `forget_memory` | Delete one named notebook when requested |

<details markdown="1">
<summary>Optional: keep history across chats</summary>

The notebook stores supplied text in its original form. `recall_memory` prepares it for the requested task. `prepare_context` works directly on supplied history without saving it.

## Try two chats

In the first chat:

> Use TOMC to remember this as workshop: there are now 28 attendees. Room B is available but not booked. Accessibility still needs confirmation.

In a new chat:

> Recall workshop from TOMC and tell me what still needs confirmation.

The host chooses whether to call tools and applies its own permission settings. Saving notes does not book a room or confirm an unresolved fact.

## Storage and capability

To continue from Codex in Claude Code, or the reverse, point both TOMC servers at the same database and use the same notebook name. [Shared-path setup and two handoff prompts](usage_tips.md#reuse-notebooks).

The default database is `~/.tomc/memory.sqlite3`, outside the installation bundle. Clients using the same database share notebooks; separate paths keep notebooks separate. The database stores submitted notes as local plaintext. Recalled notes enter the assistant's context and follow that host's data policy. Uninstalling the plugin does not itself delete this database.

The plugin sees only content passed to its tools. It does not read every chat, automatically intercept API requests or replace the host's context window. This assistant helper uses the demo's task routing and local notebook interface; it is not the exact BEAM evaluation configuration from the paper. The paper's results should not be treated as measured guarantees for this plugin workflow.

</details>

[Chinese guide](assistant_plugin_zh.md)
