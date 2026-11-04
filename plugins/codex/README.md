# TOMC for Codex

Prepare task-specific context for the assistant you already use. TOMC selects source text and computes supported task records on CPU, without another model service. This research preview contains a native plugin, a context-preparation skill and a locked MCP runtime.

TOMC is free to use, including commercially, under the MIT License in `plugins/tomc-memory/LICENSE`. Modification and redistribution are welcome; retain the copyright and license notice. Third-party dependencies retain their own licenses.

## Install

Install a current Codex CLI with plugin support and [UV](https://docs.astral.sh/uv/getting-started/installation/). Extract `tomc-memory-codex-0.3.1.zip` to a permanent directory, open a terminal in that directory, then run:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

After installing, start a new Codex session and say **Try TOMC Memory** (or **试一下 TOMC Memory**). It runs a built-in sample, shows real before/after numbers and saves nothing.

`--check` validates the package, executable paths and Codex plugin support without writing configuration or registering anything; it lists every missing prerequisite at once. The installation command writes runtime paths for your computer, registers the local marketplace and installs TOMC with the official Codex CLI commands. Then it starts the configured server once with a throwaway database and lists its tools; add `--no-verify` to skip this for an offline install. It uses the supported `.codex-plugin/plugin.json` compatibility layout with an explicit MCP configuration. Start a new session after installation. The first MCP startup needs network access to install compatible Python and the pinned dependencies through UV. No extra model API key or GPU is needed for TOMC.

If UV or Codex is outside PATH, supply their actual executable paths:

```bash
"/absolute/path/to/uv" run --no-project --python 3.12 install.py \
  --uv "/absolute/path/to/uv" --codex "/absolute/path/to/codex"
```

macOS can have Python 3.9 and no UV by default. Python 3.9 is fine for the installer; TOMC itself needs Python 3.10 or later, and `--python 3.12` lets UV provide one interpreter for both the installer and the server. If UV is missing, install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `python3 -m pip install --user uv`.

In mainland China, use mirrors for uv, Python and packages:

```bash
python3 -m pip install --user uv -i https://pypi.tuna.tsinghua.edu.cn/simple
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_PYTHON_INSTALL_MIRROR=https://registry.npmmirror.com/-/binary/python-build-standalone
python3 -m uv run --no-project --python 3.12 install.py
```

On Windows PowerShell, use `py -m pip …` and set `$env:UV_DEFAULT_INDEX` and `$env:UV_PYTHON_INSTALL_MIRROR` to the same addresses. Pass `--codex /absolute/path/to/codex` for a desktop-bundled Codex CLI that is not available as `codex` in your terminal.

To write the local launch configuration without registering anything in Codex, use `uv run --no-project --python 3.12 install.py --configure-only`, then follow the printed commands or use `/plugins` after registering the marketplace. Keep the extracted directory in place; rerun the installer after moving it. Share the original ZIP, since a configured copy contains paths specific to your computer. The installer adds TOMC through Codex commands and does not replace your configuration file.

For a separate set of notebooks, add `--store /path/to/notebooks.sqlite3` to the installer command. This explicitly configures the database path for Codex's MCP process.

After a successful installation, the helper prints one optional invitation to [Star TOMC on GitHub](https://github.com/ZipengWu365/TOMC). Use `--no-support-message` to hide it. Preflight and configure-only runs do not show it.

## Host-managed conversations

Leave active-chat compaction with the host. When native compaction is enabled or unknown, do not proactively call TOMC to recompact the same chat. Use TOMC for separately supplied external history or explicit saved notebooks. This is an assistant workflow policy, not a compaction detector or automatic model-request replacement hook. [Context ownership](https://github.com/ZipengWu365/TOMC/blob/main/docs/context_ownership.md).

## Prepare external context

Ask Codex to call TOMC's `prepare_context` with your supplied history, next task and memory budget, then answer using the returned memory. No notebook is needed. Histories that fit the budget stay intact, so a short example shows no saving; longer input can use task records and source retrieval. When a later line may have changed a value, the record is marked `STATE?` and that line is included.

The 0.3.1 runtime includes twelve tools: `try_tomc`, `prepare_context`, `remember_memory`, `recall_memory`, `list_memories`, `forget_memory`, `erase_all_memory`, `get_status`, `get_usage_stats`, `list_contexts`, `get_context` and `make_handoff`. Each result starts with a one-line `summary`; diagnostics are under `details`. The skill explains when to prepare context and how to use its sources. Counts and the budget cover memory text under a lexical estimate, excluding task text, tool envelopes and provider framing.

In an API integration, your application sends the prepared context instead of the original history in its next request. In Codex, a tool call does not delete the host's existing chat history or automatically intercept API requests. Short inputs can stay the same size, and record metadata can add overhead; savings depend on what you actually send.

## Saved context and session controls

Since 0.3.0, `prepare_context` and `recall_memory` results are **not saved** unless both **Save context records** and **Save MCP results** are on (`tomc settings --save-mcp-results on`). 0.2.0 and 0.2.1 saved them by default. Saved contexts are redacted for common secrets and deleted after 30 days (`tomc settings --retention-days N`). `forget_memory` also deletes contexts prepared from that notebook; `erase_all_memory` (with `confirm="ERASE ALL"`) or `tomc erase-all --yes` deletes everything. Old statistics that recorded numbers only cannot reconstruct past chat bodies.

Processing is on by default globally and for newly registered sessions. User-level installation makes tools available across projects; it does not force a tool call in every chat. Session registration and per-session pause require the TOMC hooks to be installed and loaded. Codex requires review and trust in `/hooks`; the installer does not change trust or approval settings. The panel follows startup/resume and prompt events, not arbitrary UI tab switches. See [host integration validation](https://github.com/ZipengWu365/TOMC/blob/main/docs/host_integration_validation_20261022.md).

Use `list_contexts` and `get_context` to inspect saved results, or `make_handoff` to obtain a self-contained continuation prompt. The management window can export a portable text package for another Agent or computer. You may include that package in Git; TOMC does not automatically commit or push. These features do not replace the native host's model requests.

## IDE extension

The current Codex IDE extension supports MCP configuration, but not native plugin installation. Use the existing TOMC environment instead:

```bash
python -m tomc setup --client codex --write
```

This merges `[mcp_servers.tomc]` into `~/.codex/config.toml` after a timestamped backup; without `--write` it prints the entry instead. You can also register the installed Python environment with `codex mcp add tomc -- /absolute/path/to/python -m tomc mcp`. Choose either standalone MCP registration or the native plugin in a given client to avoid duplicate tool entries.

## Optional notebooks and updates

To keep supplied history across chats, ask “Use TOMC to remember these notes as workshop: room B is available but not booked.” In a new session, ask “Recall workshop from TOMC and tell me what still needs to be done.”

Notebooks default to `~/.tomc/memory.sqlite3`, outside the plugin and marketplace directories. Clients using the same database share them. Removing the plugin or updating its code does not delete notebooks. The tools see only the notes supplied to them; installing does not automatically read other chats or intercept every model request.

TOMC uses the public preparation helper; the paper's BEAM configuration is a separate evaluation. The assistant uses its existing model and controls tool permissions. On 2026-10-02, preview.2 installed and enabled through its packaged installer on macOS 26.3 arm64 with Codex CLI 0.159.2. A real model called the native plugin's `prepare_context` tool and answered `framework = FastAPI`, `backup_framework = Flask` correctly. The installed host exposed all five tools of that version and passed Chinese-note persistence after restart and deletion checks with an isolated database. Earlier Windows preview.1 trials are recorded separately. Codex, Claude Desktop and Cursor GUI installation remain unvalidated. See the [macOS guide](https://github.com/ZipengWu365/TOMC/blob/main/docs/macos_usage.md) and [dated validation](https://github.com/ZipengWu365/TOMC/blob/main/docs/validation.md).

## Uninstall after a trial

Run with the same Codex executable used for installation:

```bash
codex plugin remove tomc-memory@tomc-local
codex plugin marketplace remove tomc-local
```

After stopping TOMC sessions, you can remove the extracted trial package. If you selected a separate `--store` path, delete that test database only when its notes are no longer needed. The default `~/.tomc/memory.sqlite3` persists after uninstall; keep existing notebooks, use `forget_memory` to delete a requested notebook, or run `tomc erase-all --yes` to delete everything before removing the plugin.

[Official plugin packaging](https://developers.openai.com/plugins/build/plugins) · [Codex plugin support](https://developers.openai.com/codex/plugins) · [MCP setup](https://developers.openai.com/codex/mcp)

## Context reduction statistics

Preparation and recall return a per-call estimated context reduction for the assistant to display. Ask for `get_usage_stats` with `period="all"`, `"today"`, or `"7d"` (UTC) to view cumulative totals. These are context-text estimates, not actual API or billing savings. Repeated preparations count separately; empty outputs are excluded and negative reductions retained. Numeric statistics contain no history, task text or notebook names. Prepared-context bodies and tasks are saved separately only when Save MCP results is on (off by default since 0.3.0). No telemetry is uploaded. Statistics survive notebook deletion; old numeric-only records cannot restore historical content. Existing clients need the new runtime and a new session or supported reload; desktop rendering depends on the host.
