# Python API

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

`prepare_context(history, task, budget=None)` keeps about 80% of the history's lexical-estimate tokens when `budget` is omitted (at least 1,024, so short histories stay intact); pass an integer to set the memory budget directly. It accepts text, message JSON/JSONL text, a message list, or an object containing `messages`. Supported text blocks are `text`, `input_text` and `output_text`. Unsupported content blocks raise errors; input is limited to 200,000 characters.

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

`ReaderError.category` distinguishes configuration, authentication, rate-limit, request, server, transport/timeout and malformed-response failures. Only rate-limit, server and transport failures retry. Redirects are refused, and error messages omit request and response details. A timed-out request may already have been billed.

## Add a strategy

Implement `CompressionStrategy.compress(history, units, query, budget, counter) → StrategyOutput` and pass the instance as `strategy`. Shared code enforces the budget and computes statistics.

Provide source references for derived records so users can inspect them. The optional `LLMLinguaAdapter` shows how to delegate to an installed compressor without loading a model on import. See [comparison with LLMLingua](comparison_with_llmlingua.md).
