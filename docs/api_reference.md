# Python API

For a caller-controlled request loop, [AutomaticChatSession](context_ownership.md) optimizes old message history every one/two logical requests using a cached model limit, with brief native-compaction cooldown. It does not install a client interceptor. MCP tools leave the active chat with the host. [Model capacities](model_context_limits_20261012.md).

## Prepare context before your API call

Put TOMC between your stored history and the next model request. `prepare_context` returns a prompt, messages and compilation details. Inspect what it retained, then send the prepared messages in place of the original history. Your model and SDK stay the same.

This example assumes that `history`, `task`, `client` and `model` already exist in your application. `client` supports the chat-completions interface; using it makes your usual model request.

```python
from tomc import prepare_context

prepared = prepare_context(history, task)
if not prepared.prompt:
    raise ValueError(prepared.note)  # increase the budget before sending

# Inspect prepared.prompt and prepared.compilation.evidence before handoff.
response = client.chat.completions.create(
    model=model,
    messages=prepared.messages,
)
```

**Replace the history for this request.** Appending the result to the original history adds input. Preserve your application's required instructions, and keep the original history separately for details omitted by preparation. For other text APIs, map `prepared.messages` to the provider's input format, or use `prepared.prompt`. No model weights change. The bundled `APIReader` below supports chat-completions-compatible HTTP endpoints.

TOMC can reduce request input when a long history contains material the next task does not need. The saving depends on the history, task and retained records. Short histories can stay unchanged; records and framing can make a request larger. The memory budget is not a cap on the complete model request, and preparation does not guarantee that an answer retains its quality.

The MCP plugin exposes tools and does not intercept all API traffic. Calling the tool in an existing long chat does not remove that host's previous messages. A smaller request requires your application to adopt the prepared messages, or a new chat to receive the prepared text.

### Inputs, budget and inspection

`prepare_context(history, task, budget=None, *, adaptive=None, max_chars=None)` sets the memory budget to 60–80% of the history's lexical-estimate tokens when `budget` is omitted (80% for short histories, falling to 60% at a million tokens; at least 1,024, so short histories stay intact); pass an integer to set the memory budget directly. It accepts text, message JSON/JSONL text, a message list, or an object containing `messages`. Supported text blocks are `text`, `input_text` and `output_text`. Unsupported content blocks raise errors; input is limited to 200,000 characters.

For notes and documents, `adaptive` (default `None`, meaning automatic) may keep less than the budget when the task's evidence is unambiguous. TOMC then keeps the strongly matching lines, their headings and wrapped neighbours, the few lines that share their rare names or values (the next step of a two-step question), and a margin of further matches. It fills the budget as before when a task word is missing from the history, many lines match about equally, strong lines repeat one claim with different values, the task is in Chinese or another CJK language, or the matches are too large. Conversation histories, chat transcripts, notebooks and the request gateways always fill the budget. Pass `adaptive=False` to always fill, or `adaptive=True` to try it on a conversation. Typed records compile the same either way.

When an agent reads the prepared text as one tool or command output, the client may cut it: in one external test, Codex delivered a 20,000-character result intact but cut a 58,000-character one, and the answers that depended on the missing part were wrong. Pass `max_chars` (for example `20_000`) so TOMC keeps the most relevant memory within that many characters and a quarter as many estimated tokens. `prepared.compilation.diagnostics["delivery_limit"]` records the reduced budget. The CLI takes `--max-chars`; the MCP tools apply a limit by default.

Fitting histories stay intact. For longer input, the `hybrid` router selects `tomc_raw` for supported task routes and wording-sensitive questions, or `rag` for source retrieval. The budget covers memory under the lexical counter; the task and prompt framing add tokens afterward. `prepared.compilation` contains the detailed result. If no complete record fits, `prepared.prompt` is empty and `prepared.note` asks for a larger budget. This function calls no reader and writes no persistent memory.

Check `prepared.prompt` for the actual handoff text, `prepared.compilation.evidence` for selected sources, and `prepared.compilation.ledger` for derived records. Ledger rows can be omitted from the output; check their `included` field. The parser recognizes documented operations and uses lexical routing. Inspect the sources when the history contains paraphrases, implicit updates or unfamiliar formats.

### Measure the input you actually send

Compare the complete original and prepared requests using the same model, task and application instructions. Count the prepared records, selected source text, task and prompt framing. The default lexical counter is an estimate. `cl100k_base` below is one encoding, and may differ from your model's tokenizer or billing rules. Provider-reported usage, when available, is the measure of the billed request.

The memory-level statistics in `prepared.compilation.stats` do not include every request overhead. A smaller memory alone is not a measured reduction in API input, total cost or answer quality.

