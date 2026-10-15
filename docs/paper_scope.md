# Paper and demo scope

The paper is **Task-Oriented Memory Compilation: Executable State Representations for Long-Context Language Models**. The product positioning was rechecked on 2026-10-02 against the latest local 20-page manuscript PDF. Its metadata date is 26 September at 09:53:13 UTC (10:53:13 in London). A fresh fetch confirmed that manuscript `main` still points to the older writing commit `7399657`; the result data were exported separately from that commit on 2026-09-28. [Writing review sources](WRITING_REVIEW_SOURCES.json) records these distinct authorities.

No public paper link or finalized citation is supplied here yet.

TOMC is a task-oriented context compression and representation method. Section 3.1 defines `Compress(M, q, B)`: history, task and budget in; a budgeted textual representation out. It selects evidence for a task, executes supported operations, then combines source-linked records with selected text. The reader model remains unchanged.

**TOMC 的核心是按任务压缩上下文并构建文本表示。** 它在调用模型前，编译受支持的状态、关系或计数记录，并结合选中的原文。编译器本身不保存历史；本地 notebook 是一个可选历史来源，MCP 插件提供调用入口。

## What gets compiled

| Route | Information retained |
|---|---|
| STATE | Current key–value state and snapshot-copy dependencies |
| RELATION | Endpoints joined along a requested sequence of relation labels |
| COUNT | Lexical occurrences and supporting source units within a declared scope |
| RAW | Selected original wording with source references |

The method follows `segment → select → route → compile → attach provenance → budget pack`. Compilation needs no training or auxiliary neural inference and changes neither model parameters nor KV caches. A source unit can be a line, sentence, message, table row or event.

The task determines which distinctions should survive. State replay is one example. Questions about explanations or exact wording can still require source text.

## What this repository implements

| Component | Role |
|---|---|
| TOMC reference kernels | State, relation and count operations using normalized syntax |
| Public compiler API | Input normalization, source inspection, strategy selection and whole-record packing |
| Benchmark adapters | Archived task-specific selectors, parsers and serialization behind the paper's experiments |
| `prepare_context` | Automatic selection and prompt handoff for an existing reader |
| Local MCP tools | Explicit save, recall, list and delete operations around a SQLite notebook store |

A [legacy compatibility extension](legacy_extensions.md) is documented separately. It is outside the paper and its evaluation.

The small demo parser and frozen benchmark adapters are different implementations of the representation approach. Paper scores describe those benchmark configurations. Accepting ordinary text in the demo does not establish arbitrary natural-language state extraction: short text stays intact, while longer text uses the documented rules and retrieval paths.

The compiler itself is stateless. Applications can supply histories from their own stores; the local MCP notebook is one implemented connection. See [assistant setup](assistant_setup.md) and [method semantics](method.md).

## Evidence sources

The current results cover three BEAM readers, six baseline configurations, three history lengths, RULER diagnostics and construction resources. [Paper results](paper_results.md) gives the numerical tables; [claims and limitations](claims_and_limitations.md) explains their interpretation.

`PAPER_SCOPE_SOURCES.json` records the reviewed manuscript source paths and SHA-256 hashes. `benchmarks/current_paper/manifest.json` records exported aggregate tables and approved figures. These exports contain neither manuscript PDFs nor benchmark questions and answers. `SOURCE_PROVENANCE.json` independently records the preserved research code.
