# Paper readers and coding-agent hosts

[中文说明](readers_and_agents_zh.md) · [Paper scope](paper_scope.md) · [Windows Codex measurements](codex_retention_20261005.md)

A **reader** is the model that receives the prepared context and produces an answer. A **harness** is the software around it: instructions, conversation history, tool execution and session management. Codex and Claude Code provide such a harness. The model chooses actions; the host runs tools and returns their results. See the official [Codex App Server documentation](https://learn.chatgpt.com/docs/app-server) and [Claude Code explanation](https://code.claude.com/docs/en/how-claude-code-works).

## Three uses of TOMC

| Setting | What receives TOMC's output | What the evidence covers |
|---|---|---|
| Paper API-reader experiments | GPT-5.1, Rednote preview and DeepSeek 4.1 Flash through their API clients | Paired memory comparisons, task diagnostics and construction measurements |
| Windows Codex answering test | The existing `gpt-6.1-sol` model inside Codex | Full history versus prepared evidence in one fresh answering turn |
| Native assistant tool use | The model in Codex or Claude Code, after the host executes the TOMC MCP call | Tool connection and use of returned evidence; a complete task needs its own evaluation |

The paper is titled *Task-Oriented Memory Compilation: Executable State Representations for Long-Context Language Models*. Its arXiv link will be added after upload. The reader names and logos in the paper figures identify the models evaluated there. Codex and Claude Code are additional integration environments; their names do not replace those reader labels.

## Can an assistant use TOMC while doing a task?

Yes. The assistant can request `prepare_context` with supplied history, the next task and a budget. TOMC prepares text on CPU and returns it through MCP. The model can then use the records and retained source text while answering or planning its next action. An application can also call the Python API before a model request, using the [existing API example](api_reference.md#prepare-context-before-your-api-call).

The [active Windows Codex conversation check](validation_data/windows_codex_foreground_20261005.json) returned the current `framework = FastAPI` and the earlier copied `backup_framework = Flask`, with two STATE records and their source text. It used a 64-token lexical memory budget and returned 45 estimated memory tokens. That verifies a supported state/copy example in the installed tool. It collected no provider usage and did not measure a coding task.

For a coding workflow, these records could carry a confirmed framework choice, a copied earlier configuration, or a project constraint into the next task. The demo parser needs its supported syntax for compiled operations; ordinary prose may instead retain relevant source passages. Inspect the evidence. Use prepared context in place of the full history in a later request or fresh chat; a tool call within an existing chat does not erase its earlier messages.

## Is the Codex comparison fair?

It is a controlled comparison **within one host**. Full history and the 40%, 60% and default 80% conditions used the same model, reasoning setting, installed profile, task and answering instructions. TOMC and the other plugins remained installed in the full-history control. The changed input was the evidence supplied to the answering model, rather than whether the plugin was installed.

Preparation ran through the installed MCP tool before the answering model started. Every answer used a new ephemeral thread with the same instruction to avoid tools; no answering tool calls were observed. Provider input includes the host instructions, available tool definitions and cached input. All four conditions recovered 45/45 current values, with mean paired answering-input reductions of 29.7%, 19.5% and 9.2%. [Protocol, answers and usage](codex_retention_20261005.md).

These results support context replacement for those synthetic questions. The prepared prose histories contained RAW passages without compiled operation records. They do not establish the token use of an entire coding-agent workflow or reproduce the paper's six-baseline, three-reader evaluation. Claude Code's measurements retain their own model and request protocol.

## What would a complete coding-task comparison measure?

A useful next experiment is a small framework-migration task with an unchanged public API and a fixed acceptance test. Start both conditions from the same repository snapshot, with the same model, common tool permissions, instructions and test cases. Check whether the resulting code satisfies the requirements.

Measure two designs separately:

- **Evidence replacement:** prepare context before the answering agent runs, then compare full and prepared history within the same host.
- **Native tool workflow:** let the agent call TOMC during the task and compare with the host's ordinary workflow. Record any difference in TOMC tool availability and include all preparation, recall, subsequent tool, compaction and sub-model turns in the usage total.

Report task success, total input and output, cache counts, model settings and the initial workspace. Cache input is a subset of input; reasoning output is a subset of output. A saved-input figure for one answering turn cannot stand in for the full workflow. This is a proposed next experiment, not a result already measured here.
