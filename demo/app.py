"""Offline memory workbench for local use (a Hugging Face Space can also host it)."""

from __future__ import annotations

import base64
import json
import os
from html import escape
from importlib.resources import files
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import gradio as gr
from starlette.middleware import Middleware

import tomc
from tomc import STRATEGIES, compile_memory
from tomc.input import parse_history

from .easy import build_connect, build_easy
from .evidence import build_research
from .offline import OfflineHTMLMiddleware
from .tour import (
    CASE_LABELS,
    CASES,
    EXAMPLE_NOTES,
    EXAMPLE_NOTES_ZH,
    LIMIT_CASE,
    limits_note,
    render_tour,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_STRATEGIES = tuple(strategy for strategy in STRATEGIES if strategy != "tomc2")
SCENARIOS = [
    json.loads(files("tomc").joinpath(f"data/{name}.json").read_text(encoding="utf-8"))
    for name in ("preferences", "constraints", "evidence", "snapshot")
]
BY_TITLE = {x["title"].split(" · ", 1)[0]: x for x in SCENARIOS}
LANGS = ("zh", "en")
LANG_CHOICES = {"中文": "zh", "English": "en"}
MINUS = "−"

# The page has one cream look. Gradio adds a `dark` class when the system is dark;
# remove it as soon as it appears so text never turns white on cream.
FORCE_LIGHT_HEAD = """<meta name="color-scheme" content="light">
<script>
(() => {
  const light = el => el && el.classList && el.classList.contains('dark') && el.classList.remove('dark');
  const sweep = () => document.querySelectorAll('.dark').forEach(light);
  new MutationObserver(records => records.forEach(r => light(r.target)))
    .observe(document.documentElement, {subtree: true, attributes: true, attributeFilter: ['class']});
  document.addEventListener('DOMContentLoaded', sweep);
  sweep();
})();
</script>"""
FORCE_LIGHT_JS = (
    "() => { document.querySelectorAll('.dark').forEach(el => el.classList.remove('dark')); }"
)


def _cat_src() -> str:
    data = (ROOT / "demo" / "cat-head.webp").read_bytes()
    return "data:image/webp;base64," + base64.b64encode(data).decode("ascii")


HERO = {
    "zh": {
        "tag": "AI 记事本 · 上下文压缩",
        "offline": "本机 CPU · 不调用模型",
        "h1": "改过的事，<em>只记最新的。</em>",
        "p": "长聊天里改过好几次的事，TOMC Memory 只把最新的值和它的原句交给模型，每一行都能找回出处。"
        "下面的结果是打开页面时现场算的。",
    },
    "en": {
        "tag": "AI notebook · context compression",
        "offline": "Local CPU · no model call",
        "h1": "When a fact changes, <em>only the latest version comes back.</em>",
        "p": "In a long chat where things keep changing, TOMC Memory hands your model the latest "
        "values and the lines they came from. Every line traces back to its source. "
        "The result below was computed live when the page opened.",
    },
}
TABS = {
    "zh": ("马上试", "接入助手", "30 秒导览", "工作台", "研究证据"),
    "en": ("Try it", "Connect your assistant", "30-second tour", "Workbench", "Research evidence"),
}
FOOTER = {
    "zh": "改过的事，只记最新的。本机运行，不调用模型。",
    "en": "When a fact changes, only the latest version comes back. Runs locally; no model call.",
}


def hero_html(lang: str) -> str:
    """Cat head, name and the one-liner; nothing here depends on user input."""
    h = HERO[lang]
    return (
        f'<section class="hero" lang="{"zh-CN" if lang == "zh" else "en"}">'
        f'<img class="hero-cat" src="{_cat_src()}" alt="" width="88" height="86">'
        '<div class="hero-text">'
        f'<div class="eyebrow">TOMC MEMORY · {escape(h["tag"]).upper()}</div>'
        f"<h1>{h['h1']}</h1><p>{escape(h['p'])}</p></div>"
        f'<div class="offline"><i></i> {escape(h["offline"])}</div></section>'
    )


def footer_html(lang: str) -> str:
    """The version always comes from the installed package."""
    return (
        f'<footer class="footer">TOMC Memory · v{escape(tomc.__version__)} · MIT'
        f"<span>{escape(FOOTER[lang])}</span></footer>"
    )


def load_example(title: str, lang: str = "en") -> tuple[str, str, int, str, str]:
    """Load original sample content and its appropriate task configuration."""
    item = BY_TITLE[title.split(" · ", 1)[0]]
    notes = EXAMPLE_NOTES_ZH if lang == "zh" else EXAMPLE_NOTES
    return (
        json.dumps(item["messages"], ensure_ascii=False, indent=2),
        item["query"],
        item["budget"],
        "tomc_raw" if item["strategy"] == "tomc" else item["strategy"],
        notes[item["id"]],
    )


def parse_input(text: str) -> object:
    """Accept plain context, a JSON message list, or an object with messages."""
    if len(text) > 200_000:
        raise ValueError(
            "The interactive demo accepts up to 200,000 characters. Use the Python API for larger input."
        )
    return parse_history(text)


WB = {
    "en": {
        "cards": (
            ("HISTORY", "estimated tokens"),
            ("MEMORY", "{r} of history"),
            ("CHANGE", "memory vs history"),
            ("COMPILE", "local CPU; no model call"),
        ),
        "in_memory": "in memory",
        "omitted": "budget omitted",
        "money": "At the price you entered (USD {p:g} per 1M input tokens), the memory text costs "
        "≈ ${b:.6f} → ≈ ${a:.6f} (estimate). This covers memory text only; the task, prompt "
        "overhead and answer add to the API cost. Not a bill.",
        "error": "Check the input: use plain text or JSON text messages, a nonnegative budget and price.",
        "error2": "Check the input JSON, budget and price.",
        "choose": "Choose an example",
        "strategy": "Compiler strategy",
        "loaded": "Output matches the loaded example.",
        "changed": "Inputs changed. Compile again to update the memory, or rerun the comparison.",
        "updated": "Memory updated.",
        "source": "### 01 / Source history",
        "context": "Text or conversation JSON",
        "query": "Current task / query",
        "budget_box": "Memory budget & cost estimate",
        "budget": "Memory token budget",
        "price": "Your input price (USD / 1M tokens), for an estimate",
        "run": "Compile memory  →",
        "compiled": "### 02 / Compiled memory",
        "memory": "Memory text to include in your model's prompt",
        "route": "Routing & cost estimate",
        "state_tab": "03 / State & ledger",
        "state_md": "Inspect the records and their sources. **Budget omitted** rows did not fit in the memory.",
        "state_h": ["Kind", "Key", "Value", "Sources", "Packing", "Basis"],
        "ev_tab": "Source evidence",
        "ev_md": "Original lines used by the records or retained as source text. Only text in the compiled memory goes to your model.",
        "ev_h": ["Source", "Role", "Message", "Line", "Original text"],
        "fallback": "Original text retained in memory",
        "side_tab": "Side-by-side",
        "side_md": "Compare the context each method produces. `raw` keeps the full history, including text beyond the memory budget. Answer quality is shown under Research evidence.",
        "a": "Method A",
        "b": "Method B",
        "compare": "Compare methods",
        "a_mem": "Method A memory",
        "b_mem": "Method B memory",
        "cmp_h": [
            "Method",
            "Input est.",
            "Memory est.",
            "Retained %",
            "CPU ms",
            "Within budget",
            "≈ Input USD (estimate)",
        ],
        "export": "Export / JSON",
        "json": "Result JSON, including original sources",
        "parsing": "Parsing and token counts",
        "parsing_md": "The record parser recognizes explicit operations such as `drink = tea` and `backup_drink copies drink`. "
        "Unfamiliar wording can be missed or misread. For prose and quotations, use `hybrid` or `rag` and inspect the retained text. Token counts are estimates.",
        "limits": "[Paper results and implementation limits](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md).",
    },
    "zh": {
        "cards": (
            ("原始历史", "估算 token"),
            ("准备后", "占历史的 {r}"),
            ("变化", "准备后对比原始"),
            ("耗时", "本机 CPU，不调用模型"),
        ),
        "in_memory": "已带上",
        "omitted": "预算不够没带上",
        "money": "按你填的单价（每百万输入 token {p:g} 美元）估算：记忆部分 ≈ ${b:.6f} → ≈ ${a:.6f}。"
        "只算记忆文字，问题、系统说明和回答另算。不是账单。",
        "error": "请检查输入：纯文本或 JSON 文字消息，预算和单价不能是负数。",
        "error2": "请检查 JSON、预算和单价。",
        "choose": "选一个例子",
        "strategy": "整理方法",
        "loaded": "结果和载入的例子一致。",
        "changed": "输入改了。点「整理」更新结果，或者重新对比。",
        "updated": "已更新。",
        "source": "### 01 / 原始历史",
        "context": "纯文本或聊天 JSON",
        "query": "这次要问什么",
        "budget_box": "预算和费用估算",
        "budget": "预算（token）",
        "price": "你的输入单价（美元 / 百万 token），仅用于估算",
        "run": "整理  →",
        "compiled": "### 02 / 整理结果",
        "memory": "放进模型提示里的内容",
        "route": "方法选择和费用估算",
        "state_tab": "03 / 状态和记录",
        "state_md": "看每条记录和它的出处。**预算不够没带上**的行没有放进结果。",
        "state_h": ["类型", "键", "值", "出处", "是否带上", "依据"],
        "ev_tab": "原文出处",
        "ev_md": "记录用到的原文行，或作为原句保留的行。只有结果里的文字会交给模型。",
        "ev_h": ["出处", "角色", "消息", "行", "原文"],
        "fallback": "结果里保留的原文",
        "side_tab": "方法对比",
        "side_md": "对比不同方法给出的上下文。`raw` 保留整段历史，包括超出预算的部分。答题质量见「研究证据」。",
        "a": "方法 A",
        "b": "方法 B",
        "compare": "对比",
        "a_mem": "方法 A 的结果",
        "b_mem": "方法 B 的结果",
        "cmp_h": [
            "方法",
            "原始（估算）",
            "结果（估算）",
            "保留 %",
            "CPU 毫秒",
            "在预算内",
            "≈ 输入美元（估算）",
        ],
        "export": "导出 / JSON",
        "json": "结果 JSON，含原文出处",
        "parsing": "解析规则和 token 计数",
        "parsing_md": "记录解析器认得 `drink = tea`、`backup_drink copies drink` 这类明确写法，"
        "不熟悉的说法可能漏掉或认错。整段文字和引用请用 `hybrid` 或 `rag`，再看保留的原文。token 数是估算。",
        "limits": "[论文结果和实现局限（英文）](https://github.com/ZipengWu365/TOMC/blob/main/docs/claims_and_limitations.md)",
    },
}


def compile_view(
    context: str, query: str, budget: int, strategy: str, price: float, lang: str = "en"
) -> tuple:
    """Compile locally and render measured output and its separate audit trail."""
    w = WB["zh" if lang == "zh" else "en"]
    try:
        result = compile_memory(
            parse_input(context), query, int(budget), strategy, input_price_per_million=float(price)
        )
    except (ValueError, TypeError, KeyError):
        raise gr.Error(w["error"]) from None
    stats = result.stats
    before, after = stats.input_tokens, stats.output_tokens
    if before and after < before:
        change = f"{MINUS}{round(100 * (before - after) / before)}%"
    elif before and after > before:
        change = f"+{round(100 * (after - before) / before)}%"
    else:
        change = "0%"
    values = (f"{before:,}", f"{after:,}", change, f"{stats.latency_ms:.1f} ms")
    metrics = (
        '<div class="metric-grid">'
        + "".join(
            f'<div class="metric"><span>{label}</span><strong>{value}</strong>'
            f"<small>{detail.format(r=f'{stats.retention_ratio:.1%}')}</small></div>"
            for (label, detail), value in zip(w["cards"], values)
        )
        + "</div>"
    )
    state = [
        [
            r.kind,
            r.key,
            r.value,
            ", ".join(r.sources),
            w["in_memory"] if r.included else w["omitted"],
            r.basis,
        ]
        for r in result.ledger
    ]
    evidence = [
        [u.source_id, u.role, u.message_index, u.line_number, u.text] for u in result.evidence
    ]
    route = (
        f"**{strategy} → {result.diagnostics['selected_strategy']} / {result.route}** · "
        f"{result.diagnostics['route_reason']}"
    )
    cost_before, cost_after = stats.estimated_input_cost_before, stats.estimated_input_cost_after
    # Hide money when no price was given; never show $0 as if it were a value.
    if price and cost_before is not None and cost_after is not None:
        route += "\n\n" + w["money"].format(p=price, b=cost_before, a=cost_after)
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
    context: str, query: str, budget: int, first: str, second: str, price: float, lang: str = "en"
) -> tuple:
    """Run two actual offline strategies under the same measured budget."""
    try:
        data = parse_input(context)
        results = [
            compile_memory(data, query, int(budget), s, input_price_per_million=float(price))
            for s in (first, second)
        ]
    except (ValueError, TypeError, KeyError):
        raise gr.Error(WB["zh" if lang == "zh" else "en"]["error2"]) from None
    rows = [
        [
            r.strategy,
            r.stats.input_tokens,
            r.stats.output_tokens,
            round(r.stats.retention_ratio * 100, 2),
            r.stats.latency_ms,
            r.stats.budget_compliant,
            r.stats.estimated_input_cost_after if price else None,
        ]
        for r in results
    ]
    return results[0].compiled_memory, results[1].compiled_memory, rows


