# Validation record

These entries record checks performed on the stated revisions. They distinguish local software checks from benchmark reruns, hosted checks and human usability testing.

<a id="windows-codex-retention-20261005"></a>

## Windows Codex context budgets and provider input — 2026-10-05

Used the installed preview.4 native MCP tool and Windows desktop-bundled Codex 0.160.0 with the original `gpt-6.1-sol` model, OpenAI provider and `ultra` effort. The three checked preparation sources (`easy.py`, `mcp_server.py`, `compiler.py`) matched repository commit `ad89208`. Personal configuration stayed unchanged, with no feature, MCP or tool-namespace override. Every answering condition received the same synthetic-task developer instruction.

Nine synthetic histories use three seeds at approximately 10K, 20K and 40K `cl100k_base` history tokens. Each asks for five current project values. Lengths are nested within each seed; the 45 scores are correlated values from nine histories, not 45 independent projects. The native tool prepared context outside the answering model. The 40% and 60% conditions used absolute budgets calculated from the lexical history estimate; the 80% condition omitted `budget` and passed the unchanged default-formula check.

| Context sent | Mean provider input tokens | Equal-case mean paired input reduction | Checked values |
|---|---:|---:|---:|
| Full history | 42,191 | Reference | 45/45 |
| TOMC · 40% history budget | 28,713 | 29.7% | 45/45 |
| TOMC · 60% history budget | 33,344 | 19.5% | 45/45 |
| TOMC · default 80% history budget | 38,035 | 9.2% | 45/45 |

All 36 fresh ephemeral answering turns completed, with no observed answering tool calls or model reroutes. All 27 prepared contexts selected `tomc_raw`, retaining source blocks without state, relation or count records. This is a source-selection test on ordinary prose, rather than an independent validation of operation compilation. It used no notebook operations.

Input is the final provider `inputTokens`, including cached input, host instructions and tool definitions. Cache counts are not subtracted, and no estimated host overhead is removed. Savings average each history's paired ratio rather than taking a ratio of aggregate means. Answers were rechecked against current values; page-limit scoring checks the numerical cap but does not distinguish inclusive and exclusive wording. The record retains original grading and raw usage updates. The figures cover one answering turn per condition, not extra model turns for in-chat preparation or recall; telemetry cannot rule out hidden transport retries. No billed-cost, speedup or general coding-quality claim is made.

[English report with length groups and reproduction commands](codex_retention_20261005.md) · [中文完整报告](codex_retention_20261005_zh.md) · [Audited recorded data](validation_data/windows_codex_retention_20261005.json). The separate Claude Code measurements below retain their own model and request workflow.

A separate stateless call in the active Codex conversation returned correct assignment and copy states. Its [foreground receipt](validation_data/windows_codex_foreground_20261005.json) is a tool-connection check, collected no provider usage, and is outside the 36-turn comparison. It did not exercise graphical installation.

<a id="windows-codex-preview4"></a>

## Windows native Codex installation and model acceptance — 2026-10-04

Downloaded and checksum-verified the original preview.4 Codex ZIP (91,034 bytes, SHA-256 `96b05b516efadba2e6e7f691a8869365233aad5088e7a484d0c0e63b60a013b0`). Its preflight and full installer passed with the Windows desktop-bundled Codex CLI 0.160.0 and UV 0.12.22. TOMC remains installed and enabled as `tomc-memory@tomc-local` in the owner's actual personal Codex profile. The package and UV executable live under fixed `~/.codex/tomc/` directories. Cached preparation code, MCP code and the skill matched the downloaded archive.

Using the existing `gpt-6.1-sol` model and OpenAI provider, the first real model turn called `prepare_context`, `remember_memory` and `recall_memory`. A second, distinct ephemeral chat received only the notebook name and task, called `recall_memory`, and recovered `framework = FastAPI`, `backup_framework = Flask`. Both answers were correct. All preparation/recall calls omitted `budget`; a direct host check measured 1,534 lexical input tokens, budget 1,228 and memory 1,223. This exercises the new 80% default branch, without measuring billed usage or general answer quality.

All five installed tools connected. After a complete host restart, recall and exact deletion passed. The trial's attempt to select a separate database through the parent process's `TOMC_MEMORY_PATH` was not forwarded by Codex to its native MCP subprocess. The plugin therefore used the default `~/.tomc/memory.sqlite3`: its notebook list was empty before saving, only a unique synthetic notebook was added, and its exact deletion left zero entries, independently checked with read-only SQLite. Database metadata changed; no isolation or unchanged-database claim is made.

Installation added only TOMC's marketplace and enabled-plugin settings, preserving the model, other configuration and existing plugin settings. The subsequent model trial changed no personal configuration; authentication metadata was unchanged. No feature, MCP or direct-tool-namespace override was used, and other plugins were kept enabled. Trial app-server processes stopped; TOMC's permanent installation was retained. These checks used the desktop's CLI engine and did not exercise the graphical installation flow. [Sanitized acceptance evidence](validation_data/windows_codex_preview4_20261004.json) records the current result; earlier version-specific scopes below remain historical.

## Assistant preview.4 — 2026-10-04

