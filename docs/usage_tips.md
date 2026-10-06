# TOMC usage tips

Start with the next question, rather than asking TOMC to shorten everything. The plugin prepares context for that task; your usual model answers it. You can use `prepare_context` without saving a notebook.

[Install the plugin](assistant_plugin.md) · [Python API](api_reference.md) · [中文使用技巧](usage_tips_zh.md)

## 1. Give it a specific next task

Include the names you need and the answer format in `task`. “What are the current framework and backup_framework values?” is more useful than “compress this chat.” For a coding task, mention the relevant component, constraints and unfinished work. For an explanation or quotation, say that the original wording matters.

After installing, copy this into your assistant:

```text
Call TOMC's prepare_context tool with:

history:
framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available.

task: What are the current framework and backup_framework values? Answer with one value per line, and state uncertainty if the evidence is missing.
budget: 64

Show the returned memory, note and warnings, then answer using that evidence.
Do not save this history to a notebook.
```

These are the actual tool arguments: `history`, `task` and `budget`. The requested answer format belongs in `task`; there is no separate answer-format parameter. The host decides whether to call the tool, so check that the response includes a TOMC tool result.

For Claude Code, name the registered server: “Use tomc-memory's prepare_context with this history, task … and budget 200.” The [Windows trial](validation.md#claude-code-windows-validation) passed with an explicit request; its one unnamed-task control did not call TOMC. See the [Claude Code setup](assistant_plugin.md#claude-code) if the tools are unavailable.

## 2. Keep the update chain and its order

Include earlier values, copies and later changes together. In the example, `backup_framework copies framework` takes the value at that point. Removing the initial Flask assignment loses the basis for the backup value.

Keep messages in chronological order and retain dates where available. The reference parser replays supported operations in input order; it does not sort them by date. Use consistent names for the same item. For confirmed structured facts, the supported forms include `framework = FastAPI` and `backup_framework copies framework`. Do not turn a suggestion such as “we might migrate” into a confirmed assignment.

For ordinary conversation, pass the original wording and describe the task clearly. The plugin can select source text, but it does not reliably infer every implicit update or alias. Keep the full history separately.

## 3. Use the result in the next request

In your application, send the prepared messages **in place of** the original history for that request:

```python
from tomc import prepare_context

prepared = prepare_context(history, task)
if not prepared.prompt:
    raise ValueError(prepared.note)

# Preserve any additional instructions your application requires.
response = client.chat.completions.create(
    model=model,
    messages=prepared.messages,
)
```

Here `history`, `task`, `client` and `model` are your application's existing inputs and chat-completions client. Other APIs require mapping the returned text/messages to their accepted format. This is a context-preparation step, rather than automatic compatibility with every SDK.

In an assistant, copy the prepared prompt from the demo into a new chat, then continue the task. Calling MCP inside an existing long chat does not remove that host's earlier messages. Appending prepared memory to the full history adds input; the tool call alone is not evidence of token savings.

<a id="choose-budget"></a>

## 4. Choose a budget by inspecting omissions

Without `budget`, TOMC keeps about 80% of the history's lexical-estimate tokens (at least 1,024); in the [Claude Code trial](validation.md#claude-code-windows-validation) this default answered every test question like the full history with about 20% less input. An explicit budget sets memory text under the lexical estimate. It does not cap the whole model request. The task, application instructions and provider framing add overhead.

The [Windows Codex comparison](codex_retention_20261005.md) tested the same nine synthetic histories with full history, 40%, 60% and default 80% history budgets. All four conditions answered 45/45 questions correctly. Mean paired request-input reductions were 29.7%, 19.5% and 9.2%. A 40% budget is the smaller option tested here; 60% leaves more room for evidence, and 80% remains the default. Check these choices on your own tasks before relying on the smaller budget. This trial used source selection for ordinary prose, rather than compiled operation records.

The Python API takes an absolute budget. To try 60% of the history estimate:

```python
from tomc import prepare_context

probe = prepare_context(history, task)
history_tokens = probe.compilation.stats.input_tokens
prepared = prepare_context(history, task, budget=int(history_tokens * 0.60))
# Use 0.40 to try the smaller tested budget.
```