def _build_workbench(lang: str = "en", primary: bool = True) -> None:
    """Build the complete editor, keeping the quick tour focused on one action."""
    w = WB[lang]
    example = load_example(SCENARIOS[0]["title"], lang)
    initial = compile_view(*example[:4], 1.0, lang=lang)
    suffix = f"-{lang}"
    with gr.Row():
        scenario = gr.Dropdown(
            list(BY_TITLE), value=next(iter(BY_TITLE)), label=w["choose"], scale=3, min_width=220
        )
        method = gr.Dropdown(
            list(DEMO_STRATEGIES), value=example[3], label=w["strategy"], scale=1, min_width=150
        )
    note = gr.Markdown(example[4], elem_classes="scenario-note")
    status = gr.Markdown(w["loaded"], elem_classes="output-status")
    with gr.Row(equal_height=False):
        with gr.Column(scale=5, min_width=280):
            gr.Markdown(w["source"])
            context = gr.Textbox(
                value=example[0],
                lines=10,
                max_lines=24,
                label=w["context"],
                elem_id="source-input" + suffix,
                elem_classes="mono-box",
            )
            query = gr.Textbox(value=example[1], lines=2, label=w["query"])
            with gr.Accordion(w["budget_box"], open=False):
                budget = gr.Slider(0, 4096, value=example[2], step=16, label=w["budget"])
                price = gr.Number(value=1.0, minimum=0, label=w["price"])
            run = gr.Button(w["run"], variant="primary", size="lg")
        with gr.Column(scale=7, min_width=280):
            gr.Markdown(w["compiled"])
            metrics = gr.HTML(initial[1])
            memory = gr.Textbox(
                value=initial[0],
                elem_id="memory-output" + suffix,
                elem_classes="mono-box",
                lines=10,
                max_lines=24,
                label=w["memory"],
                interactive=False,
                show_copy_button=True,
                autoscroll=False,
            )
            with gr.Accordion(w["route"], open=False):
                route = gr.Markdown(initial[5])
    with gr.Tabs():
        with gr.Tab(w["state_tab"]):
            gr.Markdown(w["state_md"])
            state = gr.Dataframe(
                value=initial[2],
                headers=w["state_h"],
                datatype=["str"] * 6,
                interactive=False,
                wrap=True,
            )
        with gr.Tab(w["ev_tab"]):
            gr.Markdown(w["ev_md"])
            evidence = gr.Dataframe(
                value=initial[3],
                headers=w["ev_h"],
                datatype=["str", "str", "number", "number", "str"],
                interactive=False,
                wrap=True,
            )
            fallback = gr.Textbox(value=initial[4], lines=6, label=w["fallback"], interactive=False)
        with gr.Tab(w["side_tab"]):
            gr.Markdown(w["side_md"])
            with gr.Row():
                first = gr.Dropdown(list(DEMO_STRATEGIES), value="tail", label=w["a"], min_width=0)
                second = gr.Dropdown(
                    list(DEMO_STRATEGIES), value="tomc_raw", label=w["b"], min_width=0
                )
                compare = gr.Button(w["compare"], variant="secondary", min_width=0)
            with gr.Row():
                left = gr.Textbox(
                    label=w["a_mem"], lines=12, interactive=False, elem_id="compare-left" + suffix
                )
                right = gr.Textbox(
                    label=w["b_mem"], lines=12, interactive=False, elem_id="compare-right" + suffix
                )
            comparison = gr.Dataframe(headers=w["cmp_h"], interactive=False)
        with gr.Tab(w["export"]):
            export = gr.JSON(value=initial[7], label=w["json"])
    with gr.Accordion(w["parsing"], open=False):
        warnings = gr.Markdown(w["parsing_md"])
        gr.Markdown(w["limits"])

    def compile_here(context: str, query: str, budget: int, strategy: str, price: float):
        return compile_view(context, query, budget, strategy, price, lang)

    def compare_here(context: str, query: str, budget: int, a: str, b: str, price: float):
        return compare_view(context, query, budget, a, b, price, lang)

    def load_here(title: str):
        return load_example(title, lang)

    inputs = [context, query, budget, method, price]
    outputs = [memory, metrics, state, evidence, fallback, route, warnings, export]
    scenario.change(load_here, scenario, [context, query, budget, method, note]).success(
        compile_here, inputs, outputs
    ).success(lambda: w["loaded"], outputs=status)
    # gr.Number reports an input when its tab first mounts, which would claim the
    # inputs changed before anyone touched them; it and the slider use blur/release.
    for control in (context, query, method):
        control.input(lambda: w["changed"], outputs=status, queue=False, api_name=False)
    price.blur(lambda: w["changed"], outputs=status, queue=False, api_name=False)
    budget.release(lambda: w["changed"], outputs=status, queue=False, api_name=False)
    run.click(compile_here, inputs, outputs, api_name="compile" if primary else False).success(
        lambda: w["updated"], outputs=status
    )
    compare.click(
        compare_here,
        [context, query, budget, first, second, price],
        [left, right, comparison],
        api_name="compare" if primary else False,
    )


