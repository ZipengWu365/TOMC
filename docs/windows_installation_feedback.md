# Windows installation feedback

[中文](windows_installation_feedback_zh.md) · [Install TOMC](assistant_plugin.md) · [Usage tips](usage_tips.md)

On 2026-10-04, preview.4 was permanently installed as a native plugin in the owner's Windows Codex profile. The existing default model called its tools successfully, including recall in a separate new chat. The desktop GUI installation flow has not been clicked through. Earlier package and client checks from 2026-10-02 remain below with their original scope.

## Current Windows Codex installation: preview.4

The original published 91,034-byte ZIP passed its checksum, prerequisite check and full installer. Its SHA-256 is `96b05b516efadba2e6e7f691a8869365233aad5088e7a484d0c0e63b60a013b0`. The package is kept at `~/.codex/tomc/assistant-preview.4`, with UV 0.12.22 at the stable Windows path `~/.codex/tomc/tools/Scripts/uv.exe`. The installed runtime and skill were checked against the ZIP, so this installation does not depend on an old trial directory.

The actual desktop-bundled Codex CLI was 0.160.0. Its existing `gpt-6.1-sol` model, OpenAI provider and login were retained. No configuration, feature, MCP-server or tool-namespace override was used for the model trial, and other plugins were left enabled.

| Check | Result |
|---|---|
| First model chat | Called `prepare_context` without a budget, saved the exact synthetic history with `remember_memory`, then called `recall_memory` without a budget |
| Separate new model chat | Received only the notebook name and task; called `recall_memory` without receiving the history or expected values |
| Answers | Both chats returned `framework = FastAPI` and `backup_framework = Flask` |
| Default-budget branch | An actual-host call measured 1,534 lexical-estimate input tokens, chose budget 1,228 and returned 1,223 memory tokens |