Run the included [API-input example](https://github.com/ZipengWu365/TOMC/blob/main/examples/api_context.py) without sending a model request:

```bash
python examples/api_context.py
# Optional BPE text counting:
python -m pip install -e '.[tokenizers]'
python examples/api_context.py --tokenizer tiktoken:cl100k_base
```

For the README's six-line migration history and 64-token lexical memory budget, the identical system/task framing yields 138 → 90 message-content tokens under the lexical estimate, or 147 → 108 under `cl100k_base`. Both paths count instructions and the task as well as history/memory text. Neither includes provider chat framing, tool schemas or hidden tokens. This synthetic example demonstrates request-text reduction; it is not billed usage or a general saving rate. The generated `messages` payload replaces the original history in the next request.

For local notebooks, see [assistant setup](assistant_setup.md).

## Prepare every turn from original history

Call `prepare_context` inside your request loop. Each call currently parses and compiles the supplied history again; it has no result cache or incremental compiler. When one conversation keeps every context it was given, `tomc.incremental.ContextUpdates(budget, max_chars=None).prepare(history, task)` sends the first context in full. Later calls send a short note when the source is unchanged, or only the lines shown earlier that now read differently or were deleted, and newly relevant lines, each with its headings. A full replacement is sent when compiled records change or the update would exceed 60% of a full context. `MemoryStore` preserves submitted records and also recompiles on recall. Keep original evidence separately: an item omitted for one task may be needed for a later task. Do not replace your stored history with `prepared.prompt`.

The [multi-turn API example](https://github.com/ZipengWu365/TOMC/blob/main/examples/api_multiturn.py) prepares each request, preserves explicit application instructions, sends only the prepared messages, and appends the actual task and answer to the original history after a successful response. Empty memory stops the request; a failed request leaves history unchanged.

```bash
# Offline: inspect two prepared requests; no model, key or network needed.
python examples/api_multiturn.py

# After setting TOMC_READER_API_KEY, TOMC_READER_BASE_URL and TOMC_READER_MODEL:
# Sends TWO potentially billable requests to your configured reader.
python examples/api_multiturn.py --live
```

The example compares message text with identical task and instruction framing, reports preparation/request latency, and keeps provider-reported usage separate from lexical estimates. The offline mode generates no answers and does not append simulated responses. The live mode is a usage example, not a controlled quality or cost comparison against full history.

This is a text-evidence workflow. Historical tool calls can be serialized as observations, but preparation does not preserve live tool-call IDs or provider-specific tool-result envelopes. Keep pending tool calls and their matching results in your application's native protocol. Pass required system/developer instructions separately as trusted application configuration; instructions embedded in historical evidence are not promoted to trusted roles.

Before adding incremental updates, distinguish retained source history/state from the budgeted memory sent on a particular turn. For result caching, include history revision, task, budget and compiler/tokenizer configuration in the cache key. Provider prompt caching is separate: compare reported cached/uncached usage and the applicable rates before claiming monetary savings.

## Control compilation

Use `compile_memory` to select a strategy, tokenizer and budget explicitly. Its default strategy is `tomc_raw`, which combines records with selected source text. Choose `tomc` to inspect the records-only mechanism.

```python
from tomc import compile_memory

result = compile_memory(
    messages="preference = tea\npreference = decaf tea",
    query="What is the current preference?",
    token_budget=256,
    strategy="tomc_raw",
    tokenizer="regex",
    input_price_per_million=1.0,  # illustrative caller-supplied price
    deterministic=True,
)
```

`messages` accepts text or a sequence of `Message`/mapping objects with string roles and content. JSON-serializable `tool_calls` become observations. Multimodal content, invalid inputs and unknown strategies raise errors. `token_budget` must be a nonnegative integer.

| Result field | Meaning |
|---|---|
| `compiled_memory` | Budgeted text intended for the reader |
| `ledger` | Candidate records, source IDs, derivation basis and inclusion status |
| `evidence` | Original lines supporting included records or raw text |
| `raw_fallback` | Source text included in the memory |
| `stats` | Token counts, retention, ratio, signed savings, latency, budget status and optional cost estimate |
| `warnings` | Parser, heuristic, budget and counting limitations |
| `diagnostics` | Selected strategy, routing reason, scope and kernel identity |

`to_dict()` returns a JSON-serializable result. `reader_messages(query)` builds provider-neutral messages and treats the memory as untrusted user data. Audit metadata is not included automatically.

The ledger can contain omitted records; check `included` before attributing a row to a reader request. Packing keeps whole records. A tiny budget can produce empty output, and `raw` deliberately ignores the cap. A null compression ratio means empty output; negative token savings mean the memory grew.

For BPE counting, install `.[tokenizers]` and select `tokenizer="tiktoken:cl100k_base"`. Initial setup may retrieve the encoding vocabulary; pre-cache it or use the offline regex counter. Neither counter includes provider-specific chat framing or hidden tokens.

## Optional HTTP reader

Set `TOMC_READER_API_KEY`, `TOMC_READER_BASE_URL` and `TOMC_READER_MODEL` in your shell. The base URL ends before `/chat/completions`. See `.env.example`; the library does not load environment files automatically.

```python
from tomc.adapters.reader import APIReader

reader = APIReader(timeout=30, retries=2)
response = reader.complete(
    result.reader_messages("What is the current preference?"),
    max_tokens=256,
    temperature=0,
    seed=42,
)
print(response.text)
print(response.usage)
```

`complete` makes a potentially billable request. Constructing the reader makes no request. Omit options such as `seed` if your provider does not support them. Usage fields come from the provider when available.

`response.usage` retains nonnegative integer `prompt_tokens`, `completion_tokens`, `total_tokens`, `prompt_cache_hit_tokens` and `prompt_cache_miss_tokens` when reported. It also retains nonnegative integer `*_tokens` counters inside `prompt_tokens_details` and `completion_tokens_details`, including `cached_tokens` and `reasoning_tokens`. Nested counters can be subsets of the totals; do not add them together as independent charges. Missing fields stay absent and missing usage returns `{}`. No cached usage, billing amount or saving is inferred. Malformed non-object usage raises a sanitized `ReaderError("invalid_response")` without retrying.

`ReaderError.category` distinguishes configuration, authentication, rate-limit, request, server, transport/timeout and malformed-response failures. Only rate-limit, server and transport failures retry. Redirects are refused, and error messages omit request and response details. A timed-out request may already have been billed.

## Add a strategy

Implement `CompressionStrategy.compress(history, units, query, budget, counter) → StrategyOutput` and pass the instance as `strategy`. Shared code enforces the budget and computes statistics.

Provide source references for derived records so users can inspect them. The optional `LLMLinguaAdapter` shows how to delegate to an installed compressor without loading a model on import. See [comparison with LLMLingua](comparison_with_llmlingua.md).
