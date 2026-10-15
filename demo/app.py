"""Offline memory workbench for local use and private Hugging Face Spaces."""

from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import gradio as gr
from starlette.middleware import Middleware

from tomc import STRATEGIES, compile_memory
from tomc.input import parse_history

from .easy import build_connect, build_easy
from .evidence import build_research
from .offline import OfflineHTMLMiddleware
from .tour import CASES, EXAMPLE_NOTES, render_tour

ROOT = Path(__file__).resolve().parents[1]
DEMO_STRATEGIES = tuple(strategy for strategy in STRATEGIES if strategy != "tomc2")
SCENARIOS = [
    json.loads(files("tomc").joinpath(f"data/{name}.json").read_text(encoding="utf-8"))
    for name in ("preferences", "constraints", "evidence", "snapshot")
]
BY_TITLE = {x["title"].split(" · ", 1)[0]: x for x in SCENARIOS}


def load_example(title: str) -> tuple[str, str, int, str, str]:
    """Load original sample content and its appropriate task configuration."""
    item = BY_TITLE[title.split(" · ", 1)[0]]
    return (
        json.dumps(item["messages"], ensure_ascii=False, indent=2),
        item["query"],
        item["budget"],
        "tomc_raw" if item["strategy"] == "tomc" else item["strategy"],
        EXAMPLE_NOTES[item["id"]],
    )


def parse_input(text: str) -> object:
    """Accept plain context, a JSON message list, or an object with messages."""
    if len(text) > 200_000:
        raise ValueError(
            "The interactive demo accepts up to 200,000 characters. Use the Python API for larger input."
        )
    return parse_history(text)


def compile_view(context: str, query: str, budget: int, strategy: str, price: float) -> tuple:
    """Compile locally and render measured output and its separate audit trail."""
    try:
        result = compile_memory(
            parse_input(context), query, int(budget), strategy, input_price_per_million=float(price)
        )
    except (ValueError, TypeError, KeyError):
        raise gr.Error(
            "Check the input: use plain text or JSON text messages, a nonnegative budget and price."
        ) from None
    stats = result.stats
    ratio = f"{stats.compression_ratio:.2f}×" if stats.compression_ratio is not None else "—"
    cards = [
        ("HISTORY", f"{stats.input_tokens:,}", "estimated tokens"),
        ("MEMORY", f"{stats.output_tokens:,}", f"{stats.retention_ratio:.1%} of history"),
        ("COMPRESSION", ratio, "input / memory"),
        ("COMPILE", f"{stats.latency_ms:.1f} ms", "local CPU; no model call"),
    ]
    metrics = (
        '<div class="metric-grid">'
        + "".join(
            f'<div class="metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>'
            for label, value, detail in cards
        )
        + "</div>"
    )
    state = [
        [
            r.kind,
            r.key,
            r.value,
            ", ".join(r.sources),
            "in memory" if r.included else "budget omitted",
            r.basis,
        ]
        for r in result.ledger
    ]
    evidence = [
        [u.source_id, u.role, u.message_index, u.line_number, u.text] for u in result.evidence
    ]
    route = (
        f"**{strategy} → {result.diagnostics['selected_strategy']} / {result.route}** · "
        f"{result.diagnostics['route_reason']}\n\n"
        f"Memory cost estimate at USD {price:g}/1M input tokens: "
        f"**${stats.estimated_input_cost_before:.6f} → ${stats.estimated_input_cost_after:.6f}**. "
        "This covers memory text only. The task, prompt overhead and answer add to the API cost."
    )
    warnings = "\n\n".join(result.warnings)
    return (
        result.compiled_memory,
        metrics,
        state,
        evidence,
        result.raw_fallback,
        route,
        warnings,
        result.to_dict(),
    )


def compare_view(
    context: str, query: str, budget: int, first: str, second: str, price: float
) -> tuple:
    """Run two actual offline strategies under the same measured budget."""
    try:
        data = parse_input(context)
        results = [
            compile_memory(data, query, int(budget), s, input_price_per_million=float(price))
            for s in (first, second)
        ]
    except (ValueError, TypeError, KeyError):
        raise gr.Error("Check the input JSON, budget and price.") from None
    rows = [
        [
            r.strategy,
            r.stats.input_tokens,
            r.stats.output_tokens,
            round(r.stats.retention_ratio * 100, 2),
            r.stats.latency_ms,
            r.stats.budget_compliant,
            r.stats.estimated_input_cost_after,
        ]
        for r in results
    ]
    return results[0].compiled_memory, results[1].compiled_memory, rows