`v0.1.0-assistant-preview.4` packages `main` at `386b616`, which keeps about 80% of the history when no budget is given (see [Default budget](#default-budget-keep-about-80)). Both bundles were built twice on Windows with identical digests:

| Preview.4 asset | SHA-256 |
|---|---|
| `tomc-memory-0.1.0.mcpb` | `3a961252c520578d32875157f225f7d861d50113c64db838179b9cd6c58a425c` |
| `tomc-memory-codex-0.1.0.zip` | `96b05b516efadba2e6e7f691a8869365233aad5088e7a484d0c0e63b60a013b0` |

The Claude bundle passed `scripts/plugin_smoke.py`. Both bundles were extracted to a path containing a space and launched over stdio with `uv run --locked`; without a budget each returned 7,195 for an 8,993-token history (80%), and explicit budgets, intact short histories and notebook recall behaved as expected. This package-build check did not run Codex preflight, model calls or GUI installation; the later Windows native acceptance is recorded above. The first upload's `.sha256` files had Windows line endings, which `sha256sum -c` on macOS and Linux reads as part of the file name; they were replaced with LF files and the downloaded release verified with `sha256sum -c`. The build scripts now always write LF checksum files.

## Archived preview.3 full installation on Windows — 2026-10-02

After syncing the macOS update `eae11ad`, freshly downloaded the published preview.3 assets and verified their sidecars and release digests. The Codex ZIP is 90,444 bytes, SHA-256 `8db8ac312d6dd5e8b07a28cc66f98027a852fbec5de447ba682363acc9bf9a10`; the Claude MCPB remains byte-identical to preview.2. Both Windows CLI 0.146.0 and desktop-bundled 0.159.2 passed the new `--check` without changing `mcp.json`, then completed native marketplace/plugin installation with explicit `--uv` and `--codex` paths in new isolated configurations.

Each actual app-server discovered five tools and passed temporary preparation, Unicode save/recall after complete host restart and deletion to zero SQLite entries. Both installations succeeded on their first attempt and printed complete removal commands. No model call, GUI interaction or personal-profile change was made; all trial processes stopped. The short-history preparation in this check retained raw text, and does not establish a new compression or quality result. Windows default model-selected use and personal permanent installation remain unverified. The [tracked evidence](validation_data/windows_installation_20261002.json) includes the new receipts, separately from historical preview.1 model and preview.2 installation checks.

The combined Linux/macOS/Windows code was checked with Python 3.11.9 in both Windows cp936 and UTF-8 mode: each run collected 142 tests, passed 141 and intentionally skipped the one POSIX executable-permission check. Both locally rebuilt packages matched the published preview.3 bytes and hashes. Source and log hashes are recorded in the same evidence summary; this follow-up does not replace the initial 126-test repair record below.

<a id="windows-encoding-fix"></a>

## Windows default-encoding repair — 2026-10-02

After syncing merged Claude Code revision `c2ac8f5`, reproduced its reported failures with Python 3.11.9, `-X utf8=0` and `PYTHONUTF8=0` set only in the test subprocess. The preferred encoding was cp936: 120 tests passed and six failed. The actual demo failure came from `demo/tour.py` reading a UTF-8 snapshot JSON with the default encoding; the other resource failures came from default-encoding reads in two existing test files.

The three demo readers (`tour.py`, `easy.py`, and the CSS reader in `app.py`) and two test files now decode the known UTF-8 resources explicitly. Existing full-suite checks passed under both cp936 and UTF-8 mode: 126 passed in each run. No tests were added. Core/MCP source, resource contents, frozen results and published preview.2 assets remain unchanged; both package digests were rechecked. User environment and personal configuration were unchanged, and no model call was made.

Local receipts and complete before/after logs are under `outputs/windows_utf8_feedback_20261002/`. The [tracked evidence summary](validation_data/windows_installation_20261002.json) includes the observed encoding, commands, result counts, source hashes and log hashes. This repair supersedes the default-codepage failure reported in the older Claude Code entry below.

## Windows full-install follow-up and usage guidance — 2026-10-02

The published preview.2 Codex ZIP was extracted into two fresh Windows directories containing spaces and Chinese characters. SHA-256 `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e` matched the downloaded sidecar and release digest. The ZIP's complete installer, without `--configure-only`, registered the marketplace and installed the plugin under isolated Codex CLI 0.146.0 and desktop-bundled CLI 0.159.2 configurations. Both actual app-server hosts discovered all five tools and passed temporary preparation, Unicode save/recall, complete host restart and deletion to zero SQLite entries. No namespace override was needed for those direct host calls.

These follow-up checks supersede the earlier preview.2 configure-only scope for CLI installation. They made no model call, GUI interaction or permanent personal-profile installation; default model-selected use remains unverified. Existing dependencies were cached, so no cold-install timing claim is made. An initial diagnostic attempt lacked its test configuration directory; correcting the test script required no package fix. Personal configuration content and default database metadata were unchanged, and all four trial app-server processes stopped.

The English and Chinese [installation feedback](windows_installation_feedback.md) separates client setup effort, successful installation/runtime/model checks, prior host failures and remaining usability work. The [usage tips](usage_tips.md) include concrete prompts, update order, source checks, request replacement, budget adjustment and optional notebooks. Both language examples prepared the expected state records offline; Python snippets parsed and relative links were checked. Manual setup now includes PowerShell commands that use the installed interpreter without activation, and the installer guide explains selecting the intended executable with `--codex`. Core/MCP source and published packages are unchanged.

The [sanitized evidence summary](validation_data/windows_installation_20261002.json) is tracked in this repository. It includes package hashes, observed versions and raw receipt hashes; raw streams containing machine paths remain local under `outputs/windows_installation_feedback_20261002/`, alongside the earlier model/package receipts. A hash identifies a retained receipt and is not an independent attestation of its claims.

## macOS installation improvements and preview.3 checks — 2026-10-02

Preview.3 adds `--check` for package/executable/plugin-command preflight, explicit `--uv` and `--codex` paths, actionable prerequisite failures and complete uninstall commands. Preflight checks the exact Codex commands used by installation before writing TOMC paths or registering the marketplace. The installation helper itself was run by the Mac's stock Python 3.9.6; UV supplies TOMC's compatible runtime. A real extracted ZIP in a path with spaces and Chinese characters passed `--check` without changing its existing `mcp.json`, then passed `--configure-only` without registering a plugin. The configured ZIP's MCP runtime exposed five tools and correctly prepared the FastAPI current value and Flask copy snapshot for a Chinese task. The extracted Claude bundle passed the locked runtime, Chinese-note, restart, isolation and deletion checks.

The smoke-check script now defaults its UV cache/Python-download directories to its disposable test root and respects explicitly supplied directories, including relative paths resolved before the subprocess changes working directory. It forwards only the selected runtime path variables rather than the caller's full environment. User-owned directories are not deleted by the smoke check.

All **142 tests** passed, including 14 added installer/environment regression cases and the two concurrently submitted archive-metadata cases. Ruff lint/format checks, strict MkDocs build, Python sdist/wheel build and frozen current/historical research-report verification passed. The CI configuration now includes macOS 14 runners and packaged MCP runtime checks; this local record does not assert that their future remote runs have passed. [Preview.3 check receipt](validation/macos-20261002-preview3.json).

The real native-plugin **model call and installation acceptance remain tied to preview.2** below. Preview.3 was checked through non-mutating installer probes, configuration-only setup and direct MCP runtime calls; it was not permanently reinstalled or subjected to a new model call. Codex/Claude Desktop/Cursor GUI installation and Claude Code on macOS remain unvalidated. The independent Windows Claude Code report is preserved in its own dated section.

## Downloaded preview.2 on macOS — 2026-10-02

Downloaded and SHA-256-verified the published `v0.1.0-assistant-preview.2` assets from commit `11071dae7bfb8fac488790bd0123ae823510718f`. The test machine ran macOS 26.3 (25D125), arm64, and Codex CLI 0.159.2. It initially had Python 3.9.6 and no UV on PATH; the trial provisioned temporary UV 0.12.22 and Python 3.12.14. TOMC requires Python 3.10 or later. The Claude bundle's separately managed runtime used Python 3.13.16. See the [original report](validation/macos-20261002-preview2.json), [local demo screenshot](assets/macos_demo_20261002.jpg), and [macOS setup/usage guide](macos_usage.md).

| Downloaded preview.2 asset | Verified SHA-256 |
|---|---|
| `tomc-memory-0.1.0.mcpb` | `83b1e3893d291e910f760d6f9ae091a692749e80a89bae8bb409d5e497b5528e` |
| `tomc-memory-codex-0.1.0.zip` | `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e` |

The downloaded ZIP installed and enabled as a native Codex plugin through its packaged `install.py`. A real model called the installed plugin's `prepare_context` tool with a 64-token lexical memory budget and correctly answered `framework = FastAPI`, `backup_framework = Flask`. The installed Codex MCP configuration exposed all five tools: `prepare_context`, `remember_memory`, `recall_memory`, `list_memories`, and `forget_memory`. Host checks passed Chinese-note storage, recall after a process restart, deletion and isolated database use.

The extracted Claude `.mcpb` passed locked stdio runtime checks for the same five tools, Chinese notes, restart recall, notebook isolation, temporary preparation, deletion, external database storage and a path containing spaces and Chinese characters. **Codex, Claude Desktop and Cursor GUI installation were not tested.** The Claude stdio result validates its runtime rather than its desktop installer; Cursor installation was not exercised in this macOS trial. Temporary installation followed by cleanup does not establish permanent personal-profile setup.

The API example reproduced 147 → 108 message-text tokens under `tiktoken:cl100k_base`, a 26.53% reduction with identical instructions and task. The selected method was `tomc_raw`; its payload retained computed state and supporting source text. The example did not make an API call. These counts exclude provider chat framing, tool schemas and hidden tokens and do not measure billed usage. The local browser at `127.0.0.1:7860` loaded, ran **Try demo**, and prepared the correct snapshot after a Chinese task was entered manually. Its message-text lexical estimates were 138 → 90 for the English task and 140 → 92 for the Chinese task; these are different counters and inputs from the BPE measurement.

All 126 tests passed in 12.87 seconds; Ruff lint passed, and all 103 checked files were already formatted. The plugin and local marketplace were removed after testing. The demo process stopped, temporary packages/runtimes/databases and newly created test caches were removed, and Codex configuration semantically matched its original state. No default `~/.tomc/memory.sqlite3` was created. User notebooks are not deleted by uninstalling the plugin.

This trial exposed setup friction rather than a compiler/runtime failure: an existing UV executable is required for the Codex ZIP, and the system Python was too old for TOMC. The installation guides now specify a compatible UV-managed interpreter, prerequisite checks, explicit UV/Codex executable paths, isolated trial storage and complete plugin/marketplace removal. These updated helper commands are a subsequent change; the measured hashes above remain the original preview.2 artifacts.

## Fresh Linux installation and downloaded plugins — 2026-10-02

A fresh checkout of `ac42b84` installed `.[demo]` on Ubuntu 24.04.5 x86_64 with UV-managed Python 3.12.13 and Gradio 5.49.1. The first system-Python `venv` attempt failed because `ensurepip` was unavailable; seeded UV recovered the partial environment. Dependency checks, local HTTP startup, the offline API example and real Chromium interactions passed. Browser checks covered preparation, clipboard contents, Chinese JSONL/Windows line endings, stale results, source inspection, workbench comparisons and research history selection at 1440, 390 and 320 px, without page overflow, page errors or external browser requests.

Actual preview.2 release downloads passed checksum/asset-digest and source-entry comparisons. Codex CLI `0.159.0-alpha.12.1` installed the native plugin in isolated settings, recognized its enabled skill and connected all five tools. Repeated installation and installation after moving its directory passed. Both extracted package runtimes passed Unicode notes, restart persistence, notebook isolation, temporary preparation and deletion. These checks made no model calls and did not change personal assistant settings; Claude/Cursor GUI acceptance and automatic model tool choice were not tested in this Linux run.

A second new environment passed the documented seeded-UV installation with `.[demo,mcp]`, dependency checks, imports, the offline example and decoded default/custom-store Cursor links. The installation guides now cover `python3`, seeded UV environments and missing `ensurepip`, with first-use and plugin-path tips. Both archive builders pin ZIP creator metadata; regressions compare complete bundles under simulated Windows/Linux defaults. Linux rebuilds now match the published preview.2 bytes and hashes exactly. Runtime, compiler, paper figures and frozen scores remain unchanged. [Linux installation and feedback](linux_validation.md) includes actual screenshots and a sanitized machine-readable receipt; prior Windows model checks remain separate below.

<a id="claude-code-windows-validation"></a>

## Claude Code in the VS Code extension — 2026-10-02

Downloaded `tomc-memory-0.1.0.mcpb` from `v0.1.0-assistant-preview.2`; its SHA-256 matched the published `83b1e3893d291e910f760d6f9ae091a692749e80a89bae8bb409d5e497b5528e`. The machine ran Windows 11 Pro with Python 3.11.9 and no system `uv`. uv 0.12.22 was installed in a trial virtual environment, and `uv sync --locked` installed the bundle's locked dependencies. A stdio client launched the server with the manifest command, listed five tools and called `prepare_context`.

Claude Code 2.1.287 was used through the VS Code extension's bundled CLI, because `claude` was not on PATH. The test machine ran Windows; only the file paths in the steps are Windows-specific, and the token and cost figures are reported by the Claude service rather than measured locally. At the owner's request, the server was registered persistently at user scope with `claude mcp add tomc-memory --scope user`, with `TOMC_MEMORY_PATH` pointing to a trial database. `claude mcp get` reported Connected.

**Models.** Every answer in this section came from Claude Code's default model, Claude Opus 5.5 (`claude-opus-5-5`). Claude Code also made small background calls to Claude Haiku 4.5 (`claude-haiku-4-5-20251001`); in the two sessions whose per-model usage was recorded, these cost US$0.003 and US$0.001, about 1–3% of each session. All reported costs include such calls.

Five fresh headless sessions (`claude -p`, the profile's default model) used a synthetic 80-turn history with six state updates among unrelated turns:

| Session | TOMC calls | Result |
|---|---|---|
| Task naming `prepare_context`, budget 120 | `prepare_context` | `tomc_raw`; no supported typed records in the prose, six relevant lines retained; 2,085 → 101 estimated tokens; correct deadline, page limit and owner |
| Same task without naming TOMC | none | Correct answer from the history in the prompt |
| Save notebook | `remember_memory` | Saved one entry |
| New session without the history | `recall_memory` | 2,090 → 101 estimated tokens; all three values correct |
| Delete notebook | `forget_memory` | Deleted one entry; `list_memories` was blocked by the trial's tool allowlist (the stdio check listed it) |

The first two sessions cost US$0.27 and US$0.13; the notebook sessions were not costed separately. Token counts are lexical estimates, not provider-billed tokens. In both runs with returned memory, the model noted that TOMC's zero-based source IDs differ by one from the history's own `u1` labels; the installation guide now explains this. The model did not call TOMC unprompted in the one trial above. Interactive use in the VS Code panel and Claude Code on macOS/Linux remain untested. Separately, under the default Windows code page, six demo and release tests fail with `UnicodeDecodeError`; with `PYTHONUTF8=1`, all 126 tests pass.

### Measured input tokens

A follow-up compared two fresh sessions answering the same task. Session A received the full history in its prompt. Session B received only the notebook name and task, called `recall_memory` with budget 120 and answered from the returned memory; both answers were correct.

| Measure | A: full history | B: notebook recall |
|---|---|---|
| History or memory text, `cl100k_base` tokens | 2,217 | 116 (−94.8%) |
| Input tokens of the answering request, as reported by Claude Code (input + cache creation + cache read) | 42,782 | 40,402 (−5.6%) |
| Requests in the session | 1 | 3 (tool loading, `recall_memory`, answer) |
| Total input tokens in the session | 42,782 | 119,638 |
| Session cost | US$0.121 | US$0.123 |

Each Claude Code request carries roughly 39,000 tokens of its own instructions and tool definitions, and the tool call added two requests, mostly served from cache. For a history of this size, TOMC therefore reduced the history text but not Claude Code's input cost. The reduction matters for much longer histories, or for API requests that send prepared context without this fixed overhead.

### Scaling with history length

An earlier version of this study fixed the memory budget at 120 lexical-estimate tokens and kept the same six relevant updates at every length. Its prepared context was therefore set by the budget rather than by the history, so it is replaced by the follow-up below.

The follow-up used synthetic team-chat histories of 670, 1,340 and 2,700 turns (9,970, 20,063 and 40,451 `cl100k_base` tokens; at most 170,092 characters). They tracked eight project values through 69, 126 and 236 natural-language updates, and also contained look-alike distractors from other projects, such as another deadline or page count, and varied small talk. One request asked five questions about the latest values, graded per question. Each history was imported as a notebook outside the model. TOMC selected `tomc_raw` in every case. Each cell is a single run with the profile's default model (`claude-opus-5-5`); costs are those reported by Claude Code.

API-style requests replaced Claude Code's system prompt with the messages' own system text and disabled built-in tools and MCP servers (`--system-prompt`, `--tools ""`, `--strict-mcp-config`). Cells give input tokens, cost and correct answers:

| History (`cl100k_base`) | Full history | TOMC, budget 1,024 | TOMC, budget 8,192 |
|---|---|---|---|
| 9,970 | 17,436 · US$0.169 · 5/5 | 2,688 · US$0.027 · 4/5 | 15,781 · US$0.148 · 5/5 |
| 20,063 | 34,292 · US$0.334 · 5/5 | 2,797 · US$0.029 · 2/5 | 15,960 · US$0.155 · 5/5 |
| 40,451 | 68,327 · US$0.628 · 5/5 | 2,789 · US$0.029 · 3/5 | 15,596 · US$0.143 · 5/5 |

In Claude Code with its default tools, the history pasted into the prompt was compared with `recall_memory` from the imported notebook. Cells give cost and correct answers:

| History (`cl100k_base`) | Full history in prompt | Recall, budget 1,024 | Recall, budget 8,192 |
|---|---|---|---|
| 9,970 | US$0.247 · 5/5 | US$0.141 · 4/5 | US$0.253 · 5/5 |
| 20,063 | US$0.400 · 5/5 | US$0.139 · 2/5 | US$0.249 · 5/5 |
| 40,451 | US$0.709 · 5/5 | US$0.137 · 3/5 | US$0.247 · 5/5 |

With budget 8,192, every answer was correct, and the saving grew with history length. API-style input fell by 9%, 53% and 77% and cost by 12%, 53% and 77%. In Claude Code, cost was unchanged at about 10,000 tokens and fell by 38% and 65% at 20,000 and 40,000 tokens. Budget 1,024 cut input by 85–96% but answered only two to four of the five questions. Every wrong answer was a value set by an earlier update of the same field; one of them, a deadline, also appeared in a distractor. The updates were prose, so TOMC kept them as selected source text rather than compiling them into state records, and a 1,024-token budget did not hold the latest update for every value. The full history answered every question correctly at every length; in this test TOMC reduced cost, not errors. These are single runs on one synthetic history per length.

### Budget as a share of the history

The same three histories and five questions were rerun as API-style requests with the budget set to 10%, 20%, 40% and 60% of each history's lexical-estimate length (8,993, 18,116 and 36,517 tokens). The share kept is the prepared messages' `cl100k_base` length divided by the history's. Cells give correct answers and the cost change against the full-history request above (5/5 at every length):

| Share of history kept | About 10K tokens | About 20K tokens | About 40K tokens |
|---|---|---|---|
| 10% | 3/5 · −85% | 3/5 · −87% | 4/5 · −88% |
| 20% | 4/5 · −74% | 4/5 · −78% | 5/5 · −80% |
| 40% | 5/5 · −56% | 5/5 · −58% | 5/5 · −59% |
| 60% | 5/5 · −39% | 5/5 · −42% | 5/5 · −41% |

Keeping 40% or more matched the full history at every length while cutting cost by 39–59%. At 10–20%, every wrong answer was again a value set by an earlier update of the same field; some of these values also appeared in distractors. The required share depends on how much of the history the task needs and on whether updates can be compiled into state records, so these thresholds apply to this synthetic task; they come from single runs.

### Default budget: keep about 80%

From this revision, `prepare_context`, `recall_memory` and the CLI keep about 80% of the history's lexical-estimate tokens when no budget is given (at least 1,024, so short histories stay intact), and the MCP instructions advise answering directly for histories under about 10,000 tokens. To choose the default, the realistic task was repeated with three generator seeds at each length (nine histories). Budgets of 50%, 60% and 70% were set explicitly; the 80% row used the new default without a budget argument. These API-style runs used Claude Code 2.1.288 and Claude Opus 5.5:

| Share of history kept | Correct answers | Input change | Cost change |
|---|---|---|---|
| 50% | 45/45 | −48.6% (mean) | −47% to −59% |
| 60% | 45/45 | −39.0% | −39% to −52% |
| 70% | 45/45 | −29.5% | −30% to −44% |
| 80% (default) | 45/45 | −19.8% | −22% to −37% |

The full history also answered all 45 questions. The largest cost changes come from one 40K-token history whose full-history request cost US$0.774, versus about US$0.63 for the other two, so input change is the steadier measure. The 80% default keeps a margin above every share that matched the full history here; these are synthetic histories with one model.

Saving a long history through the chat would require the model to repeat it as a tool argument, so the histories were imported outside the model.
## API-input product revision and assistant preview.2 — 2026-10-02

The English and Chinese homepages now lead with sending less context in the next LLM API request. They retain assistant installation as the main entry and add a visible Python API example. The application must send prepared context instead of the original history for that request; an MCP tool does not clear messages already held by its host. Savings depend on history, task, source retention, tokenizer and required instructions. Short histories can pass through, and additional records or framing can increase input. The paper's baseline/TOMC paired comparisons and frozen numerical results were left unchanged.

The default offline demo now uses the README's six-line API-migration history and 64-token lexical memory budget. Actual preparation selects `tomc_raw`, retains two snapshot-state records with source text, and reports memory estimates of 93 → 45. Counting all message contents under the same system/task framing gives 138 → 90 lexical-estimate tokens (34.78% reduction). The independently executed `examples/api_context.py --tokenizer tiktoken:cl100k_base` gives 147 → 108 message-text tokens (26.53%). Neither includes provider chat framing, tool schemas or hidden tokens; no billed usage, fixed saving rate or answer-quality claim follows from these counts. The optional BPE check used tiktoken 0.14.0 in the local validation environment. No reader call was made.

The demo keeps memory-only statistics separate, displays zero or negative input changes, and marks empty evidence as unusable rather than promoting a saving ratio. Real Chromium checks at 1440, 390 and 320 px exercised the new default, exact clipboard copying, source inspection, JSONL import, edited inputs, late responses, and existing workbench/research views. No page-level overflow, page errors or external browser requests occurred. Current desktop/mobile screenshots show this actual local demo. Reports are under `outputs/api_demo_ui_receipt_20261002.json` and the related browser outputs.

Preview.2 changes plugin descriptions, the Codex skill and MCP guidance to lead with `prepare_context`; notebooks are optional. Tools, return values, compiler algorithms and persistence behavior are unchanged. Two repeated builds had identical digests. The official MCPB 2.1.2 validator accepted the extracted Claude manifest. Real stdio checks exercised the extracted Claude bundle and configured Codex ZIP runtime, covering tool discovery, temporary compilation, Unicode notes, restart persistence, isolation and deletion. The packages share 35 byte-identical runtime files. Local receipts are in `outputs/api_plugin_preview_20261002/`.

| Preview.2 asset | SHA-256 |
|---|---|
| `tomc-memory-0.1.0.mcpb` | `83b1e3893d291e910f760d6f9ae091a692749e80a89bae8bb409d5e497b5528e` |
| `tomc-memory-codex-0.1.0.zip` | `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e` |

The dated Windows desktop model trials below used preview.1. During this product revision, preview.2 received package/runtime checks only; no model call or personal client configuration change was made. The later macOS entry above records preview.2 native CLI installation and a model tool call. GUI installation and permanent personal-profile installation remain unverified. The generated API-use illustration is conceptual, with its exact built-in generation prompt stored beside it.

## Manuscript-based product positioning — 2026-10-02

Both GitHub remotes were fetched again. Manuscript `main` remains `7399657`; its older PDF was not used as the writing authority. The author's records name the final local 20-page manuscript PDF, whose metadata and SHA-256 were reverified. The full paper and implementation appendices were read. Section 3.1 defines `Compress(M, q, B)`; Sections 3.2–3.4 explain supported task operations and records combined with selected source text.

The English and Chinese homepages now describe the context compression/representation package first. Assistant plugins remain the primary entry, direct `prepare_context` is the visible use example, and notebook storage is optional. The illustration follows history/task/budget to prepared context and the existing model. Its labels are conceptual, not measured results. The documented English/Chinese examples passed real stdio MCP calls: a 64-token lexical budget selected `tomc_raw`, retaining two snapshot-state records and source links without saving history. Scientific comparison text, frozen scores and runtime code remain unchanged.

GitHub-rendered Markdown previews passed at 1440, 390 and 320 px in both themes for both languages: 32/20 px header/subtitle, full-width figures, usable anchors and six expandable sections, with no page overflow or errors. Strict MkDocs also rendered the optional-storage guide headings and included its local image copies. This covers the Markdown body with an approximated repository frame, rather than live client GUI installation.

## Actual Windows Codex profile and model checks — 2026-10-02

The later model trial used the Windows desktop app's bundled Codex app-server 0.159.2 with the owner's existing profile, default `gpt-6.1-sol` model, OpenAI provider and ChatGPT authentication. It launched the original downloaded package runtime through temporary MCP settings and used synthetic text in a separate database. TOMC was not persistently installed in that profile. Personal configuration content, authentication metadata and the default notebook database metadata remained unchanged; all trial processes stopped afterward.

The README compilation example passed one real model turn and one model-selected `prepare_context` call. The six-line history exceeded its 64-token memory budget: the default lexical counter estimated 93 input tokens and 45 prepared-context tokens. TOMC selected `tomc_raw`, produced the two snapshot-state records (`framework = FastAPI`, `backup_framework = Flask`) with source references, and retained three source blocks. The model answered both values correctly. The database remained empty. These are estimates for the memory text, excluding the task and tool envelope, and one example does not establish benchmark quality or API-billed token savings.

A separate two-chat trial also passed. The first fresh model thread prepared, saved and recalled a synthetic history. A second distinct thread received only the notebook name and task, called `recall_memory`, and recovered all three expected values without receiving the original history or answer. Independent host calls verified persistence after a complete process restart and deletion down to zero entries. This short-history case retained raw text within budget; it tests optional storage and recall, rather than compression.

Both successful model trials required temporary direct exposure of the `mcp__tomc` tool namespace. Without that override, the minimal desktop host completed a model turn but did not make TOMC tools accessible. Two earlier model attempts through npm CLI 0.146.0 were rejected with HTTP 400 because that older host could not use the profile's default model with ChatGPT authentication. The desktop host supported the unchanged model and login. These observations do not establish default tool discovery, persistent/native plugin installation or the desktop GUI installation flow; Claude/Cursor model-driven use also remains untested.

Across these diagnostic attempts, seven model-turn requests yielded four successful test turns and eight TOMC tool calls, two older-host HTTP rejections, and one completed turn without TOMC access. The compiler itself made no neural inference calls. Local receipts are `outputs/plugin_user_trial_20261002/actual_profile_summary_20261002T165253Z.json` and `actual_compilation_summary_20261002T165627Z.json`, with the underlying item streams and independent database assertions retained alongside them. The temporary setting follows the [official Codex configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json); the real host was exercised through its [app-server protocol](https://learn.chatgpt.com/docs/app-server).

## Downloaded plugin checks on Windows — 2026-10-02

Downloaded the published assets from `v0.1.0-assistant-preview.1`, rather than testing only the working checkout. Codex ZIP SHA-256 `51fda9431f17013d3ce64effff185faa49825216e9d90dd7c27de60fddd4ebde` and Claude MCPB SHA-256 `a035690acfa9c7d0b6ce85af07678cdcb738971ea453ae8125436efdd2ccce2e` matched their sidecars and GitHub release digests. No package or runtime source fix was required.

The original Codex ZIP installed through `uv run --no-project install.py` under Windows Codex CLI 0.146.0. Its isolated app-server initialized all five tools. Calls through that real host saved Chinese notes, recalled them after a complete host restart, deleted the notebook and confirmed an empty list. Independent MCP checks also covered topic isolation and temporary preparation. The installation directory contained spaces and Chinese characters. Personal Codex configuration and notebook files were unchanged.

The original Claude bundle passed the official MCPB 2.1.2 manifest validator. Its locked UV runtime started from an extracted Windows directory with spaces and Chinese characters, installing its dependencies in isolation. Cursor used a freshly installed `.[mcp]` environment; its generated installation link decoded to the intended interpreter and database, and that exact configuration started outside the repository. Both runtimes passed five-tool checks, Unicode/emoji notes, restart persistence, notebook isolation, retry deduplication, preparation without saving, and exact deletion. Dependency checks passed.

Trial UV versions were 0.12.19 for Codex and 0.12.22 for Claude/Cursor, installed only in trial directories. The checks used synthetic notes and isolated databases, made no model calls, and did not alter personal client settings. GUI installation and model-selected tool use across clients were not tested. Local reports are under `outputs/plugin_user_trial_20261002/` and `outputs/claude_cursor_user_trial_20261002/`.

## Plugin-first homepage — 2026-10-02

The product header now uses a transparent horizontal TOMC logo, a 32 px functional heading and a 20 px short subtitle in GitHub's shared CSS. English and Chinese Markdown previews passed at 1440, 390 and 320 px in both light and dark modes. The logo displayed at 380 px on desktop and scaled to the phone text column without overflow; its blue wordmark remained visible in both themes. The updated landscape illustration filled the text column, all images loaded, and navigation and expandable installation sections remained usable. Byte-identical product images in `docs/assets/` were included in the strict MkDocs build. These checks cover the rendered Markdown body with an approximated repository frame, rather than a live GitHub repository page.

Both READMEs now lead with local project notebooks and assistant installation. A landscape, icon-led illustration shows explicit saving and recall in a new chat; the demo is a secondary context-preparation preview. The documentation overview follows the same order. The illustration is synthetic and does not establish a plugin performance result. Paper comparison prose, scores, figures and runtime source remain unchanged.

GitHub's official Markdown renderer retained the landscape figure, original-image link and expandable installation sections. Local previews using shared GitHub CSS were inspected at 1440, 390 and 320 px; the figure matched the 898/358/288 px text column, with no page overflow or browser errors. The same landscape asset is used at all sizes. Navigation targets matched GitHub slug generation and were exercised in the local preview; five expandable sections opened correctly. These are previews of the GitHub-rendered body, not live client screenshots.

## Homepage layout — 2026-10-02

The English and Chinese homepages give method and BEAM figures an explicit display width. The method overview follows the usage instructions; results precede strategy details. Platform installation steps, the mechanism example's Python code and maintainer links use expandable sections. The Space YAML configuration moved to a maintainer document so the GitHub introduction appears first.

GitHub's official Markdown API retained the image widths and expandable sections. Local previews using its shared CSS were inspected at 1440, 390 and 320 px. Both paper figures matched the text column: 898 px on desktop, 358/288 px on mobile. The original BEAM SVG displayed at 528 px on desktop. All five expandable sections opened normally, with no page-level overflow or browser errors. These are previews of GitHub-rendered bodies, not live repository-page screenshots.

The baseline/TOMC result prose and numbers remain unchanged. All 85 assets, benchmark files and core source files match the preceding homepage revision. Seven release and isolated Space-staging checks passed, along with Ruff and strict MkDocs. Space staging restores the same SDK/Python/entry-point metadata in a separate upload directory and checksums the resulting bytes; it leaves the GitHub README and inventory intact. The existing private Space was read-only verified as running and was not redeployed by this layout pass.

## Homepage installation and release checks — 2026-10-02

The English homepage now explains hosted and local demo use, Claude Desktop installation, Cursor registration, Codex CLI installation, Codex IDE MCP setup and a two-chat memory example. It links to the versioned assistant preview packages and checksums. The Chinese homepage mirrors these entry points. Hosted Space access is separate from private GitHub access, and the hosted deployment remains earlier than this local release.

GitHub's Markdown renderer retained the English entry table, client table, command blocks and four artifact/checksum links; the navigation targets match the rendered section headings. The scientific sections were unchanged. All 120 tests, Ruff and strict MkDocs passed. Both plugin packages still reproduce byte for byte from their current source, including the Codex package previously exercised in the actual host. This upload does not change repository visibility or deploy the Hugging Face Space.

## Codex installation candidate — 2026-10-02

Built the English `tomc-memory-codex-0.1.0.zip` candidate (87,997 bytes, SHA-256 `51fda9431f17013d3ce64effff185faa49825216e9d90dd7c27de60fddd4ebde`). Repeated builds produced the same hash. The package contains a local marketplace, the supported `.codex-plugin/plugin.json` compatibility manifest, a focused memory skill and the same runtime/lock bytes as the Claude candidate. It contains no personal paths or database. The installer generates absolute UV/runtime paths on the recipient's computer, optionally sets a separate database with `--store`, and registers the package through Codex commands.

Actual Linux Codex CLI `0.159.0-alpha.12.1` installed and enabled the extracted candidate in an isolated configuration. Its app-server recognized the namespaced memory skill and discovered all five real TOMC tools as connected. A separate MCP SDK client exercised that packaged backend for restart persistence, retry deduplication, Unicode recall, notebook isolation, temporary preparation, deletion and missing-notebook errors. Both host and SDK databases stayed outside the installation in temporary test locations. No model turn was started, no model credentials were supplied and personal client settings were untouched. Local receipts and the probe script are under `outputs/codex_plugin_probe/`.

Repeating installation and moving the extracted directory both passed. After the move, the marketplace, installed plugin source and cached MCP configuration referred to the new runtime path, and the actual host reconnected with the old directory removed. The new path also contained spaces and Chinese characters.

The tested CLI did not load MCP components from the newer portable root manifest and did not provide plugin-root variables to MCP subprocesses. The compatibility manifest and generated absolute paths address those observed launch failures. This is a test of the stated Linux CLI version, not every client version. The Codex IDE entry uses direct MCP configuration instead of native plugin installation. GUI installation and model-driven conversations remain untested.

All 120 tests, Ruff, strict MkDocs, skill validation, release scanning and wheel/source-distribution builds passed. This candidate remains local; it was not pushed, published or deployed.

## English default interface and plugin — 2026-10-02

The plugin name, installation description, tool descriptions, bundled README, primary assistant guides and default demo controls now use English. The Chinese installation guide is a separate optional page. Unicode history and paths remain supported, and existing bilingual example/size parameters are still accepted by the demo helpers.

Rebuilt the English installation candidate (83,586 bytes). Its source and extracted manifests passed the official MCPB 2.1.2 validator. The extracted locked runtime passed Chinese-note persistence, restart recall, isolation and deletion checks. All 119 tests passed. Real Chromium checks covered preparation, copying, stale responses, Chinese CRLF JSONL upload, source inspection and result filtering at 1440, 390 and 320 px, without page errors, external requests or page-level overflow. Updated desktop/mobile screenshots reflect the English interface. Ruff and strict MkDocs passed. This work is local; no hosted deployment or desktop GUI installation was performed.

## Assistant installation candidate — 2026-10-02

Built `tomc-memory-0.1.0.mcpb` (83,971 bytes) using the MCPB 0.4 UV runtime. The archive includes the existing TOMC source, a fixed MCP 1.30.0 dependency and a public-PyPI UV lock. It excludes the demo, experiments, local databases and virtual environments. Repeated builds produced identical SHA-256 hashes. The official `@anthropic-ai/mcpb` CLI 2.1.2 validated both the source manifest and the manifest extracted from the artifact; they matched byte for byte. The private candidate is unsigned.

A real MCP client launched the extracted bundle using its manifest command, in a fresh UV environment outside the checkout. It discovered all five tools, saved Chinese notes, restarted and recalled them, checked notebook isolation, prepared temporary text and deleted one notebook. The launch directory included spaces and Chinese characters; the database remained outside that directory. `scripts/plugin_smoke.py` reproduces these checks with synthetic data and no model calls.

Cursor install links decode to the same configuration as the existing setup command, including absolute interpreter and storage paths. Tests cover spaces, Chinese paths, unchanged manual configuration and rejection of a link request for other clients. The command prints configuration only; it does not open or edit a client. All 119 tests, Ruff checks, strict MkDocs and wheel/source-distribution builds passed.

Claude Desktop installation on macOS/Windows, Cursor GUI confirmation and model-driven tool selection remain untested. Runtime/protocol checks do not establish those product flows. No client configuration, model API service, repository visibility or hosted demo was changed. The candidate is prepared locally and has not been published to an extension directory or package registry.

## Exploratory demo use — 2026-10-02

Tested the latest GitHub main (`ea6b15e`) and the running private CPU Space (`1a8a236d72bb3523855290d813272988637dcfef`). Key entry/compilation files and release inventories matched. Real browsers completed preparation, exact clipboard copying, Chinese JSONL upload, source expansion, snapshot updates and result filtering. Anonymous Space access returned 404. All inputs were synthetic; no paid reader was called.

A late-result race was reproduced locally and online: an old prepared prompt could reappear after editing cleared it. The reviewed fix receives results privately in the UI and checks their submitted history, task and size before display. Editing clears visible output immediately in the browser. Queued submissions are cancelled; a completed stale response is ignored. A controlled two-second delay verified that an old result neither appeared nor cleared a newer valid result.

The same review adds one-click example preparation, task placeholders, Chinese validation hints and explicit recovery instructions when a long source line cannot fit even at the maximum size. Core algorithms and benchmark measurements are unchanged. All 108 tests and real-browser checks passed at 1440, 390 and 320 px, with no local page errors or external requests. The hosted test blocked optional platform metadata/fonts separately. The fix is prepared in a review branch; it is not a report of a new HF deployment.

## Paired-method comparison labels, 2026-10-01

The main BEAM tables now label every score pair `Baseline / TOMC`: the same reader answers matched questions using memory built by each method. This describes the measured pair, without asserting that the methods cannot be combined. API integration remains distinct from a combined memory-method experiment. The compilation ablation keeps its separate `Full TOMC / TOMC w/o compilation` labels.

All numerical values in the changed reports and prose match the preceding main commit `ae0ae13`. Frozen data and scientific figures were unchanged. All 106 tests, Ruff lint/format and strict MkDocs passed. Local browser checks passed at 1440, 390 and 320 px with the new labels; links and result anchors were verified. No benchmark or reader calls were made.

## Paper scope correction, 2026-10-01

Both GitHub remotes were fetched before this correction: demo `main` was `a1f93ca`, manuscript `main` was `7399657`. The manuscript's remote `main.pdf` has 28 pages; the final manuscript PDF has 20 pages and later writing changes. The final manuscript PDF is the writing authority. Neither PDF contains TOMC2. [Writing review sources](WRITING_REVIEW_SOURCES.json) records the commits and PDF hashes; the original exported-data provenance remains separate.

The API and CLI now default to `tomc_raw`, combining compiled records with selected source text. Automatic routing no longer invokes the archived software-trace adapter. The interface and launch prose cover the paper method; explicit legacy calls remain compatible through the separate compatibility page. Frozen kernels, input fixtures, research figures and measurements were unchanged.

All 106 tests passed, including default API/CLI state replay with source text, routing with coding cues, and source retrieval without legacy instructions. Ruff lint/format and strict MkDocs passed. Local Chromium checks passed at 1440, 390 and 320 px, with no overflow, page errors or external requests. The first-use examples, workbench choices and tour were inspected, and screenshots were refreshed.

## Demo writing review, 2026-10-01

The review covered both READMEs, the documentation, demo interface, generated result reports and launch drafts. It used the author's Manuscript Argument Audit, ARGUS and Nature polishing criteria to make the API handoff clear and remove empty or repetitive prose. The final manuscript PDF and frozen snapshot supplied the numerical claims.

All 104 tests, including a new release-inventory ordering regression check, Ruff lint/format checks and strict MkDocs passed. The current snapshot's original hashes and arithmetic passed; the main-table scores were checked against the previous report after reversing their display order to baseline / TOMC. Research kernels, routing, experiment IDs and frozen measurements were unchanged. README and launch examples reproduced the state records and source links.

Local Chromium checks passed at 1440, 390 and 320 px, including copying, JSONL upload, stale-output clearing, keyboard source expansion, compilation, comparisons and result selection. No page errors or external requests were observed. On Windows, the clipboard adds CRLF line endings; the check compares the copied text after normalizing line endings. Desktop and mobile screenshots were refreshed and inspected. The launch brief also passed at 1440 and 390 px.

Git attributes preserve the original bytes of hash-verified evidence, vendor sources and supplied figures across checkouts. Maintained text uses LF. Release entries use the same path order on Windows and Linux. The new `--brief-only` option refreshes launch prose without regenerating images.

GitHub and Hugging Face visibility were checked read-only and remained private. The Space was sleeping; this review made no reader calls, deployment, visibility change or promotional posts. Launch copy remains a draft.

## Manuscript synchronization, 2026-09-28

The writing checkout was synchronized to `7399657`. The demo uses its three-reader, six-baseline BEAM snapshot, separate repaired NIAH pair and updated construction measurements. The English/Chinese READMEs and research UI use the same aggregates. Historical four-reader Hybrid-RAG results remain separate.

All 103 tests, Ruff lint/format checks, strict MkDocs and package build passed. Current verification covered export hashes, paired score/input arithmetic, equal-reader and long-history aggregation, common-set ability means and repaired NIAH arithmetic. Historical statistical reconstruction also passed. These checks made no reader or judge calls.

Local Chromium checks covered context preparation, exact clipboard copying, JSONL upload, stale-output clearing, source expansion, state compilation, comparisons, history selection and resource-table display. Layouts at 1440, 390 and 320 px had no page-level horizontal overflow, browser errors or external requests. Wide tables scrolled inside their panels. Desktop/mobile captures and the method/BEAM figures were inspected.

The release uses the exact 300 KB overview PNG rather than its 9 MB SVG. Scans check file sizes, credential patterns and reachable Git history. This synchronization included no Hugging Face deployment or visibility change.

## Method and assistant integration, 2026-09-09

The paper-scope review aligned the READMEs, UI, figures, setup examples and launch drafts with task-oriented memory for long-context LLMs. It kept the historical TOMC2 software-trace adapter and new MCP integration distinct. Source hashes are in `PAPER_SCOPE_SOURCES.json`. Research kernels, compiler algorithms, routing defaults and frozen scores were unchanged.

The 102-test suite, Ruff checks, strict MkDocs and frozen BEAM reconstruction passed. It covered automatic handoff, notebook isolation, capacity rollback, concurrent appends and CLI configuration. JSON/JSONL and supported text-block imports had explicit errors for unsupported content.

A real MCP SDK client launched the stdio server, discovered tools, saved two notebooks, restarted, recalled one without mixing content, and deleted that notebook. Clients using protocol versions 2024-11-05 and 2025-03-26 initialized and made tool calls. GUI installation and model-driven tool selection in each assistant were not tested.

The official SDK 1.30.0 was pinned separately from the zero-dependency core. A fresh virtual environment installed `.[demo,dev,mcp]`, passed `pip check` and passed all 102 tests. This checked the shared Pydantic resolution on a clean installation.

Chromium checks at 1440×900, 390×844 and 320×740 covered clipboard contents, JSONL compilation, clearing old output after edits, source expansion, edited state compilation, comparison and assistant setup. The preparation button was visible without scrolling; no page errors or page-level horizontal overflow occurred. Synthetic workshop notes were used for the new default-screen captures.

## Project-page figures, 2026-09-09

The visual pass added the original mark, bilingual overview/snapshot/software-trace diagrams, narrow-screen variants and a BEAM plot. `assets/figure_data.json` records source hashes and synthetic outputs. The agent diagram uses included observations and checks that the shown verifier is omitted at the example budget.

GitHub's Markdown rendering API retained the expandable application examples and responsive figures in both READMEs. Its sanitized HTML was previewed locally at 1280, 390 and 320 px. Images loaded, narrow-screen variants were selected, and no page-level horizontal overflow occurred. Light and dark surrounding layouts were inspected. SVG text bounds were checked for clipping, and desktop PNGs were inspected.

These were local previews of GitHub-rendered fragments, not live GitHub-page screenshots. The existing 87-test suite and frozen-statistics reconstruction passed. The statistical graph retained bootstrap and missingness-expanded intervals and the nonsignificant Flash marker.

## Demo and launch materials, 2026-09-09

The guided tour, workbench and research page were checked with Python 3.12.13 and Gradio 5.49.1.

| Check | Recorded result |
|---|---|
| Core, demo and release suite | 87 passed, including provenance, short-input overhead, HTML escaping and omitted-row display |
| Chromium interactions | Three tour cases, keyboard source expansion, editor navigation, changed-input notice, edited compilation and comparison passed |
| First viewport | Compiled state card visible at 1440×900, 390×844 and 320×740 |
| Responsive layout | No page-level horizontal overflow at 1440, 390 and 320 px |
| Local browser requests | No external requests or page errors |
| Launch assets | SVG and 1280×640 PNG generated from actual snapshot output; PNG below 1 MB; HTML inspected on desktop/mobile |
| Synthetic quickstart | `examples/snapshot.py` returned drink=decaf tea and backup_drink=tea with source references |
| Documentation/style | Strict MkDocs, Ruff lint and formatting passed |

`make launch-assets` rebuilds the HTML and SVG. Install optional Playwright and Chromium, then run `python scripts/launch_assets.py --render` to render the PNG. The capture script reads the running demo. These assets show synthetic compiler operations, not generated reader answers.

Optional Node server-side rendering is disabled in both launch entry points. With Gradio 5.49.1, that proxy can send initial HTML before offline middleware removes stock CDN resources. Local and hosted compilation use the same client rendering path.

The private hosted demo was tested with requests outside its exact `hf.space` host blocked. Source expansion and edited-input compilation passed. Gradio still attempted optional `huggingface.co` metadata and Google-font requests, which were blocked and recorded. Hosted startup was therefore not classified as making zero external requests. The compiler itself made no reader calls.

No first-use study, propagation/conversion experiment or model-driven cross-chat evaluation was run. Those questions remain outside these engineering checks.

<a id="cross-assistant-notebooks"></a>

## Cross-assistant notebooks, 2026-10-08

On Windows, the installed Codex and Claude Code TOMC server commands were launched over MCP stdio with a test-only `TOMC_MEMORY_PATH` pointing to one synthetic SQLite database. Seven fresh processes completed eleven tool calls. Codex saved a state-copy history; Claude Code recalled the current FastAPI value and earlier Flask snapshot, appended a Starlette update, and a restarted Codex process read that update. The registered Claude Code preview.5 project entry also read the same notebook. Concurrent appends from both clients remained present after another restart.

The original saved message content was preserved exactly. This checked installed plugin-server interoperability and persistence, with no model calls or native GUI/chat handoff. The real client configurations and default databases were not modified. Clients sharing a database still need explicit save/recall requests; this is not automatic chat or cross-device synchronization. [Sanitized check record](validation_data/cross_client_memory_20261008.json).

中文：在 Windows 上，用已安装的 Codex 与 Claude Code 插件服务入口，通过 MCP stdio 在独立合成数据库中完成双向保存、读取、更新、重启和并发追加。7 个进程、11 次工具调用通过；原始笔记保留完整。没有调用模型或验证原生界面的自动接续，真实配置和默认数据库未改动。共享记忆本仍需显式保存、取回，以及一致的数据库路径。

## Initial staging, 2026-09-08

The initial checks used Python 3.12.13 and Gradio 5.49.1. The GitHub workflow was configured for Python 3.10 and 3.12.

| Check | Recorded result |
|---|---|
| Behavioral, integration, provenance and release tests | 84 passed |
| BPE budget sweep | 1,024 strategy/budget combinations passed with `cl100k_base` |
| Chromium | Compilation and side-by-side actions passed without JavaScript errors |
| Local offline startup | No external requests after removing optional stock CDN resources |
| Responsive layout | No page-level horizontal overflow at 1440 and 390 px |
| Packaging | Wheel/sdist built; isolated wheel import, compilation and bundled examples worked outside the checkout |
| Frozen BEAM reconstruction | Four configurations matched full-precision effects, intervals, p values and input reductions |
| Documentation | Strict MkDocs and local Markdown links passed |
| Release scanning | No findings in the reviewed inventory |
| API harness | Ten-request dry-run plan generated; no paid calls |

The screenshots used synthetic input. `scripts/browser_smoke.py` contains the browser checks and requires a separate Playwright installation. The presentation layer removes stock iframe-resizer CDN scripts and font preconnects while preserving packaged local JavaScript.

This revision did not test downloaded LLMLingua weights, live readers, private benchmark adapters or public deployment. The optional official adapter was tested for argument delegation with a mock; model accuracy and latency were not measured.
