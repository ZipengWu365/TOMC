# TOMC launch drafts

These posts are drafts. GitHub and the Hugging Face demo are private; their links currently require access. Publish after the owner approves public release and the demo works without signing in. A public paper URL and PyPI release are still pending.

## One sentence

License for current launch material: TOMC is free to use under the MIT License, including commercially. Modification and redistribution are welcome; retain the copyright and license notice. Research citation is encouraged. Third-party dependencies and provider marks retain their own terms and ownership.

当前许可口径：TOMC 采用 MIT 许可证，允许免费商业使用、修改、二次开发与再发布；复制或分发时保留版权声明和许可证。欢迎试用、反馈、贡献与合作，研究使用欢迎引用。第三方依赖和提供商标识保留各自条款与权利。

EN: **TOMC is a CPU memory module for your existing LLM API.** It computes supported state updates, relations and counts, then gives the same model records and source text to answer from.

中文：**TOMC 是可以接在现有 LLM API 前面的 CPU 记忆模块。** 它先执行支持的状态更新、关系连接和计数，再把记录与原文交给同一个模型回答。

Short visual line: **CPU-built memory for the model you already use.**

## Developer post — English

You can use TOMC with the LLM API you already call. Give it a history and a question; it prepares memory on CPU and returns ordinary text for your existing reader. There are no model weights to load or reader parameters to change.

The tour starts with three operations: set `drink` to tea, copy it to `backup_drink`, then change `drink` to decaf tea. TOMC resolves the current value and the earlier copy before the model answers. You can open each state record to check its source.

The Python core has no runtime dependencies. The web demo also offers a paste-and-copy path. Its built-in parser handles explicit operations such as `key = value` and `B copies A`; free-form conversation needs the raw or retrieval paths, or a task-specific parser.

