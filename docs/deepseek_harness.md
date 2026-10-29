# TOMC Memory for DeepSeek Harness

[中文](deepseek_harness_zh.md)

**Unofficial community integration, independently developed and maintained.**
TOMC connects to DeepSeek Harness (DSH) through the official
`@deepseek-ai/dsh-mcp-client` over local stdio. DSH launches the Python server and
exposes its tools as `mcp__tomc__<tool>`. No fork of DSH is required.

[Dated validation and test scope](deepseek_harness_validation_20261029.md).

TOMC runs memory preparation on CPU without an additional model service. Your
chosen DSH model still performs the assistant's reasoning and answer generation.
Use explicitly saved task notes or separately supplied history; the MCP connection
does not intercept model requests or replace DSH's active-chat compaction.

## Install from source

Requirements: Git, Python 3.10+ and a Node.js version supported by your DSH release
(the validation uses Node.js 24). Configure your model in DSH separately. TOMC
itself needs no model API key.

Clone the **public software repository**:

```sh
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
python -m venv .venv
```

On Windows PowerShell, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[mcp]'
.\.venv\Scripts\python.exe scripts/setup_deepseek.py --output "$env:USERPROFILE/.tomc/deepseek/tomc.cordis.yml"
npx.cmd --yes @deepseek-ai/dsh@0.2.1-rc.5 web --patch "$env:USERPROFILE/.tomc/deepseek/tomc.cordis.yml"
```

On macOS/Linux, the equivalent commands are:

```sh
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/python scripts/setup_deepseek.py --output "$HOME/.tomc/deepseek/tomc.cordis.yml"
npx --yes @deepseek-ai/dsh@0.2.1-rc.5 web --patch "$HOME/.tomc/deepseek/tomc.cordis.yml"
```

The overlay contains absolute paths to **your** Python and notebook database.
Keep the checkout and virtual environment in place. It has no credentials and
adds only the TOMC MCP entry. The helper writes UTF-8 and refuses to overwrite
an existing file; choose a new output filename if regenerating after a move.
Do not distribute your generated configuration as a portable installer.

The example pins the DSH version used for validation. DSH is a preview and later
versions may change integration APIs. The macOS/Linux commands are provided as
equivalents; consult the validation record for actually tested platforms.

For an already-installed DSH CLI, replace `npx ... web` with `dsh web`. Keep
`--patch` before app-specific flags such as `--port`. Launch with that overlay
each time. For persistent integration, merge its single `insert` operation into
your existing profile's `cordis.patch.yml`; never replace an existing patch file
that may contain other configuration. Do not register TOMC twice in one profile.

For a separate notebook database, add `--store /absolute/path/memory.sqlite3`
when generating the overlay. To share notes with another assistant, explicitly
choose the same database file in both clients. Default storage is
`~/.tomc/memory.sqlite3`, unless `TOMC_MEMORY_PATH` is configured.

## Verify in two fresh DSH sessions

Open the authenticated local URL printed by DSH and configure a working model.
Allow the requested TOMC calls through DSH's normal permission prompts.

1. In session A, send:

   > Use mcp__tomc__remember_memory to save a notebook named dsh-demo:
   > Project Lark uses port 4317. Keep the public API unchanged. Pagination tests
   > are still pending. Show whether the tool succeeded.

2. Create a **new session** in the same DSH profile, without copying the earlier
   conversation, and send:

   > Use mcp__tomc__recall_memory on notebook dsh-demo. What port does Project
   > Lark use, what must stay unchanged, and which tests remain? Do not guess.

3. Ask for a next-step checklist based on the recalled constraints. Verify the
   actual tool result and answer, rather than accepting a claim that it was saved.

`mcp__tomc__get_status` reports runtime settings, while
`mcp__tomc__list_memories` lists available notebook names. To remove the synthetic
demo note, explicitly ask to forget only `dsh-demo`.

## Data and scope

- Named notebook writes are explicit. TOMC does not automatically collect the
  entire DSH chat or inspect your other chats.
- Successful preparation and recall save prepared context and task text locally
  by default in TOMC 0.2.1. Context recording can be disabled in TOMC's controls;
  existing snapshots remain until deleted. Inspect `get_status` before use.
- TOMC's processing is local. Tool results selected for the conversation are
  visible to the DSH model provider, just like other model context.
- Token estimates refer to prepared memory, not full API billing. Short inputs
  may remain intact; tool overhead can outweigh savings. This integration does
  not establish a universal quality, latency, or cost improvement.
- Removing `--patch` disconnects this integration on the next launch but does
  not delete saved notes or context snapshots.

## Troubleshooting

If tools do not appear, inspect DSH startup errors and check that the configured
Python still exists and can run `-m tomc mcp`. Regenerate the overlay if you moved
the virtual environment. This is an additive Cordis patch, not an `mcpServers`
JSON file for another client.

A DSH page loading while its APIs return HTTP 403 is a browser Host/Origin issue,
not evidence that TOMC connected. Keep the printed hostname and port consistent,
and inspect browser/proxy rewriting; do not disable DSH's trust checks. The local
Windows validation required a loopback port-80 launch because the browser sent
an Origin without the non-default port. Use `--port 80` only if available and
permitted on your system; other machines can use DSH's normal port.

Upstream references: [MCP client](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md),
[memory MCP guide](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md),
[community posting rules](https://github.com/deepseek-ai/deepseek-harness/discussions/2004).
