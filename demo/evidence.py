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


def build_research():
    """Render the same verified evidence used by the repository report."""
    manifest = verify()
    gr.Markdown(
        "## Evidence from the paper\n\n"
        "**3 readers · 6 baseline configurations · 3 history lengths**\n\n"
        "**Same model, different context.** TOMC runs predefined operations on the history, "
        "then combines the resulting records with selected source text. "
        "It prepares this memory on CPU without training or auxiliary neural inference. "
        "Your existing model reads the result and answers.\n\n"
        f"Manuscript `{manifest['paper_commit'][:7]}` · synced {manifest['synced_on']}. "
        "These tables contain the paper's recorded measurements."
    )
    gr.Markdown(
        "### BEAM: quality and reader input\n\n"
        "TOMC has higher quality means in all **36 long-history comparisons (500K/1M)**. "
        "Overall reader-input savings average **34.77% vs LIGHT** and **34.35% vs "
        "hierarchical LLMLingua-2**. These are mean scores and reader-input measurements from the evaluated configurations."
    )
    tier = gr.Radio(
        TIERS, value="Overall", label="Original history length", elem_id="evidence-tier"
    )
    gr.Markdown(
        "**Each cell: Baseline / TOMC.** The two scores use the same reader and matched questions, "
        "with memory from the named baseline or from TOMC. "
        "Scroll sideways on narrow screens."
    )
    scores = gr.Markdown(beam_table(), elem_id="evidence-scores", elem_classes="evidence-table")
    tier.change(beam_table, inputs=tier, outputs=scores, api_name=False)
    gr.Markdown(beam_intro(), elem_id="evidence-notes")
    with gr.Accordion("Valid pairs and scoring protocols", open=False):
        gr.Markdown(protocol_text(), elem_classes="evidence-table")
    with gr.Accordion("RULER: which information does each task need?", open=False):
        gr.Markdown(ruler_text(), elem_classes="evidence-table")
    with gr.Accordion("BEAM: remove compilation, keep the same sources", open=False):
        gr.Markdown(ablation_text(), elem_classes="evidence-table")
    with gr.Accordion("Construction time and resource measurements", open=False):
        gr.Markdown(resources_text(), elem_classes="evidence-table")
    gr.Markdown(
        "### What this demo implements\n\n"
        "Try state updates, relations and counts with the example parser. "
        "The workbench's `rag` retrieves lines with BM25; the paper's BEAM-RAG uses BGE embeddings. "
        "The demo's `hybrid` chooses among local methods; historical Hybrid-RAG combines retrieval methods.\n\n"
        "[All lengths and ten memory abilities](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/RESULTS.md) · "
        "[Method and limitations](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md) · "
        "[Historical four-reader batch](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/HISTORICAL_BEAM.md)\n\n"
        "Run `make reproduce-results` to check file hashes and recalculate these tables locally. "
        "This uses the saved measurements and makes no API calls."
    )