Demo: [TOMC Memory Workbench](https://huggingface.co/spaces/Zipeng365/tomc-agent-memory-demo)

## 开发者发布稿 — 中文

TOMC 可以接在你已经使用的 LLM API 前面。输入历史和当前问题，它在 CPU 上构建记忆，输出普通文本，再由原来的模型回答。接入时不需要下载模型权重，也不需要修改 reader。

Demo 从一个小例子开始：先设定 `drink = tea`，复制给 `backup_drink`，再把 `drink` 改为 `decaf tea`。TOMC 会先算出当前值和之前保留的副本；展开状态记录，还能找到对应的原始操作。

Python 核心包没有第三方运行依赖，网页也支持直接粘贴历史、复制准备好的上下文。目前内置解析器支持 `key = value`、`B copies A` 等显式操作；自由对话可走原文或检索路径，更复杂的状态抽取需要任务适配器。

试用入口：[TOMC Memory Workbench](https://huggingface.co/spaces/Zipeng365/tomc-agent-memory-demo)

## Developer code

After cloning the repository, install the core with `python -m pip install -e .`. This example builds memory locally:

```python
from tomc import compile_memory

history = "drink = tea\nbackup_drink copies drink\ndrink = decaf tea"
question = "What are the current drink and backup_drink values?"
memory = compile_memory(history, question, token_budget=256, strategy="tomc_raw")
print(memory.compiled_memory)
messages = memory.reader_messages(question)
```

With your existing Chat Completions client and selected `model`, the handoff is:

```python
response = client.chat.completions.create(model=model, messages=messages)
```

For another API, put `memory.compiled_memory` and the question into its own request format. The compiler is independent of the provider; the built-in HTTP connector supports Chat Completions-compatible endpoints. Calling a reader uses that provider's credentials and pricing. The offline demo calls no reader.

## 30-second recording

Record the running demo with the bundled synthetic snapshot. Keep the input, output and token-count note visible. The video has not been recorded.

| Time | Screen | Narration |
|---|---|---|
| 0–5 s | Show the history and question | “Keep your LLM API. TOMC prepares its memory on CPU.” / “继续用原来的 LLM API，TOMC 在 CPU 上准备记忆。” |
| 5–12 s | Show `drink = decaf tea` and `backup_drink = tea` | “The current value changed. The earlier copy kept tea.” / “当前值变了，之前的副本仍然保留 tea。” |
| 12–19 s | Expand the copy's source lines | “Each state record points back to its source operations.” / “每条状态记录都能追溯到产生它的操作。” |
| 19–25 s | Edit one assignment and compile again | “Change an input and inspect the new memory.” / “改一个输入，再看新记忆。” |
| 25–30 s | Show exported memory and the local quickstart | “Pass this text to your reader, or copy the prepared prompt.” / “把这段文本交给你的 reader，也可以直接复制提示词。” |

Use 1440×900 for the first recording and provide a transcript. The tiny snapshot may grow after adding source labels; it illustrates copy semantics. `assets/social_preview.png` is a still image.

## Show HN draft

Title: **Show HN: TOMC — CPU-built memory for your existing LLM API**

I built TOMC to move supported memory operations into a CPU step before an LLM answers. It can resolve explicit state updates, follow typed relations and compute counts, then return records and source text to your existing reader.

The demo lets you paste a history and task, inspect what was retained, and copy a prompt into your model. The tour shows a value changing after another variable has copied it. The Python package exposes the same compiler and returns plain text or chat messages.

The built-in parser expects explicit assignments, copies and edges. Its router and retrieval use lexical rules, so they can miss paraphrases or pick the wrong route. Raw evidence remains useful for questions about reasons or exact wording. The workbench uses synthetic inputs; the paper's archived benchmarks are linked separately.

I'd like to see small examples where the retained memory misses something needed for the task. Please use synthetic input rather than private conversations.

Demo URL after public release: [TOMC Memory Workbench](https://huggingface.co/spaces/Zipeng365/tomc-agent-memory-demo)

Check the [Show HN guidelines](https://news.ycombinator.com/showhn.html) before submitting. The current private Space is not ready for a public post.

## Research post — English

TOMC builds task-oriented memory on CPU for black-box LLM readers. It executes supported state, relation and count operations during construction, then combines the resulting records with selected source text under a token budget. The answering model stays the same.

On BEAM, we evaluated GPT-5.1, Rednote preview and DeepSeek 4.1 Flash over 100K–1M-token histories against six baseline configurations. TOMC has higher mean quality in all 36 reader–baseline–length comparisons at 500K/1M. Overall reader-input savings average 34.77% versus LIGHT and 34.35% versus hierarchical LLMLingua-2, with readers weighted equally.

The measured CPU construction stage averages 4.21 s/call across six replays. The measured per-call stages for BRIEF-Pro and LongLLMLingua take 47.94 and 72.07 s, respectively—11.4 and 17.1 times TOMC's stage time. These measurements exclude reader inference and keep stage boundaries; they are not end-to-end application speedups.

Each results cell is **Baseline / TOMC**. The same reader answers with memory built by the named baseline or by TOMC, using matched questions and scoring within each pair. The separate compilation ablation compares **Full TOMC / TOMC w/o compilation**, removing records and instructions while retaining source text and routing.

The companion demo exposes the reference operations and source links. Its parser and BM25 retrieval differ from the benchmark adapters. Gains vary by task and comparator: some abilities favor the baselines, token savings are not universal, and the direct LLMLingua-2 1M condition includes empty memories. Full results and protocols are available in the [result report](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/RESULTS.md).

`make reproduce-results` checks the saved aggregates and rebuilds the report. It also reconstructs the separate historical four-reader statistics. Rerunning model inference is a separate step; no private benchmark questions or API payloads are distributed here.

## 研究版发布稿 — 中文

TOMC 为黑盒 LLM reader 在 CPU 上构建任务记忆。它在构建时执行支持的状态更新、关系连接和计数，把结果记录与选中的原文结合在 token 预算内，再交给原来的模型回答。

BEAM 实验使用 GPT-5.1、Rednote preview 和 DeepSeek 4.1 Flash，比较六种 baseline 配置，历史长度为 100K–1M tokens。在 500K/1M 的 36 个 reader–baseline–长度组合中，TOMC 的质量均值都更高。三个 reader 等权平均后，整体输入比 LIGHT 少 34.77%，比分层 LLMLingua-2 少 34.35%。

CPU 构建阶段在六次回放中平均耗时 4.21 秒/次。BRIEF-Pro 和 LongLLMLingua 实测构建阶段分别为 47.94 和 72.07 秒/次，即 TOMC 的 11.4 和 17.1 倍。这些是同为每次调用的阶段时间，排除了 reader 推理；不能直接解释为完整应用加速。

主表按 **Baseline / TOMC** 排列。同一个 reader 分别使用该行基线构建的记忆和 TOMC 构建的记忆，每对使用匹配的问题和评分。独立的编译消融比较 **Full TOMC / TOMC w/o compilation**：移除记录及其指令，保留原文和路由。

配套 Demo 展示参考操作和来源核对，parser 与 BM25 检索和论文适配器有所不同。收益随任务和对照变化：部分能力 baseline 更强，输入节省并非处处成立，LLMLingua-2 直接版的 1M 条件还包含空记忆。完整数字、协议和解释见[结果报告](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/RESULTS.md)。

`make reproduce-results` 核对保存的聚合数据并重建报告，也会重建独立历史四 reader 批次的统计。重新调用模型做实验是另外一步；仓库不分发私有题目或 API payload。

## Replies to common questions

**Can I use my current API?** Yes. The compiler returns ordinary text, so you can add it to your current client's request. Chat Completions messages are provided as a convenience; other APIs use their own request format. This does not mean every provider has been tested.

**What does the main table compare?** It pairs baseline memory and TOMC memory using the same reader and matched questions. The baseline memory comes from the named method; TOMC constructs the other condition. API integration means using that context with your existing reader. Adding TOMC to another memory method was not evaluated in this table. The separate compilation ablation holds source text and routing fixed.

**How reliable is the string matching?** The built-in rules cover explicit operations, not arbitrary language understanding. They can miss synonyms or misroute a question. For example, the current English router can mistake `account` for a count query because it matches the substring `count`. Inspect the route and retained sources; use raw evidence or a task-specific parser when the rules do not fit.

**Can I paste an ordinary conversation?** Yes. Histories that fit the chosen memory budget stay intact; longer histories use the heuristic router and retrieval. Accepting prose does not mean the compiler extracted every state update from it.

**How does TOMC differ from LLMLingua?** TOMC computes records from supported operations and retains selected source text. Text compressors select text or tokens. The paper compares specific configurations; the [method comparison](../docs/comparison_with_llmlingua.md) explains their inputs and use cases.

**Why did the example get longer?** Record labels and source IDs add overhead. A small snapshot example can grow. The demo reports memory length under its selected counter; use your provider's accounting to measure an actual request.

**Does the demo measure answer quality?** It shows the memory the compiler produced. The linked benchmark report contains the archived reader-answer measurements and their evaluation conditions.

**How do I install it?** Clone the repository, then install `-e .` for the core or `-e '.[demo]'` for the UI. A PyPI release is pending.

## Examples of clear project presentation

[Mem0](https://github.com/mem0ai/mem0) shows memory being used in a chat client. [LLMLingua](https://github.com/microsoft/LLMLingua) puts an installation command and compressor input/output together. [LightMem](https://github.com/zjunlp/LightMem) links scenario tutorials and reproduction scripts. For TOMC, use a short integration snippet, an inspectable operation example and a direct results link. LightMem is a presentation reference here; it is distinct from the LIGHT baseline in our paper.