def _build_page(lang: str) -> None:
    """One complete page in one language; the language switch shows one of two."""
    names = TABS[lang]
    gr.HTML(hero_html(lang))
    with gr.Tabs(selected=f"use-{lang}") as entrances:
        with gr.Tab(names[0], id=f"use-{lang}"):
            build_easy(lang, primary=lang == "zh")
        with gr.Tab(names[1], id=f"connect-{lang}"):
            build_connect(lang)
        with gr.Tab(names[2], id=f"tour-{lang}"):
            labels = CASE_LABELS[lang]
            with gr.Row(elem_classes="tour-controls"):
                case = gr.Dropdown(
                    [(labels[key], key) for key in CASES],
                    value=next(iter(CASES)),
                    label="选一个例子" if lang == "zh" else "Explore a case",
                    scale=3,
                    min_width=0,
                )
                own = gr.Button(
                    "用你自己的聊天试试 →" if lang == "zh" else "Try your own history →",
                    variant="primary",
                    scale=1,
                    min_width=0,
                )
            story = gr.HTML(render_tour(next(iter(CASES)), lang), elem_classes="tour-story")

            def tour_here(case: str) -> str:
                return render_tour(case, lang)

            case.change(tour_here, case, story, api_name=False)
            gr.Markdown(
                "想用自己的聊天记录，去「马上试」；论文结果在「研究证据」。这些例子都是本机现场整理的示例数据。"
                if lang == "zh"
                else "Try your own history in **Try it**, or read the paper's results under "
                "**Research evidence**. These examples run the local compiler on sample data."
            )
            with gr.Accordion(
                "局限：很短的聊天" if lang == "zh" else "Limits: very short chats", open=False
            ):
                gr.Markdown(limits_note(lang), elem_classes="limits-note")
                gr.HTML(render_tour(LIMIT_CASE, lang), elem_classes="tour-story")
        with gr.Tab(names[3], id=f"workbench-{lang}"):
            _build_workbench(lang, primary=lang == "zh")
        with gr.Tab(names[4], id=f"research-{lang}"):
            build_research(lang)
    gr.HTML(footer_html(lang))
    own.click(lambda: gr.Tabs(selected=f"use-{lang}"), outputs=entrances, api_name=False)


