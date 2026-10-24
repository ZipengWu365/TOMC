# TOMC desktop extension

Prepare task-specific context for your existing assistant. TOMC selects source text and computes supported task records on CPU, without another model service. This is the source template for the private installation preview.

TOMC is free to use, including commercially, under the MIT License included in the bundle. Modification and redistribution are welcome; retain the copyright and license notice. Third-party dependencies retain their own licenses.

Build it from the TOMC checkout:

```bash
python scripts/build_plugin.py
```

The output is `outputs/plugins/tomc-memory-0.2.1.mcpb`. In a current Claude Desktop with MCPB UV support, open **Settings → Extensions → Advanced settings → Install Extension…**, select the file, and follow its installation prompts. The first launch needs network access to download Python and pinned dependencies. No extra model API key, GPU or manual JSON editing is needed.

## Host-managed conversations

Leave active-chat compaction with the host. When native compaction is enabled or unknown, do not proactively call TOMC to recompact the same chat. Use TOMC for separately supplied external history or explicit saved notebooks. This is an assistant workflow policy, not a compaction detector or automatic model-request replacement hook. [Context ownership](https://github.com/ZipengWu365/TOMC/blob/main/docs/context_ownership.md).

## Prepare external context

Ask your assistant to call `prepare_context` with supplied history, the next task and a memory budget, then answer using the returned memory. No notebook is needed. Histories that fit stay intact; longer input can use supported state, relation or count records and source retrieval.

Counts and the budget cover memory text under a lexical estimate, excluding task text, tool envelopes and provider framing. An API application can send prepared context instead of the original history in its next request. Calling the tool in a chat does not delete existing host history or automatically intercept API requests. Short inputs can stay the same size, and records can add overhead; savings depend on what you actually send.

## Saved context and controls (since 0.2.0)

The runtime exposes ten tools. Four new read-only tools provide status and continuation: `get_status`, `list_contexts`, `get_context` and `make_handoff`. Successful preparation and recall save the prepared context and task locally by default. Turn off context recording in the TOMC panel to stop future body storage; existing snapshots remain until deleted. A short input may be preserved in full. Old numeric-only statistics cannot reconstruct earlier chats.

Global processing and newly registered sessions default to on. Session-specific controls require a supported host's TOMC hooks to be installed and loaded; the Claude Desktop MCPB alone does not establish Claude Code hook support. The optional Codex/Claude Code integration registers metadata and guards TOMC calls, without automatically replacing model requests. Codex additionally requires `/hooks` trust review. See [host integration validation](https://github.com/ZipengWu365/TOMC/blob/main/docs/host_integration_validation_20261022.md).

`make_handoff` returns a self-contained continuation prompt; it does not send it elsewhere. The management window can export a portable text package for another Agent or computer. It can be added to Git by the user; TOMC does not commit or push automatically.

## Optional notebooks

To keep supplied history across chats, ask “Save these notes to TOMC as workshop: 28 attendees; room B is available but not booked.” In a new chat, ask “Recall workshop from TOMC and tell me what to do next.”

Notebooks default to `~/.tomc/memory.sqlite3`, outside the extension directory. The server honors `TOMC_MEMORY_PATH` when provided by a host; different clients using the same path share notebooks. Only content passed to the tools is stored. Uninstalling the extension does not erase notebooks; ask to forget a specific notebook before uninstalling if desired.

The bundle includes TOMC source and a locked MCP runtime. It uses the public preparation route; the paper's BEAM configuration is a separate evaluation. The assistant decides when to call tools and controls tool permissions. Installing does not automatically read all chats or intercept every model request.

Windows checks cover the packaged stdio runtime, not Claude Desktop model use. Desktop GUI installation on macOS/Windows still needs acceptance testing; see the [validation record](https://github.com/ZipengWu365/TOMC/blob/main/docs/validation.md) for dated package checks and their conditions. The source project and MCPB specify Linux too, but this does not imply an official Claude Desktop Linux client is available. Private package updates are installed manually; this preview is unsigned and is not in an extension directory.

[Claude installation guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) · [MCPB UV example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv)

## Context reduction statistics (0.1.2)

Preparation and recall return a per-call estimated context reduction for the assistant to display. Ask for `get_usage_stats` with `period="all"`, `"today"`, or `"7d"` (UTC) to view cumulative totals. These are context-text estimates, not actual API or billing savings. Repeated preparations count separately; empty outputs are excluded and negative reductions retained. Numeric statistics contain no history, task text or notebook names. Since 0.1.5, prepared-context bodies and tasks are saved separately by default, unless context recording is disabled. No telemetry is uploaded. Statistics survive notebook deletion; old numeric-only records cannot restore historical content. Existing clients need the new runtime and a new session or supported reload; desktop rendering depends on the host.
