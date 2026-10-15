# Method semantics

TOMC compiles memory before the reader is called. It executes defined operations on CPU, then combines source-linked records with selected text under a budget. It needs no training or auxiliary neural inference. The reader receives text through its existing API.

The paper defines STATE, RELATION, COUNT and RAW routes. This page describes the public adapters; [paper scope](paper_scope.md) distinguishes them from the frozen benchmark implementations.

## Supported operations

The reference parser recognizes normalized lines:

```text
A = 3
B copies A
A = 8
C copies B
```

SET writes a value. COPY reads the source's value at that point in the history. This example produces `A=8, B=3, C=3`: changing A later does not change B. Copies retain their supporting source chain. An undefined source produces `<UNKNOWN>`.

Relations use syntax such as `alice -[assigned]-> team` and `team -[owns]-> archive`. A query containing `relation: assigned > owns` requests that label sequence. The compiler joins its endpoints; it does not infer arbitrary graph transitivity.

COUNT records lexical occurrences and the number of supporting source units. In this adapter, its scope is all nonempty content lines, using the paper's English lexical tokenizer.

## Where matching can fail

The parser and router use explicit syntax and keyword rules. `preference = tea` is a supported assignment; a sentence such as “I might switch to tea” is source text, not a confirmed state update. Paraphrases, negation and ambiguous references need interpretation that these rules do not provide.

BM25 ranks source lines by lexical overlap, so it can miss synonyms or evidence connected through meaning rather than shared words. Routing can also select an unsuitable strategy. The source inspector shows what was retained and why; use it to check important updates and keep the original history for omitted details.

## Budget and audit behavior

Source IDs follow nonempty content lines in order: `u0`, `u1`, and so on. Original text, message roles and line positions remain available in the audit result.

The ledger lists candidate records before budget packing. Only rows marked `included` reach `compiled_memory`. Source evidence and the inspector are outside the memory budget unless their text is also packed into the memory.

| Adapter detail | Behavior |
|---|---|
| Typed operation scope | All normalized content-line operations, preserving historical COPY dependencies |
| Source selection | Line-level BM25, restored to source order after packing |
| `tomc` | Whole budget available for compiled records |
| `tomc_raw` | Starts with 42% for records, then uses remaining space for source text |
| Routing | Reference predicates, Chinese task cues and wording/semantic cues |
| Accounting | The selected counter is used for input, output and final budget validation |

The reference caps are 96 state rows, 80 count rows and 120 relation paths. Packing can omit complete rows. Tiny budgets can produce empty memory. The `raw` comparison deliberately ignores the cap and reports whether it was exceeded.

Default token counts are lexical estimates, including punctuation and individual CJK characters. Optional BPE counting requires an explicit encoding. Neither is a measurement of provider-billed chat input. Structured metadata can increase short inputs.

## Implementation sources

`src/tomc/_vendor/reference.py` is the preserved paper reference implementation. `SOURCE_PROVENANCE.json` records the origins and hashes of preserved research files.

The public TOMC adapter calls the reference state, relation and count kernels. Public input handling and whole-record serialization differ from the benchmark prompts.

The current API uses the paper's snapshot-copy semantics. `compile_memory` defaults to `strategy="tomc_raw"`, combining records with selected source text. Explicit `tomc` selects the records-only mechanism. Automatic context preparation retains fitting histories; for longer input, it uses `tomc_raw` for supported task routes and wording-sensitive questions, or `rag` for source retrieval.

## Runtime scope

For fixed input and configuration, built-in compilation is deterministic apart from measured latency. State replay and count accumulation are linear; BM25 scales with document length and query terms. Relation joins can grow with branching.

The interactive input limit is 200,000 characters. The demo does not establish million-token interactive latency, and optional reader calls or learned compressors have their own runtime behavior.