def _build_workbench() -> None:
    """Build the complete editor, keeping the quick tour focused on one action."""
    example = load_example(SCENARIOS[0]["title"])
    initial = compile_view(*example[:4], 1.0)
    with gr.Row():
        scenario = gr.Dropdown(
            list(BY_TITLE),
            value=next(iter(BY_TITLE)),
            label="Choose an example",
            scale=3,
        )
        method = gr.Dropdown(
            list(DEMO_STRATEGIES), value=example[3], label="Compiler strategy", scale=1
        )
    note = gr.Markdown(example[4], elem_classes="scenario-note")
    status = gr.Markdown("Output matches the loaded example.", elem_classes="output-status")
    with gr.Row(equal_height=False):
        with gr.Column(scale=5, min_width=260):
            gr.Markdown("### 01 / Source history")
            context = gr.Textbox(
                value=example[0],
                lines=10,
                max_lines=24,
                label="Text or conversation JSON",
                elem_id="source-input",
            )
            query = gr.Textbox(value=example[1], lines=2, label="Current task / query")
            with gr.Accordion("Memory budget & cost estimate", open=False):
                budget = gr.Slider(0, 4096, value=example[2], step=16, label="Memory token budget")
                price = gr.Number(value=1.0, minimum=0, label="Your input price (USD / 1M tokens)")
            run = gr.Button("Compile memory  →", variant="primary", size="lg")
        with gr.Column(scale=7, min_width=260):
            gr.Markdown("### 02 / Compiled memory")
            metrics = gr.HTML(initial[1])
            memory = gr.Textbox(
                value=initial[0],
                elem_id="memory-output",
                lines=10,
                max_lines=24,
                label="Memory text to include in your model's prompt",
                interactive=False,
                show_copy_button=True,
                autoscroll=False,
            )
            with gr.Accordion("Routing & cost details", open=False):
                route = gr.Markdown(initial[5])
    with gr.Tabs():
        with gr.Tab("03 / State & ledger"):
            gr.Markdown(
                "Inspect the records and their sources. **Budget omitted** rows did not fit in the memory."
            )
            state = gr.Dataframe(
                value=initial[2],
                headers=["Kind", "Key", "Value", "Sources", "Packing", "Basis"],
                datatype=["str"] * 6,
                interactive=False,
                wrap=True,
            )
        with gr.Tab("Source evidence"):
            gr.Markdown(
                "Original lines used by the records or retained as source text. Only text in the compiled memory goes to your model."
            )
            evidence = gr.Dataframe(
                value=initial[3],
                headers=["Source", "Role", "Message", "Line", "Original text"],
                datatype=["str", "str", "number", "number", "str"],
                interactive=False,
                wrap=True,
            )
            fallback = gr.Textbox(
                value=initial[4],
                lines=6,
                label="Original text retained in memory",
                interactive=False,
            )
        with gr.Tab("Side-by-side"):
            gr.Markdown(
                "Compare the context each method produces. `raw` keeps the full history, including text beyond the memory budget. Answer quality is shown under Research evidence."
            )
            with gr.Row():
                first = gr.Dropdown(list(DEMO_STRATEGIES), value="tail", label="Method A")
                second = gr.Dropdown(list(DEMO_STRATEGIES), value="tomc_raw", label="Method B")
                compare = gr.Button("Compare methods", variant="secondary")
            with gr.Row():
                left = gr.Textbox(
                    label="Method A memory", lines=12, interactive=False, elem_id="compare-left"
                )
                right = gr.Textbox(
                    label="Method B memory",
                    lines=12,
                    interactive=False,
                    elem_id="compare-right",
                )
            comparison = gr.Dataframe(
                headers=[
                    "Method",
                    "Input est.",
                    "Memory est.",
                    "Retained %",
                    "CPU ms",
                    "Within budget",
                    "Input USD est.",
                ],
                interactive=False,
            )
        with gr.Tab("Export / JSON"):
            export = gr.JSON(value=initial[7], label="Result JSON, including original sources")
    with gr.Accordion("Parsing and token counts", open=False):
        warnings = gr.Markdown(
            "The record parser recognizes explicit operations such as `drink = tea` and `backup_drink copies drink`. "
            "Unfamiliar wording can be missed or misread. For prose and quotations, use `hybrid` or `rag` and inspect the retained text. Token counts are estimates."
        )
        gr.Markdown(
            "[Paper results and implementation limits](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md)."
        )
    gr.HTML(
        '<footer class="footer">TOMC · v0.1 &nbsp; <span>Prepare memory, then call your model.</span></footer>'
    )
    inputs = [context, query, budget, method, price]
    outputs = [memory, metrics, state, evidence, fallback, route, warnings, export]
    scenario.change(load_example, scenario, [context, query, budget, method, note]).success(
        compile_view, inputs, outputs
    ).success(lambda: "Output matches the loaded example.", outputs=status)
    for control in inputs:
        control.input(
            lambda: "Inputs changed. Compile again to update the memory, or rerun the comparison.",
            outputs=status,
            queue=False,
        )
    run.click(
        compile_view,
        [context, query, budget, method, price],
        [memory, metrics, state, evidence, fallback, route, warnings, export],
        api_name="compile",
    ).success(lambda: "Memory updated.", outputs=status)
    compare.click(
        compare_view,
        [context, query, budget, first, second, price],
        [left, right, comparison],
        api_name="compare",
    )


