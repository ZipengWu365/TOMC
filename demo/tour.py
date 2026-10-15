"""Render a small, source-linked tour from actual offline compiler results."""

from __future__ import annotations

import json
from html import escape
from importlib.resources import files

from tomc import compile_memory

CASES = {
    "State updates & snapshots": ("snapshot", "Keep an earlier value after an update."),
    "When original words matter": ("evidence", "Some questions need the original words."),
}

EXAMPLE_NOTES = {
    "preferences": "Follow explicit updates such as `drink = tea`, and keep a copied value after the original changes.",
    "constraints": "Keep the latest constraints when earlier assignments have been replaced.",
    "evidence": "A `venue = library` record gives the choice, but the original sentence explains why. Keep that source text for this question.",
    "snapshot": "Copy the current value, then update the original. The copy keeps its earlier value. This view shows records alone; full TOMC also includes selected source text.",
}


def render_tour(case: str) -> str:
    """Compile a bundled case and escape all displayed source and output text."""
    name, headline = CASES[case]
    item = json.loads(files("tomc").joinpath(f"data/{name}.json").read_text(encoding="utf-8"))
    result = compile_memory(item["messages"], item["query"], item["budget"], item["strategy"])
    sources = {u.source_id: u for u in result.evidence}
    rows = []
    for row in result.ledger:
        citations = "".join(
            f'<div class="citation"><span>{escape(sid)} · message {sources[sid].message_index + 1}, '
            f"line {sources[sid].line_number}</span><code>{escape(sources[sid].text)}</code></div>"
            for sid in row.sources
            if sid in sources
        )
        packed = "In memory" if row.included else "Budget omitted · audit only"
        rows.append(
            f'<details class="state-card"><summary><span class="state-key">{escape(row.key)}</span>'
            f'<strong>{escape(row.value)}</strong><span class="source-toggle">{packed} · sources +</span>'
            f'</summary><div class="citations">{citations or "No source text included for this row."}'
            f"<small>Basis: {escape(row.basis)}</small></div></details>"
        )
    source_history = "".join(
        f'<div class="history-step"><span>{i + 1:02d} / {escape(m["role"])}</span>'
        f"<pre>{escape(m['content'])}</pre></div>"
        for i, m in enumerate(item["messages"])
    )
    if not rows:
        rows.append(
            '<div class="raw-card"><p>This route preserves source text for this question.</p>'
            f"<pre>{escape(result.compiled_memory)}</pre></div>"
        )
    stats = result.stats
    size_note = (
        "Adding source labels expands this tiny example. Inspect the update and copy records."
        if stats.output_tokens > stats.input_tokens
        else "Counts measure this example's context. Paper answer scores are under Research evidence."
    )
    route = escape(result.diagnostics["selected_strategy"])
    scope = "COMPILED RECORDS EXAMPLE" if item["strategy"] == "tomc" else "SAMPLE HISTORY"
    return (
        '<section class="tour-result" aria-label="Compiled example">'
        f'<div class="tour-intro"><div><span class="eyebrow">{scope} / {route}</span>'
        f"<h2>{headline}</h2><p>{escape(EXAMPLE_NOTES[name])}</p></div></div>"
        '<div class="story-grid"><div class="story-source">'
        "<h3><span>01</span> The history</h3>"
        f'<div class="history-scroll">{source_history}</div></div>'
        '<div class="story-memory"><h3><span>02</span> Memory for the next step</h3>'
        '<p class="inspect-hint">Open a state row to inspect its original sources.</p>'
        f'<div class="ledger-scroll">{"".join(rows)}</div></div></div>'
        f'<div class="tour-measure"><strong>{stats.input_tokens} → {stats.output_tokens}</strong>'
        f"<span>estimated tokens · budget {stats.token_budget}<br>{size_note}</span>"
        '<span class="cpu-note">Compiled on CPU<br>No model or API call</span></div>'
        f'<details class="tour-output"><summary>Compiled memory and token counts</summary>'
        f"<pre>{escape(result.compiled_memory)}</pre><p>Query: {escape(item['query'])}</p>"
        "<p>Only the compiled memory is covered by these token counts. The source inspector, query, "
        "chat formatting and generated reader answers are excluded.</p>"
        f"<p>{escape(' '.join(result.warnings))}</p></details></section>"
    )
