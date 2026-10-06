# TOMC and other memory tools

TOMC changes the representation of selected history before a reader answers. Token compressors choose which text or tokens to retain. Persistent memory systems add storage and retrieval across interactions. These functions can be used at different points in an application.

The upstream sources below were reviewed on 2026-09-08. Reviewed revisions and licensing notes are recorded in `THIRD_PARTY_LOCK.json`.

## Compilation and compression

| Method | What it retains or constructs | Conditioning | Reader-facing output |
|---|---|---|---|
| Raw | Complete input | None | Original input |
| Truncation | A contiguous span | Position | Kept span |
| Demo BM25 | Source lines | Query terms | Retrieved lines |
| LLMLingua | Contexts, sentences and tokens selected by a compressor | Prompt components; optional question/instruction | Compressed prompt |
| LongLLMLingua | Ranked contexts and selected tokens | Question | Reordered/compressed evidence |
| LLMLingua-2 | Tokens selected by a learned model | Task-agnostic | Selected text |
| TOMC demo | State, relation and count records; optional source text | Task route | Source-linked records and selected text |

The method distinctions follow the [LLMLingua](https://arxiv.org/abs/2310.05736), [LongLLMLingua](https://arxiv.org/abs/2310.06839) and [LLMLingua-2](https://arxiv.org/abs/2403.12968) papers. LLMLingua-2 is task-agnostic by default. TOMC's explicit state replay is limited to its supported operations.

The [LLMLingua README](https://github.com/microsoft/LLMLingua) makes its API easy to try with a short installation and compression example. TOMC likewise provides a small entry point and visible before/after memory. Its ledger adds source references and shows which records fit the budget. The [LLMLingua-2 experiment directory](https://github.com/microsoft/LLMLingua/tree/main/experiments/llmlingua2) separates compression from downstream evaluation; TOMC's benchmark reports are also separate from interactive compilation.

[Selective Context](https://github.com/liyucheng09/Selective_Context) uses a base model to estimate self-information for lexical units. It provides a Python interface and Streamlit demo. This repository includes neither its implementation nor unrun quality scores.

## Storage and agents

[Mem0](https://github.com/mem0ai/mem0) provides persistent memory with add/search operations. [Letta](https://github.com/letta-ai/letta) provides stateful agents and explicit memory management.

TOMC's core compiles a supplied history without storing it. The optional MCP integration adds a small local SQLite notebook store. An application could place a compiler between its memory store and reader, but Mem0 and Letta integrations have not been implemented or benchmarked here.

## What the paper compares

The paper evaluates LongLLMLingua, direct and hierarchical LLMLingua-2, BRIEF-Pro, BEAM-RAG and LIGHT with the same three readers. Each row pairs baseline-produced memory with TOMC-produced memory on matched questions.

[Paper results](paper_results.md) reports each paired comparison and history length. Overall equal-reader input savings are 34.35% versus hierarchical LLMLingua-2 and 9.32% versus LongLLMLingua. Savings vary by length and baseline. Direct LLMLingua-2 produces 200 empty memories at 1M; its low input therefore does not establish effective compression.

The results describe the archived evaluation configurations. The resource table includes a CUDA LLMLingua-2 implementation; it does not establish that LLMLingua-2 requires CUDA.

## Use the official LLMLingua adapter

The optional adapter calls an installed official compressor. It redistributes neither source nor model weights. LLMLingua's [MIT license](https://github.com/microsoft/LLMLingua/blob/main/LICENSE) and each selected model's license apply separately.

```bash
python -m pip install -e '.[llmlingua]'
```

This example initializes a model and may download weights:

```python
from llmlingua import PromptCompressor
from tomc import compile_memory
from tomc.adapters.llmlingua import LLMLinguaAdapter

official = PromptCompressor(
    model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
    use_llmlingua2=True,
    device_map="cpu",
)
result = compile_memory(
    "Your own long context",
    "Your task",
    128,
    LLMLinguaAdapter(official, variant="llmlingua2"),
)
```

For LLMLingua or LongLLMLingua, supply a compatible official causal compressor and select `variant="llmlingua"` or `"longllmlingua"`. The latter forwards the documented question-conditioned ranking and reordering options.

If official output exceeds the chosen TOMC counter's budget, the adapter reports additional clipping. The clipped output differs from the untouched official result. Without a configured compressor, it raises `AdapterUnavailable` instead of substituting another method.

See [data and licensing](data_and_license.md) for dependency and source records.