def create_demo() -> gr.Blocks:
    """Build an immediately usable tour with separate editing and research entrances."""
    theme = gr.themes.Base(
        primary_hue="emerald",
        secondary_hue="slate",
        neutral_hue="stone",
        font=["Arial", "sans-serif"],
        font_mono=["ui-monospace", "monospace"],
    )
    with gr.Blocks(
        theme=theme,
        css=(ROOT / "demo/style.css").read_text(encoding="utf-8"),
        title="TOMC · Task-oriented context compression",
        analytics_enabled=False,
        delete_cache=(3600, 3600),
    ) as app:
        gr.HTML(
            '<header class="masthead"><div class="brand">TOMC<span> / CONTEXT COMPRESSION</span></div>'
            '<div class="offline"><i></i> CONTEXT · CPU ONLY</div></header>'
            '<section class="hero"><div class="eyebrow">TASK-ORIENTED CONTEXT COMPRESSION</div>'
            "<h1>Send less history.<br><em>Keep task context.</em></h1>"
            "<p>Prepare context before your next API request. Keep the same model and compare "
            "estimated input tokens. No API key or paid model call is needed here.</p></section>"
        )
        with gr.Tabs(selected="use") as entrances:
            with gr.Tab("Use now", id="use"):
                build_easy()
            with gr.Tab("Connect your assistant", id="connect"):
                build_connect()
            with gr.Tab("30-second tour", id="tour"):
                with gr.Row(elem_classes="tour-controls"):
                    case = gr.Dropdown(
                        list(CASES), value=next(iter(CASES)), label="Explore a case", scale=3
                    )
                    own = gr.Button("Try your own history →", variant="primary", scale=1)
                story = gr.HTML(render_tour(next(iter(CASES))), elem_id="tour-story")
                case.change(render_tour, case, story, api_name=False)
                gr.Markdown(
                    "Try your own history in **Use now**, or read the paper's results under **Research evidence**. "
                    "These examples run the local compiler on sample data."
                )
            with gr.Tab("Workbench", id="workbench"):
                _build_workbench()
            with gr.Tab("Research evidence", id="research"):
                build_research()
        own.click(lambda: gr.Tabs(selected="use"), outputs=entrances, api_name=False)
    return app


if __name__ == "__main__":
    create_demo().queue(default_concurrency_limit=2, max_size=24).launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.environ.get("PORT", "7860")),
        share=False,
        ssr_mode=False,
        show_error=False,
        enable_monitoring=False,
        app_kwargs={"middleware": [Middleware(OfflineHTMLMiddleware)]},
    )
