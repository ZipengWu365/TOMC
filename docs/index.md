<img src="assets/tomc_logo_20261002.png" alt="TOMC" width="380">

# TOMC documentation

TOMC prepares context before your next LLM API call. Give it a history, a task and a memory budget. It selects source text and computes supported state, relation or count records. Send the result in place of the full history to reduce the input your model receives. Preparation runs on CPU without training or an extra model service.

Install the plugin in Codex, Cursor or Claude Desktop, or use the Python API in your application. It processes only supplied content. Savings depend on the input and task; short histories can stay unchanged, and records plus prompt overhead can increase a request.

<a href="assets/plugin_usage_api_20261003.png">
  <img src="assets/plugin_usage_api_20261003.png" alt="Install TOMC in Codex, Cursor, Claude Desktop or Claude Code. Supply history, task and budget; TOMC prepares context for the same assistant." width="1280">
</a>

## Start here

- [Install TOMC](assistant_plugin.md): choose Codex, Cursor or Claude Desktop.
- [Prepare context](assistant_plugin.md#prepare-context): supply history, task and budget through the installed tool.
- [Use before an API call](api_reference.md#prepare-context-before-your-api-call): replace the original history with prepared messages using your existing client.
- [Manual MCP setup](assistant_setup.md): register an installed environment in your client.
- [Usage tips (English)](usage_tips.md): choose a task, check sources and use the prepared context in your next request. [中文使用技巧](usage_tips_zh.md).
- [Windows installation feedback](windows_installation_feedback.md): preview.4 native Codex installation, real model calls and earlier client checks.
- [Windows Codex input comparison](codex_retention_20261005.md): full history versus 40%, 60% and default 80% history budgets. [中文报告](codex_retention_20261005_zh.md).
- [See the demo](quickstart.md): inspect how TOMC prepares context for an assistant.
- [Python API](api_reference.md): add context preparation to an existing application.

The demo illustrates context preparation and does not create persistent notebooks across chats. It needs no model or API key. Short histories stay intact. Longer histories use rule-based routing to combine compiled records with source text, or retrieve relevant lines. The parser supports defined operations; it does not extract reliable state from arbitrary prose.

## Understand the method

[Method semantics](method.md) explains state replay, relation joins, counts and budget handling. [Architecture](architecture.md) shows where the compiler fits between your history and reader. [Comparison with other tools](comparison_with_llmlingua.md) describes how compilation differs from token selection and persistent memory systems.

The paper studies task-oriented memory representations. The local notebook store supplies histories to the compiler through MCP. [Paper scope](paper_scope.md) explains how the demo and benchmark implementations relate to the manuscript.

## Optional history storage

The compiler is stateless. The local notebook tools can save supplied notes in their original form and prepare them again on recall. Direct `prepare_context` calls do not save history. [Try two chats](assistant_plugin.md#try-two-chats) when you want that persistence.

## Developer API

Prepare the history, inspect the result, then send it to your existing model. `prepare_context` returns a ready prompt, messages and compilation details with records and sources.

The output is ordinary text. Use your own SDK for a text-based LLM API without changing model weights. Replace the original history for that request rather than appending the result. The included HTTP connector supports chat-completions-compatible endpoints; other providers use your own client and message format.

The MCP plugin exposes tools; it does not intercept every request or remove an active chat's existing messages. Using prepared context in a new chat can avoid resending the original history. Count the full request with the provider's tokenizer to assess savings; the default memory budget uses a lexical estimate and excludes prompt overhead.

## Measured Windows Codex input

With the original `gpt-6.1-sol` model and `ultra` effort in Windows Codex 0.160.0, all four conditions answered 45/45 latest-state questions across nine synthetic histories. Mean reported request input was 42,191 tokens for full history, 28,713 at a 40% history budget, 33,344 at 60%, and 38,035 at the unchanged 80% default. Mean paired input reductions were 29.7%, 19.5% and 9.2%.

These are single answering turns in new chats after preparation through the installed MCP tool. Input includes cached tokens, host instructions and tool definitions. All prepared contexts used source selection, without compiled operation records. Budget shares describe lexical history estimates; they are not percentages of the whole request or billed cost. [English report](codex_retention_20261005.md) · [中文报告](codex_retention_20261005_zh.md) · [Recorded data](validation_data/windows_codex_retention_20261005.json)

## Read the evidence

The [README paper explanation](https://github.com/ZipengWu365/TOMC#paper-explained) retains the manuscript title and figures. [Reader models and agent hosts](readers_and_agents.md) explains how the paper's API readers relate to Codex and Claude Code, and what the assistant tests measure. [中文说明](readers_and_agents_zh.md).

[Paper results](paper_results.md) reports the frozen three-reader BEAM comparisons, RULER diagnostics and construction measurements. The current snapshot comes from manuscript commit `7399657`. These are archived experiments, not scores produced by the interactive demo.

Use [claims and limitations](claims_and_limitations.md) to interpret the comparisons, and [reproducibility](reproducibility.md) to verify the exported arithmetic. Historical four-reader Hybrid-RAG results remain separate.