Both preparation calls run on CPU; neither makes an LLM call. The MCP tool also takes an absolute `budget`, with no `retention_ratio` argument. Read `input_estimated_tokens` from its default preparation result, multiply by 0.40 or 0.60, round down to an integer, and pass that value as `budget`. To keep the default, omit `budget`; it uses `max(1024, ceil(history_estimate × 0.8))`.

Prepare the same task with a generous budget first, inspect the retained facts, then lower the budget while checking what disappears. Whole records must fit. If the memory is empty, increase the budget before handing it to a model. If important evidence is absent, provide the original passage or use a larger budget.

Short histories that already fit stay intact. That is expected behavior, and no compression is claimed. Source labels and instructions can also make small requests larger.

## 5. Check the evidence when names or meanings are tricky

The reference implementation uses explicit operation syntax and lexical rules. Different names for the same person, synonyms, negation and implied changes can cause missed evidence or an unsuitable route. A bigger budget does not make the parser understand an unsupported update.

Read the returned `memory`, `note` and `warnings`. For a detailed audit, use the demo's **Workbench** or the Python result:

```python
print(prepared.prompt)
print(prepared.compilation.ledger)
print(prepared.compilation.evidence)
```

Ledger rows are candidates; only rows with `included=True` reach the memory. Check both the included records and selected source text, then return to the original history if a key fact is absent. The MCP reply does not include the full ledger or source inspector. Source links help inspection; they do not prove that every relevant passage was retained.

TOMC assigns source IDs from `u0`, the first non-empty line. Labels such as `u1:` already written in your history remain part of its text; they are not TOMC's IDs. Use the returned source text to resolve the mapping rather than assuming those two numbering systems match.

## 6. Use notebooks only for material you want to reuse

Choose one notebook per project/topic, such as `api-refactor`, and save constraints, confirmed decisions and unfinished work you need in a later chat. Installation does not automatically collect your conversations.

Copy these prompts when needed:

| Action | Prompt |
|---|---|
| Save | “Use TOMC's remember_memory to save this in api-refactor: keep public API routes and response fields unchanged. Pagination tests have not been written or run.” |
| Resume in a new chat | “Use TOMC's recall_memory for api-refactor. Task: remind me of the API constraints and unfinished testing before we continue. Budget: 1024.” |
| Find a name | “Use TOMC's list_memories to show the notebook names.” |
| Add a confirmed correction | “Append this confirmed update to api-refactor with remember_memory: framework = FastAPI. Preserve the earlier history; this is the latest confirmed framework.” |
| Delete | “Use TOMC's forget_memory to delete the exact notebook api-refactor.” |

`remember_memory` appends; it does not edit an individual old entry. Supply corrected values and their order explicitly, and check the next recall. `forget_memory` deletes the entire named notebook and cannot undo that deletion through the tool. To replace a notebook completely, keep the wanted source material, explicitly request deletion of that name, then save the replacement.

Notebooks store submitted text as plaintext. Clients using the same database share them, and uninstalling the plugin does not delete that database. Use direct `prepare_context` when you only want a one-time preparation.

## 7. Measure the request, then check the answer

Compare original and prepared requests with the same model, task, application instructions and preparation budget. Count all text you actually send, including the task and memory framing. Keep the model's answer settings the same when comparing answers.

The tool's `input_estimated_tokens` and `memory_estimated_tokens` cover history/memory under a lexical estimate. They do not include the complete host request. For a repeatable local example, run:

```bash
python examples/api_context.py
# Optional BPE message-content counting:
python -m pip install -e '.[tokenizers]'
python examples/api_context.py --tokenizer tiktoken:cl100k_base
```

The example holds the system instruction and task constant and uses a 64-token lexical memory budget. `cl100k_base` counts one encoding's message content; your model may use another tokenizer. Provider framing, tool schemas and hidden tokens are excluded here. Check provider-reported usage when assessing the request's billed input.

Try representative tasks and check whether the prepared evidence still supports the answer. Smaller input alone does not establish better answers or lower total cost. Paper results and this plugin workflow have different evaluation scopes; there is no fixed saving rate for every history.
