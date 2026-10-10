# TOMC for Codex

Prepare task-specific context for the assistant you already use. TOMC selects source text and computes supported task records on CPU, without another model service. This private preview contains a native plugin, a context-preparation skill and a locked MCP runtime.

TOMC is free to use, including commercially, under the MIT License in `plugins/tomc-memory/LICENSE`. Modification and redistribution are welcome; retain the copyright and license notice. Third-party dependencies retain their own licenses.

## Install

Install a current Codex CLI with plugin support and [UV](https://docs.astral.sh/uv/getting-started/installation/). Extract `tomc-memory-codex-0.1.0.zip` to a permanent directory, open a terminal in that directory, then run:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

`--check` validates the package, executable paths and Codex plugin support without writing configuration or registering anything. The installation command writes runtime paths for your computer, registers the local marketplace and installs TOMC with the official Codex CLI commands. It uses the supported `.codex-plugin/plugin.json` compatibility layout with an explicit MCP configuration. Start a new session after installation. The first MCP startup needs network access to install compatible Python and the pinned dependencies through UV. No extra model API key or GPU is needed for TOMC.

If UV or Codex is outside PATH, supply their actual executable paths:

```bash
"/absolute/path/to/uv" run --no-project --python 3.12 install.py \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"
```

macOS can have Python 3.9 and no UV by default. TOMC needs Python 3.10 or later; `--python 3.12` lets UV provide a compatible interpreter. This includes using a desktop-bundled Codex CLI that is not available as `codex` in your terminal.

To write the local launch configuration without registering anything in Codex, use `uv run --no-project --python 3.12 install.py --configure-only`, then follow the printed commands or use `/plugins` after registering the marketplace. Keep the extracted directory in place; rerun the installer after moving it. Share the original ZIP, since a configured copy contains paths specific to your computer. The installer adds TOMC through Codex commands and does not replace your configuration file.

For a separate set of notebooks, add `--store /path/to/notebooks.sqlite3` to the installer command. This explicitly configures the database path for Codex's MCP process.

## Prepare context

Ask Codex to call TOMC's `prepare_context` with your supplied history, next task and memory budget, then answer using the returned memory. No notebook is needed. For a state example, use `framework = Flask`, `backup_framework copies framework` and `framework = FastAPI`; ask for the current values. TOMC supports these explicit assignments and snapshot copies. Histories that fit the budget stay intact; longer input can use task records and source retrieval.

The plugin includes the same five tools as the Claude and Cursor integrations, plus a skill explaining when to prepare context and how to use its sources. Counts and the budget cover memory text under a lexical estimate, excluding task text, tool envelopes and provider framing.

In an API integration, your application sends the prepared context instead of the original history in its next request. In Codex, a tool call does not delete the host's existing chat history or automatically intercept API requests. Short inputs can stay the same size, and record metadata can add overhead; savings depend on what you actually send.

## IDE extension

The current Codex IDE extension supports MCP configuration, but not native plugin installation. Use the existing TOMC environment instead:

```bash
python -m tomc setup --client codex
```

This prints the configuration to merge into Codex settings. You can also register the installed Python environment with `codex mcp add tomc -- /absolute/path/to/python -m tomc mcp`. Choose either standalone MCP registration or the native plugin in a given client to avoid duplicate tool entries.

## Optional notebooks and updates

To keep supplied history across chats, ask “Use TOMC to remember these notes as workshop: room B is available but not booked.” In a new session, ask “Recall workshop from TOMC and tell me what still needs to be done.”

Notebooks default to `~/.tomc/memory.sqlite3`, outside the plugin and marketplace directories. Clients using the same database share them. Removing the plugin or updating its code does not delete notebooks. The tools see only the notes supplied to them; installing does not automatically read other chats or intercept every model request.

TOMC uses the public preparation helper; the paper's BEAM configuration is a separate evaluation. The assistant uses its existing model and controls tool permissions. On 2026-10-02, preview.2 installed and enabled through its packaged installer on macOS 26.3 arm64 with Codex CLI 0.159.2. A real model called the native plugin's `prepare_context` tool and answered `framework = FastAPI`, `backup_framework = Flask` correctly. The installed host exposed all five tools and passed Chinese-note persistence after restart and deletion checks with an isolated database. Earlier Windows preview.1 trials are recorded separately. Codex, Claude Desktop and Cursor GUI installation remain unvalidated. See the [macOS guide](https://github.com/ZipengWu365/TOMC/blob/main/docs/macos_usage.md) and [dated validation](https://github.com/ZipengWu365/TOMC/blob/main/docs/validation.md).

## Uninstall after a trial

Run with the same Codex executable used for installation:

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

After stopping TOMC sessions, you can remove the extracted trial package. If you selected a separate `--store` path, delete that test database only when its notes are no longer needed. The default `~/.tomc/memory.sqlite3` persists after uninstall; keep existing notebooks or use `forget_memory` to delete a requested notebook before removing the plugin.

[Official plugin packaging](https://developers.openai.com/plugins/build/plugins) · [Codex plugin support](https://developers.openai.com/codex/plugins) · [MCP setup](https://developers.openai.com/codex/mcp)
