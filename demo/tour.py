"""Render a small, source-linked tour from actual offline compiler results."""

from __future__ import annotations

import json
from html import escape
from importlib.resources import files

from tomc import compile_memory

MINUS = "−"

# Tour cases that show compression. The tiny snapshot case lives under Limits.
CASES = {
    "Moving constraints": ("constraints", "Only the latest constraints come back."),
    "Changing preferences": ("preferences", "Preferences change; the current ones come back."),
}
LIMIT_CASE = "State updates & snapshots"
ALL_CASES = {
    **CASES,
    LIMIT_CASE: ("snapshot", "Keep an earlier value after an update."),
}
CASE_LABELS = {
    "zh": {
        "Moving constraints": "改来改去的活动安排",
        "Changing preferences": "改来改去的偏好",
        LIMIT_CASE: "很短的聊天（局限）",
    },
    "en": {key: key for key in ALL_CASES},
}
HEADLINES_ZH = {
    "constraints": "活动安排改了好几次，只带回最新的。",
    "preferences": "偏好一直在变，带回的是现在的。",
    "snapshot": "更新之后，复制出来的那份还记得旧值。",
}

EXAMPLE_NOTES = {
    "preferences": "Follow explicit updates such as `drink = tea`, and keep a copied value after the original changes.",
    "constraints": "Keep the latest constraints when earlier assignments have been replaced.",
    "evidence": "A `venue = library` record gives the choice, but the original sentence explains why. Keep that source text for this question.",
    "snapshot": "Copy the current value, then update the original. The copy keeps its earlier value. This view shows records alone; full TOMC also includes selected source text.",
}
EXAMPLE_NOTES_ZH = {
    "preferences": "跟着 `drink = tea` 这样明确的更新走；原值改了以后，复制出来的值保持复制时的样子。",
    "constraints": "前面的安排被新的覆盖了，只留最新的约束。",
    "evidence": "`venue = library` 给出了选择，但为什么选它要看原句。这类问题会把原句一起带上。",
    "snapshot": "先复制当前值，再改原值，复制出来的那份保持旧值。这里只看记录；完整的 TOMC 还会带上挑出的原句。",
}

_T = {
    "en": {
        "history": "The history",
        "memory": "Memory for the next step",
        "hint": "Open a row to see the original lines it came from.",
        "msg": "message {m}, line {l}",
        "in": "In memory",
        "out": "Budget omitted · audit only",
        "sources": "sources +",
        "none": "No source text included for this row.",
        "basis": "Basis",
        "raw": "This route preserves source text for this question.",
        "tokens": "estimated tokens · budget {b}",
        "grew": "Adding source labels expands this tiny example. Inspect the update and copy records.",
        "ok": "Counts measure this example's context. Paper answer scores are under Research evidence.",
        "cpu": "Compiled on CPU<br>No model or API call",
        "output": "Compiled memory and token counts",
        "query": "Query",
        "scope": "Only the compiled memory is covered by these token counts. The source inspector, "
        "query, chat formatting and generated reader answers are excluded.",
        "records": "COMPILED RECORDS EXAMPLE",
        "sample": "SAMPLE HISTORY",
        "aria": "Compiled example",
    },
    "zh": {
        "history": "原来的聊天",
        "memory": "交给下一步的内容",
        "hint": "点开一行，看它来自原文哪一行。",
        "msg": "第 {m} 条第 {l} 行",
        "in": "已带上",
        "out": "预算不够没带上 · 只留作核对",
        "sources": "出处 +",
        "none": "这一行没有附原文。",
        "basis": "依据",
        "raw": "这个问题需要原话，所以带上了原文。",
        "tokens": "估算 token · 预算 {b}",
        "grew": "例子太短，加上来源标签反而变长了。这里看的是更新和复制的记录。",
        "ok": "只算这个例子的上下文。论文里的答题分数在「研究证据」。",
        "cpu": "本机 CPU 处理<br>不调用模型或 API",
        "output": "准备好的内容和 token 数",
        "query": "问题",
        "scope": "token 数只算准备好的内容，不含来源查看器、问题、聊天格式和模型回答。",
        "records": "结构化记录示例",
        "sample": "示例聊天",
        "aria": "示例结果",
    },
}


def _change(before: int, after: int, lang: str) -> str:
    saved = before - after
    if saved > 0:
        return f"{MINUS}{round(100 * saved / before)}%"
    if saved < 0:
        return f"变多了 {-saved}" if lang == "zh" else f"+{-saved}, larger"
    return "0%"


