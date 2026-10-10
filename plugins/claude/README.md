# TOMC desktop extension

Prepare task-specific context for your existing assistant. TOMC selects source text and computes supported task records on CPU, without another model service. This is the source template for the private installation preview.

TOMC is free to use, including commercially, under the MIT License included in the bundle. Modification and redistribution are welcome; retain the copyright and license notice. Third-party dependencies retain their own licenses.

Build it from the TOMC checkout:

```bash
python scripts/build_plugin.py
```

The output is `outputs/plugins/tomc-memory-0.1.0.mcpb`. In a current Claude Desktop with MCPB UV support, open **Settings → Extensions → Advanced settings → Install Extension…**, select the file, and follow its installation prompts. The first launch needs network access to download Python and pinned dependencies. No extra model API key, GPU or manual JSON editing is needed.

## Prepare context

Ask your assistant to call `prepare_context` with supplied history, the next task and a memory budget, then answer using the returned memory. No notebook is needed. Histories that fit stay intact; longer input can use supported state, relation or count records and source retrieval.

Counts and the budget cover memory text under a lexical estimate, excluding task text, tool envelopes and provider framing. An API application can send prepared context instead of the original history in its next request. Calling the tool in a chat does not delete existing host history or automatically intercept API requests. Short inputs can stay the same size, and records can add overhead; savings depend on what you actually send.

## Optional notebooks

To keep supplied history across chats, ask “Save these notes to TOMC as workshop: 28 attendees; room B is available but not booked.” In a new chat, ask “Recall workshop from TOMC and tell me what to do next.”

Notebooks default to `~/.tomc/memory.sqlite3`, outside the extension directory. The server honors `TOMC_MEMORY_PATH` when provided by a host; different clients using the same path share notebooks. Only content passed to the tools is stored. Uninstalling the extension does not erase notebooks; ask to forget a specific notebook before uninstalling if desired.

The bundle includes TOMC source and a locked MCP runtime. It uses the public preparation route; the paper's BEAM configuration is a separate evaluation. The assistant decides when to call tools and controls tool permissions. Installing does not automatically read all chats or intercept every model request.

Windows checks cover the packaged stdio runtime, not Claude Desktop model use. Desktop GUI installation on macOS/Windows still needs acceptance testing; see the [validation record](https://github.com/ZipengWu365/TOMC/blob/main/docs/validation.md) for dated package checks and their conditions. The source project and MCPB specify Linux too, but this does not imply an official Claude Desktop Linux client is available. Private package updates are installed manually; this preview is unsigned and is not in an extension directory.

[Claude installation guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) · [MCPB UV example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv)
