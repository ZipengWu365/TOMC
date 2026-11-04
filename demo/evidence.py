"""Explore manuscript aggregates; no model calls or benchmark execution."""

import gradio as gr

from benchmarks.reproduce.current import (
    TIERS,
    ablation_text,
    beam_intro,
    beam_table,
    protocol_text,
    resources_text,
    ruler_text,
    verify,
)

_T = {
    "en": {
        "intro": "## Evidence from the paper\n\n"
        "**3 readers · 6 baseline configurations · 3 history lengths**\n\n"
        "**Same model, different context.** TOMC runs predefined operations on the history, "
        "then combines the resulting records with selected source text. "
        "It prepares this memory on CPU without training or auxiliary neural inference. "
        "Your existing model reads the result and answers.\n\n"
        "Manuscript `{commit}` · synced {synced}. "
        "These tables contain the paper's recorded measurements.",
        "beam": "### BEAM: quality and reader input (paper snapshot, 100K–1M)\n\n"
        "TOMC has higher quality means in all **36 long-history comparisons (500K/1M)**. "
        "Overall reader-input savings average **34.77% vs LIGHT** and **34.35% vs "
        "hierarchical LLMLingua-2**. These are mean scores and reader-input measurements from "
        "the evaluated configurations. The later 10M follow-up is not included here; these "
        "scores are not comparable with other projects' BEAM numbers.",
        "tier": "Original history length",
        "cell": "**Each cell: Baseline / TOMC.** The two scores use the same reader and matched "
        "questions, with memory from the named baseline or from TOMC. "
        "Scroll sideways on narrow screens.",
        "pairs": "Valid pairs and scoring protocols",
        "ruler": "RULER: which information does each task need?",
        "ablation": "BEAM: remove compilation, keep the same sources",
        "resources": "Construction time and resource measurements",
        "outro": "### What this demo implements\n\n"
        "Try state updates, relations and counts with the example parser. "
        "The workbench's `rag` retrieves lines with BM25; the paper's BEAM-RAG uses BGE embeddings. "
        "The demo's `hybrid` chooses among local methods; historical Hybrid-RAG combines retrieval methods.\n\n"
        "[All lengths and ten memory abilities](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/RESULTS.md) · "
        "[Method and limitations](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md) · "
        "[Historical four-reader batch](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/HISTORICAL_BEAM.md)\n\n"
        "Run `make reproduce-results` to check file hashes and recalculate these tables locally. "
        "This uses the saved measurements and makes no API calls.",
    },
    "zh": {
        "intro": "## 论文里的证据\n\n"
        "**3 个读者模型 · 6 种对照配置 · 3 种历史长度**\n\n"
        "**模型不换，只换交给它的上下文。** TOMC 先按固定规则处理历史，整理出记录，再配上挑出的原句。"
        "整个过程在 CPU 上完成，不需要训练，也不调用别的神经网络。答题的还是你原来的模型。\n\n"
        "论文版本 `{commit}` · 同步于 {synced}。下面的表格是论文里记录的测量值，保留英文原表。",
        "beam": "### BEAM：答题质量和输入量（论文快照，10 万到 100 万 token）\n\n"
        "在 **36 组长历史对比（50 万 / 100 万）** 里，TOMC 的平均质量分全部更高。"
        "交给读者模型的输入量平均比 **LIGHT 少 34.77%**，比 **分层 LLMLingua-2 少 34.35%**。"
        "这些是所测配置下的平均分和输入量。后来做的 1000 万补充实验不在这里；"
        "这些分数不能直接和其他项目的 BEAM 分数比。",
        "tier": "原始历史长度",
        "cell": "**每格：对照方法 / TOMC。** 两个分数用同一个读者模型、同一批问题，"
        "只是上下文分别来自对照方法和 TOMC。手机上可以左右滑动表格。",
        "pairs": "有效配对和评分方式",
        "ruler": "RULER：每类任务需要什么信息？",
        "ablation": "BEAM：去掉整理这一步，来源不变",
        "resources": "构建时间和资源占用",
        "outro": "### 这个演示实现了什么\n\n"
        "示例解析器能处理状态更新、关系和计数。工作台里的 `rag` 用 BM25 找原句；论文里的 BEAM-RAG 用 BGE 向量。"
        "演示里的 `hybrid` 在本地方法之间挑一个；论文里早期的 Hybrid-RAG 是把几种检索方法合起来。\n\n"
        "[全部长度和十种记忆能力](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/RESULTS.md) · "
        "[方法和局限](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md) · "
        "[早期四个读者模型的结果](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/HISTORICAL_BEAM.md)\n\n"
        "运行 `make reproduce-results` 可以核对文件哈希，并在本地重新算出这些表。"
        "它只用保存好的测量值，不调用任何 API。",
    },
}


def build_research(lang: str = "en"):
    """Render the same verified evidence used by the repository report."""
    t = _T["zh" if (lang or "").startswith("zh") else "en"]
    manifest = verify()
    gr.Markdown(
        t["intro"]
        .replace("{commit}", manifest["paper_commit"][:7])
        .replace("{synced}", str(manifest["synced_on"]))
    )
    gr.Markdown(t["beam"])
    tier = gr.Radio(TIERS, value="Overall", label=t["tier"], elem_classes="evidence-tier")
    gr.Markdown(t["cell"])
    scores = gr.Markdown(beam_table(), elem_classes=["evidence-table", "evidence-scores"])
    tier.change(beam_table, inputs=tier, outputs=scores, api_name=False)
    gr.Markdown(beam_intro(), elem_classes="evidence-notes")
    with gr.Accordion(t["pairs"], open=False):
        gr.Markdown(protocol_text(), elem_classes="evidence-table")
    with gr.Accordion(t["ruler"], open=False):
        gr.Markdown(ruler_text(), elem_classes="evidence-table")
    with gr.Accordion(t["ablation"], open=False):
        gr.Markdown(ablation_text(), elem_classes="evidence-table")
    with gr.Accordion(t["resources"], open=False):
        gr.Markdown(resources_text(), elem_classes="evidence-table")
    gr.Markdown(t["outro"])