def pick_language(choice: str | None) -> tuple:
    """Show exactly one of the two pages."""
    lang = LANG_CHOICES.get(choice or "", "zh")
    return tuple(gr.Column(visible=lang == code) for code in LANGS)


def language_from_request(request: gr.Request | None) -> tuple:
    """`?lang=en` opens the English page; everything else opens Chinese."""
    value = ""
    if request is not None:
        value = (request.query_params.get("lang") or "").lower()
    choice = "English" if value.startswith("en") else "中文"
    return (choice, *pick_language(choice))


def create_demo() -> gr.Blocks:
    """Chinese by default, a visible language switch, and a result already on screen."""
    theme = gr.themes.Base(
        primary_hue="emerald",
        secondary_hue="slate",
        neutral_hue="stone",
        font=["Arial", "PingFang SC", "Microsoft YaHei", "sans-serif"],
        font_mono=["ui-monospace", "monospace"],
    )
    with gr.Blocks(
        theme=theme,
        css=(ROOT / "demo/style.css").read_text(encoding="utf-8"),
        head=FORCE_LIGHT_HEAD,
        js=FORCE_LIGHT_JS,
        title="TOMC Memory · 改过的事，只记最新的",
        analytics_enabled=False,
        delete_cache=(3600, 3600),
    ) as app:
        with gr.Row(elem_classes="topbar", equal_height=True):
            gr.HTML(
                f'<div class="brand"><img src="{_cat_src()}" alt="" width="30" height="30">'
                "TOMC Memory</div>",
                elem_classes="brand-cell",
            )
            language = gr.Radio(
                list(LANG_CHOICES),
                value="中文",
                show_label=False,
                container=False,
                elem_id="lang-switch",
                elem_classes="lang-switch",
                min_width=0,
            )
        pages = []
        for lang in LANGS:
            with gr.Column(visible=lang == "zh", elem_classes=f"page page-{lang}") as page:
                _build_page(lang)
            pages.append(page)
        language.change(
            pick_language, language, pages, queue=False, api_name=False, show_progress="hidden"
        )
        app.load(
            language_from_request,
            None,
            [language, *pages],
            queue=False,
            api_name=False,
            show_progress="hidden",
        )
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