def render_tour(case: str, lang: str = "en") -> str:
    """Compile a bundled case and escape all displayed source and output text."""
    lang = "zh" if (lang or "").startswith("zh") else "en"
    t = _T[lang]
    key = next((k for k, labels in CASE_LABELS[lang].items() if case in (k, labels)), case)
    name, headline = ALL_CASES[key]
    if lang == "zh":
        headline = HEADLINES_ZH[name]
    notes = EXAMPLE_NOTES_ZH if lang == "zh" else EXAMPLE_NOTES
    item = json.loads(files("tomc").joinpath(f"data/{name}.json").read_text(encoding="utf-8"))
    result = compile_memory(item["messages"], item["query"], item["budget"], item["strategy"])
    sources = {u.source_id: u for u in result.evidence}
    rows = []
    for row in result.ledger:
        citations = "".join(
            f'<div class="citation"><span>{escape(sid)} · '
            + t["msg"].format(m=sources[sid].message_index + 1, l=sources[sid].line_number)
            + f"</span><code>{escape(sources[sid].text)}</code></div>"
            for sid in row.sources
            if sid in sources
        )
        packed = t["in"] if row.included else t["out"]
        rows.append(
            f'<details class="state-card"><summary><span class="state-key">{escape(row.key)}</span>'
            f'<strong>{escape(row.value)}</strong><span class="source-toggle">{packed} · {t["sources"]}</span>'
            f'</summary><div class="citations">{citations or t["none"]}'
            f"<small>{t['basis']}: {escape(row.basis)}</small></div></details>"
        )
    source_history = "".join(
        f'<div class="history-step"><span>{i + 1:02d} / {escape(m["role"])}</span>'
        f"<pre>{escape(m['content'])}</pre></div>"
        for i, m in enumerate(item["messages"])
    )
    if not rows:
        rows.append(
            f'<div class="raw-card"><p>{t["raw"]}</p>'
            f"<pre>{escape(result.compiled_memory)}</pre></div>"
        )
    stats = result.stats
    size_note = t["grew"] if stats.output_tokens > stats.input_tokens else t["ok"]
    route = escape(result.diagnostics["selected_strategy"])
    scope = t["records"] if item["strategy"] == "tomc" else t["sample"]
    change = _change(stats.input_tokens, stats.output_tokens, lang)
    grew = " grew" if stats.output_tokens > stats.input_tokens else ""
    return (
        f'<section class="tour-result" aria-label="{t["aria"]}">'
        f'<div class="tour-intro"><div><span class="eyebrow">{scope} / {route}</span>'
        f"<h2>{escape(headline)}</h2><p>{escape(notes[name])}</p></div></div>"
        f'<div class="tour-measure{grew}"><strong>{stats.input_tokens} → {stats.output_tokens}'
        f" <em>{change}</em></strong>"
        f"<span>{t['tokens'].format(b=stats.token_budget)}<br>{size_note}</span>"
        f'<span class="cpu-note">{t["cpu"]}</span></div>'
        '<div class="story-grid"><div class="story-source">'
        f"<h3><span>01</span> {t['history']}</h3>"
        f'<div class="history-scroll">{source_history}</div></div>'
        f'<div class="story-memory"><h3><span>02</span> {t["memory"]}</h3>'
        f'<p class="inspect-hint">{t["hint"]}</p>'
        f'<div class="ledger-scroll">{"".join(rows)}</div></div></div>'
        f'<details class="tour-output"><summary>{t["output"]}</summary>'
        f"<pre>{escape(result.compiled_memory)}</pre><p>{t['query']}: {escape(item['query'])}</p>"
        f"<p>{t['scope']}</p>"
        f"<p>{escape(' '.join(result.warnings))}</p></details></section>"
    )


def limits_note(lang: str = "en") -> str:
    """The tiny case that grows, measured live and framed as a limit."""
    item = json.loads(files("tomc").joinpath("data/snapshot.json").read_text(encoding="utf-8"))
    stats = compile_memory(item["messages"], item["query"], item["budget"], item["strategy"]).stats
    before, after, count = stats.input_tokens, stats.output_tokens, len(item["messages"])
    if (lang or "").startswith("zh"):
        return (
            f"**局限：很短的聊天不需要压缩。** 下面这个只有 {count} 条消息的例子，加上来源标签以后反而从 "
            f"{before} 变成 {after} token。TOMC Memory 遇到放得下的历史会原样发送；"
            "这个例子只是用来看「复制出来的值记得旧值」这种记录。"
        )
    return (
        f"**Limits: very short chats don't need compression.** This {count}-message example goes "
        f"from {before} to {after} tokens once source labels are added. TOMC Memory sends a "
        "history that fits as it is; this example is only here to show how a copied value keeps "
        "its earlier value."
    )