The two model turns made four TOMC calls. The default budget is `max(1024, ceil(input_estimated_tokens × 0.8))`; task text and tool framing are outside it. This is a functional check of one synthetic example, not measured API-billed savings or a general quality guarantee. See the [dated validation](validation.md#windows-codex-preview4) and [sanitized preview.4 evidence](validation_data/windows_codex_preview4_20261004.json).

Storage was tested in the actual default `~/.tomc/memory.sqlite3` database. It contained no notebooks before the first save. The model saved one uniquely named synthetic notebook; recall after a complete host restart passed, and exact deletion removed its one entry. The final host list and an independent read-only SQLite check both showed zero entries. The database metadata changed during this test; it was not an isolated test database. Configuration after installation and authentication metadata stayed unchanged. Installation itself added TOMC's plugin and marketplace while preserving other plugin settings.

## Context budgets and actual input — 2026-10-05

The installed native MCP tool prepared nine synthetic histories outside the answering model. Windows Codex 0.160.0 then used the original `gpt-6.1-sol` model and `ultra` effort in 36 fresh answering chats, without changing personal configuration. Full history and the 40%, 60% and default 80% history budgets each answered 45/45 latest-state questions correctly.

| Context sent | Mean request input tokens | Mean paired input reduction |
|---|---:|---:|
| Full history | 42,191 | Reference |
| TOMC · 40% history budget | 28,713 | 29.7% |
| TOMC · 60% history budget | 33,344 | 19.5% |
| TOMC · default 80% history budget | 38,035 | 9.2% |

Input is the complete provider-reported total, including cached input, host instructions and tool definitions. Reduction averages the nine paired history-level ratios. Preparation was CPU-only and outside the answering turn; in-chat preparation or recall can add model turns. All prepared contexts used source selection without operation records. The test covers synthetic latest-state retrieval, not general coding quality or billed cost. [Full English report](codex_retention_20261005.md) · [中文报告](codex_retention_20261005_zh.md) · [Recorded data](validation_data/windows_codex_retention_20261005.json)

A separate [foreground tool check](validation_data/windows_codex_foreground_20261005.json) in the active Codex conversation also returned the correct assignment and copy states. It collected no provider usage and is not part of the retention comparison. The graphical installation flow remains untested.

## How much setup is needed?

| Client | What the user does | Installation friction |
|---|---|---|
| Codex CLI | Install `uv` and a Codex CLI with plugin commands; download and extract the ZIP; run `uv run --no-project install.py`; open a new session | One installer command once the prerequisites are present. Keep the extracted directory; rerun the installer after moving it. |
| Claude Desktop | Download the `.mcpb` extension and install it through the client's extension settings | The host manages Python and dependencies when it supports this UV bundle. The GUI flow has not been tested here. |
| Claude Code | Extract the `.mcpb`, install its locked dependencies with `uv`, then register the runtime with `claude mcp add` | CLI registration was tested through the Windows VS Code extension's bundled executable. Keep the extracted runtime directory. |
| Cursor | Install TOMC with `.[mcp]`, generate the installation link, then confirm it in Cursor | More steps than the packaged clients. The link registers an existing environment; it is not a portable installer. |
| Python application | Install the repository package and call `prepare_context` before the existing model client | The application must replace the original history with the prepared messages, adapting them to its provider's format. |

The repository is private, so downloads require access or a copy shared by a collaborator. First-time dependency installation needs network access. TOMC preparation needs no extra model key or GPU; the assistant still uses its own model account.

## What passed?

| Package or client | Verified result | Scope |
|---|---|---|
| Current Codex preview.4, desktop-bundled CLI 0.160.0, 2026-10-04 | Permanent native installation in the personal profile and two real default-model chats passed | Four TOMC calls; preparation and recall used the new default budget; the separate new chat had no history or expected values; GUI installation untested |
| Archived Codex preview.3 published ZIP, CLI 0.146.0 and desktop-bundled CLI 0.159.2, 2026-10-02 | Non-mutating preflight and full marketplace/plugin installation passed on both hosts | Five actual-host tools, temporary preparation, Unicode persistence across host restart and deletion; no model calls |
| Codex preview.1 ZIP, CLI 0.146.0 | Marketplace registration and plugin installation completed; the actual host discovered five tools | Fresh, isolated Codex configuration; no model call in this installation test |
| Windows desktop-bundled Codex 0.159.2, preview.1 runtime | Real model preparation, saving and recall passed; a separate fresh model chat recalled the saved notes without receiving the history | Existing default model and login, temporary MCP settings and separate synthetic database |
| Claude Desktop preview.1 and preview.2 bundles | Official MCPB 2.1.2 manifest validation and extracted, locked stdio runtime checks passed | Package/runtime tests; no Claude Desktop GUI installation or model conversation |
| Claude Code 2.1.287, preview.2 runtime | The separately merged report records user-scope registration and tool calls in fresh headless sessions | Explicit preparation, cross-session save/recall and deletion; VS Code interactive panel untested |
| Cursor preview.1 environment | Fresh `.[mcp]` installation and the generated link's exact launch target passed | Runtime tests outside the checkout; no Cursor GUI confirmation or model conversation |
| Codex preview.2 published ZIP, CLI 0.146.0 and desktop-bundled CLI 0.159.2 | Full installer completed marketplace registration and plugin installation on both hosts; each actual app-server discovered five tools | Fresh, isolated configurations; preparation, Unicode save/recall, full host restart and deletion passed; no model calls |

The runtime checks covered all five tools, Chinese and emoji text, notebook isolation, persistence after process restart, duplicate save retries and exact deletion. Direct preparation left the notebook database empty. The [validation record](validation.md) provides the dated scope of each test; the [sanitized evidence summary](validation_data/windows_installation_20261002.json) records package hashes and receipt provenance.

The preview.2 follow-up used the original published ZIP, not the working checkout. Its SHA-256 was `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e`, matching the release and sidecar. Unlike the earlier configure-only check, this ran the complete installer. It needed no direct namespace override for host discovery and direct MCP calls; it did not test model-selected use. Existing dependency caches were reused, so its elapsed time is not a cold-install performance result. One initial attempt failed because the test script had not created its isolated configuration directory; correcting the test script required no package change.

The [archived preview.3](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.3) was downloaded separately and retested on both Windows hosts on 2026-10-02. Its 90,444-byte Codex ZIP has SHA-256 `8db8ac312d6dd5e8b07a28cc66f98027a852fbec5de447ba682363acc9bf9a10`, matching the sidecar and release digest. `--check` left `mcp.json` unchanged; full installation with explicit `--uv`/`--codex` paths passed on the first attempt. The updated helper printed both plugin and marketplace removal commands. No override was needed for direct host tool checks; that trial made no model calls. Its Claude MCPB was byte-identical to preview.2.

## Claude Code's separate Windows trial

The [merged Claude Code record](validation.md#claude-code-windows-validation) reports five fresh headless sessions with the profile's default model. Explicit `prepare_context`, saving, recall in a new session without the history, and deletion passed. One control that did not name TOMC answered from the full history without calling the tool. The final model call to `list_memories` was blocked by the trial allowlist; the stdio check discovered all five tools.

This prose example selected six relevant source lines without typed records. Its preparation estimates were 2,085 → 101, and notebook recall was 2,090 → 101, for memory text under the lexical counter. These are not whole-request or billed-input measurements. The report's US$0.27 and US$0.13 session costs come from different workflows and do not establish a cost saving. TOMC source IDs start at `u0` and differ from labels already written into a history. See the [Claude Code guide](assistant_plugin.md#claude-code) for usage and Windows notes.

That server was registered persistently at user scope and still launches from its trial directory. Removing or moving that directory would break its registration. The original model transcripts were not archived in this repository; this summary cites the merged report, rather than claiming a new independent model trial. Interactive VS Code panel use and macOS/Linux remain untested.

## Archived Codex diagnostics, 2026-10-02

**The CLI on PATH and the desktop engine were different versions.** The npm CLI 0.146.0 could install the plugin, but two real model requests were rejected with HTTP 400 for the profile's default model and ChatGPT authentication. The desktop-bundled 0.159.2 engine completed the tests using the same model and login. Installation success therefore did not establish model access for that older CLI.

**The earlier minimal desktop probe needed temporary direct tool exposure.** A model turn without the override completed without access to TOMC. Successful preview.1 trials temporarily set `features.code_mode.direct_only_tool_namespaces=["mcp__tomc"]`. This was a diagnostic setting, not a permanent change or a general installation recipe. The 2026-10-04 preview.4 native installation passed model tool use without that override.

Across the model diagnostics, seven turn requests yielded four successful turns and eight TOMC calls, two older-host rejections, and one completed turn without TOMC access. The compilation example produced the expected FastAPI/Flask states. Its memory text estimates were 93 → 45 under the lexical counter; these are not API-billed token counts.

## What was fixed, and what still needs work?

Earlier packaging checks found that the tested host did not load the portable root manifest or provide plugin-root variables. The compatibility manifest and installer-generated absolute runtime paths address those recorded launch failures. The current Windows runtime tests found no further compiler or persistence defect requiring a source change.

This documentation update adds Windows commands that use the environment's Python directly, so virtual-environment activation is unnecessary. It also explains how to select the intended Codex executable with `--codex`, and separates successful registration from tool and model checks. See [manual setup](assistant_setup.md) and the [Codex installation guide](assistant_plugin.md#codex).

**Windows demo resource decoding is fixed.** We reproduced the Claude Code report's six test failures with Python 3.11.9 using Windows cp936. The tour read a UTF-8 snapshot as GBK; two existing test files also read UTF-8 resources with the platform default. The three demo resource readers and two test files now specify UTF-8. At that revision, both the default-codepage and UTF-8-mode runs passed all 126 tests. This fixes the local demo and resource checks without changing core compilation, plugin code, resource contents or the published packages. No global environment setting is required. See the [repair record](validation.md#windows-encoding-fix).

After integrating the Linux and macOS updates on 2026-10-02, both Windows encoding modes passed 141 tests out of 142 collected; one POSIX executable-permission check is intentionally skipped on Windows. Rebuilt local packages matched the archived preview.3 release hashes. Those checks covered the combined code changes and packaging, without adding a GUI or model trial.

The current installer retains the prerequisite check, explicit executable paths and uninstall instructions introduced in preview.3. Run `uv run --no-project --python 3.12 install.py --check` before installation; it checks the package and required commands without registering TOMC. Windows native installation and default-model tool use are now verified for the stated preview.4 host. Remaining usability work is to test the desktop GUI flows and reduce Cursor's setup steps. Check tool connection and a real call after installation; preflight alone does not establish that the model can call the tools.

The archived 2026-10-02 Codex tests used synthetic notes without permanently installing TOMC in the personal profile; their personal configuration and default notebook metadata stayed unchanged. The 2026-10-04 installation intentionally added the native plugin and is recorded separately above. Raw Codex diagnostic streams remain local because they include machine paths and host metadata. Repository summaries contain no credentials, personal notebook contents or thread identifiers.
