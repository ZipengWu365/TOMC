<img src="assets/tomc_logo_20261002.png" alt="TOMC Memory" width="380">

# TOMC Memory

**English** | [简体中文](https://github.com/ZipengWu365/TOMC/blob/main/README_zh.md) · v0.3.1 research preview · MIT

**When a fact changes, only the latest version comes back.** TOMC Memory prepares a smaller, task-specific context from a long history or from notes you saved, on CPU, with each kept value linked to its source line. It works as an MCP server for Codex, Claude Code and other MCP clients, and as a Python API before your own LLM call.

After installing, say **"Try TOMC Memory"** to your assistant, or run `tomc try`.

## Start here

- [Install TOMC Memory](assistant_plugin.md): Claude Code, Codex, Claude Desktop, Cursor, TRAE, WorkBuddy; `tomc setup --write` and `tomc doctor`.
- [Before you use it](https://github.com/ZipengWu365/TOMC#before-you-use-it): what it does not do, what it stores, which clients are checked.
- [What changed in 0.3.1](release_notes_0.3.1.md) · [中文更新说明](release_notes_0.3.1_zh.md) · [0.3.0](release_notes_0.3.0.md)
- [Evidence and claims ledger](evidence.md): every number with its source, model, sample size and version, plus the negative results. [中文](evidence_zh.md)
- [Switch assistants](usage_tips.md#reuse-notebooks): save project notes in one client, recall them in another on the same computer.
- [Use before an API call](api_reference.md#prepare-context-before-your-api-call): send prepared messages in place of the original history.
- [Local demo](quickstart.md): see how TOMC prepares context, no model or API key needed.
- [Usage tips](usage_tips.md) · [中文使用技巧](usage_tips_zh.md)

## What it stores

The Python `prepare_context` helper is stateless. The MCP tools save notebooks only when you call `remember_memory`, and save prepared results only if you turn that on (`tomc settings --save-mcp-results on`). Everything stays in a local SQLite file. [Security and privacy](https://github.com/ZipengWu365/TOMC/blob/main/SECURITY.md)

## Understand the method

[Method semantics](method.md) explains state replay, relation joins, counts and budget handling. [Architecture](architecture.md) shows where the compiler sits between your history and your model. [Comparison with other tools](comparison_with_llmlingua.md) describes how compilation differs from token selection and persistent memory systems. [Context ownership](context_ownership.md) explains why TOMC leaves the active chat to the host.

## Read the evidence

[Evidence](evidence.md) collects the assistant trials, the v0.3.0 stale-value benchmark and the BEAM and RULER results with their conditions. [Paper results](paper_results.md) holds the paper snapshot tables (manuscript commit `7399657`). [Claims and limitations](claims_and_limitations.md) explains how to read them, and [Reproducibility](reproducibility.md) shows how to recheck the arithmetic offline with `make reproduce`. The paper is not public yet.
