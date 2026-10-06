# Windows Codex: context budgets and actual input — 2026-10-05

[中文报告](codex_retention_20261005_zh.md) · [Recorded data](validation_data/windows_codex_retention_20261005.json) · [Budget tips](usage_tips.md#choose-budget)

All four conditions answered 45/45 latest-project-state questions correctly. Compared with full history, 40%, 60% and default 80% history budgets reduced reported request input by a mean paired 29.7%, 19.5% and 9.2%. Preparation used the installed TOMC MCP tool on CPU, followed by one answering turn in a new Codex chat.

## Overall results

Each condition has nine answering turns and 45 checked values. Input means are rounded to the nearest token; the JSON preserves unrounded means, each answer and its usage receipt.

| Context sent | Mean provider input tokens | Mean paired input reduction | Checked values |
|---|---:|---:|---:|
| Full history | 42,191 | Reference | 45/45 |
| TOMC · 40% history budget | 28,713 | 29.7% | 45/45 |
| TOMC · 60% history budget | 33,344 | 19.5% | 45/45 |
| TOMC · default 80% history budget | 38,035 | 9.2% | 45/45 |

For each history, reduction is `100 × (1 − prepared_input / full_input)`. The reported percentage averages those nine ratios equally. It is not the percentage change calculated from the two condition means; that would give longer histories more weight.

## Results by history length

Each length has three histories and 15 checked values per condition. The labels describe approximate history lengths under `cl100k_base`, not complete request input or TOMC's lexical budget count.

| History length | Context sent | Mean provider input tokens | Mean paired input reduction | Checked values |
|---|---|---:|---:|---:|
| ~10K | Full history | 29,023 | Reference | 15/15 |
| ~10K | TOMC · 40% budget | 23,195 | 20.1% | 15/15 |
| ~10K | TOMC · 60% budget | 25,160 | 13.3% | 15/15 |
| ~10K | TOMC · default 80% | 27,134 | 6.5% | 15/15 |
| ~20K | Full history | 38,846 | Reference | 15/15 |
| ~20K | TOMC · 40% budget | 27,258 | 29.8% | 15/15 |
| ~20K | TOMC · 60% budget | 31,220 | 19.6% | 15/15 |
| ~20K | TOMC · default 80% | 35,173 | 9.5% | 15/15 |
| ~40K | Full history | 58,705 | Reference | 15/15 |
| ~40K | TOMC · 40% budget | 35,687 | 39.2% | 15/15 |
| ~40K | TOMC · 60% budget | 43,651 | 25.6% | 15/15 |
| ~40K | TOMC · default 80% | 51,797 | 11.8% | 15/15 |

## What was tested

The answering reader was `gpt-6.1-sol`; Codex supplied the surrounding instructions, tools and session handling. The full-history control also kept TOMC and the other plugins installed. This is an evidence comparison within the same host, not a plugin-installed versus plugin-uninstalled comparison. [Paper readers and coding-agent hosts](readers_and_agents.md).

The Windows desktop-bundled Codex CLI was 0.160.0, using the existing `gpt-6.1-sol` model, OpenAI provider and `ultra` effort. Preview.4 was already installed in the actual personal profile. The three checked preparation sources (`easy.py`, `mcp_server.py`, `compiler.py`) matched repository commit `ad89208`. Personal configuration stayed unchanged; no feature, MCP or tool-namespace override was used. The harness gave every condition the same developer instruction to answer from supplied evidence without tools.

The corpus uses seeds 11, 23 and 37, each at 670, 1,340 and 2,700 chat turns. Histories contain ordinary prose updates and distractors. Five questions ask for the current deadline, page limit, evaluation owner, weekly meeting time and presentation venue. Lengths within a seed are nested. The 45 values therefore come from nine related histories and three seeds, rather than 45 independent projects.

For each history, the harness called the native MCP `prepare_context` tool outside the answering model. The 40% and 60% budgets were the history's lexical estimate multiplied by 0.40 or 0.60 and rounded down. The 80% condition omitted `budget`, exercising the unchanged `max(1024, ceil(history_estimate × 0.8))` default. Actual mean lexical evidence retention was 39.98%, 59.96% and 79.97%.

All 27 prepared contexts selected `tomc_raw` and contained source blocks, with no `STATE`, `REL` or `COUNT` records. The ordinary-prose histories exercised source-selection fallback; this test does not independently validate operation compilation.

Each full or prepared evidence packet then went into its own fresh ephemeral answering thread. All 36 answering turns completed, with no observed tool calls or model reroutes. Notebook saving and recall were not used. Asking an assistant to prepare or recall inside a chat adds model turns, which these single-answer figures do not include. Telemetry does not rule out hidden transport retries.

## How tokens and answers were checked

Input is the final Codex `inputTokens` count, including cached input, host instructions and available tool definitions. Cached input is a subset of this total and is not subtracted. No estimated host overhead is removed. `cl100k_base` counts in the JSON describe supplied text; they are not asserted to be the provider's tokenizer. `outputTokens` includes `reasoningOutputTokens`; both fields are recorded, and they must not be added together. This report makes no currency-cost or speedup claim.

Answers were checked against the generator's current values, with normalized strings and recognized page-cap paraphrases. The page-limit check tests the stated numerical value; it does not distinguish inclusive from exclusive limits. The JSON retains original grading alongside the checked values. These descriptive results cover synthetic latest-state questions with one model, not general coding ability or a guarantee that a smaller budget preserves every fact.

## Choose a budget

40% produced the smallest tested requests; 60% leaves more room for evidence. Both are options to compare with full history on your own tasks. The default remains 80%. Use [the Python example and MCP instructions](usage_tips.md#choose-budget) to set an absolute budget, then inspect retained evidence and check the answer.

The [Claude Code results](validation.md#claude-code-windows-validation) used Claude Opus 5.5 and a separate request workflow. Its approximately 20% default-input reduction should not be substituted for the Codex result.

## Reproduce the comparison

Check the published record offline first. This needs Python 3.11 or later, with no account, installed plugin, MCP host or model request:

```bash
python scripts/benchmarks/codex_retention_report.py --verify-published docs/validation_data/windows_codex_retention_20261005.json
```

It regenerates the synthetic corpus and checks history hashes, expected values, saved answers, usage accounting and aggregate arithmetic. It does not repeat the model experiment.

Use Python 3.11 or later, install `tiktoken`, and have the TOMC plugin installed in the Codex profile being tested. Replace the CLI placeholder with your desktop-bundled executable. The runner uses that profile's model, provider and effort; it does not set them. Generating the corpus is offline; the runner makes 36 answering turns plus CPU-only preparation calls.

```bash
python -m pip install tiktoken
python scripts/benchmarks/codex_retention_cases.py --output outputs/codex_cases.json
python scripts/benchmarks/codex_retention_run.py --cli "C:/path/to/desktop-bundled/codex.exe" --cases outputs/codex_cases.json --output outputs/codex_retention --concurrency 2
```

Run the commands from the repository root. Add `--resume` to the runner to continue completed results in the same output directory. The report helper's export mode (`--results`, `--cases`, `--output`) is specific to the recorded October 5 host; its provenance constants need updating for a different setup. The dated [recorded data](validation_data/windows_codex_retention_20261005.json) includes corpus and result hashes, per-case scores, budgets, retained-text token counts and provider usage; later reruns can differ.
