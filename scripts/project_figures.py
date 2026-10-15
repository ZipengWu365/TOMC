"""Original, reproducible project-page diagrams and a frozen-evidence figure.

SVG diagrams use code-native vectors. The statistical figure uses Matplotlib.
Run --render to add PNG exports using optional Playwright + Chromium.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import textwrap
from html import escape
from pathlib import Path

from tomc import compile_memory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
INK, BLUE, GREEN, AMBER = "#273343", "#356da6", "#287451", "#97651b"
SKY, MINT, SAND = "#edf4fc", "#edf6e8", "#fff5df"


class Drawing:
    """A small SVG writer with explicit dimensions and escaped text."""

    def __init__(self, width: int, height: int, title: str, desc: str):
        self.parts = [
            f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0L7 4L0 8" fill="none" stroke="{INK}" stroke-width="1.4"/></marker></defs>
<rect width="100%" height="100%" rx="16" fill="white"/>
<style>text{{font-family:Arial,'Noto Sans CJK SC',sans-serif;fill:{INK}}}.mono{{font-family:ui-monospace,'DejaVu Sans Mono',monospace}}</style>'''
        ]

    def text(self, x, y, text, size=22, color=INK, bold=False, mono=False, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" style="fill:{color}" '
            f'font-weight="{700 if bold else 400}" text-anchor="{anchor}" '
            f'class="{"mono" if mono else "label"}">{escape(str(text))}</text>'
        )

    def box(self, x, y, w, h, fill="white", stroke="#9ba9b5", radius=14):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>'
        )

    def arrow(self, x1, y1, x2, y2, dashed=False):
        self.parts.append(
            f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{INK}" stroke-width="2.4" stroke-dasharray="{"6 5" if dashed else "none"}" marker-end="url(#arrow)"/>'
        )

    def write(self, name):
        (OUT / name).write_text("\n".join(self.parts) + "\n</svg>\n", encoding="utf-8")


def sample_result():
    sample = json.loads((ROOT / "src/tomc/data/snapshot.json").read_text())
    return sample, compile_memory(
        sample["messages"], sample["query"], sample["budget"], sample["strategy"]
    )


def mark():
    d = Drawing(
        128,
        128,
        "TOMC source-linked state mark",
        "Three indexed memory cards connected to source nodes.",
    )
    d.box(15, 17, 78, 89, SKY, BLUE, 12)
    d.box(25, 26, 78, 89, SAND, AMBER, 12)
    d.box(35, 35, 78, 80, MINT, GREEN, 12)
    for y, width in ((57, 42), (74, 29), (91, 35)):
        d.parts.append(
            f'<path d="M51 {y}h{width}" stroke="{GREEN}" stroke-width="5" stroke-linecap="round"/>'
        )
    for y in (57, 91):
        d.parts.append(
            f'<path d="M10 {y}H35" stroke="{BLUE}" stroke-width="2.5"/><circle cx="10" cy="{y}" r="5" fill="white" stroke="{BLUE}" stroke-width="2.5"/>'
        )
    d.write("tomc_mark.svg")


def overview(zh=False, mobile=False):
    def tr(en, cn):
        return cn if zh else en

    width, height = (520, 1320) if mobile else (1280, 660)
    d = Drawing(
        width,
        height,
        tr("TOMC: from history to traceable memory", "TOMC：从历史到可追溯记忆"),
        tr(
            "TOMC compiles selected history into task-conditioned records and raw evidence under a budget for an unchanged LLM reader. The output illustrates the STATE route.",
            "TOMC 将选中的历史编译成任务相关记录与原文证据，按预算组合后交给不变的大模型；输出以 STATE 路由为例。",
        ),
    )
    d.text(32, 43, "TOMC  /  TASK-ORIENTED MEMORY COMPILATION", 14, BLUE, True)
    if mobile:
        d.text(32, 87, tr("History → traceable memory", "历史 → 可追溯的记忆"), 29, bold=True)
        positions = [(32, 130, 456, 278), (32, 456, 456, 330), (32, 834, 456, 270)]
    else:
        d.text(
            32,
            91,
            tr("Turn history into memory for the next task.", "将历史编译成下一步任务所需的记忆。"),
            36,
            bold=True,
        )
        positions = [(32, 154, 348, 330), (456, 154, 348, 330), (880, 154, 368, 330)]
    x, y, w, h = positions[0]
    d.box(x, y, w, h, SKY, BLUE)
    d.text(x + 22, y + 39, tr("01  History + task", "01  历史与当前任务"), 25, BLUE, True)
    for i, line in enumerate(("drink = tea", "backup_drink copies drink", "drink = decaf tea")):
        d.text(x + 22, y + 88 + i * 38, line, 17 if not mobile else 20, mono=True)
    d.text(x + 22, y + 220, tr("What is current?", "哪些状态现在有效？"), 23, BLUE, True)
    d.text(x + 22, y + 252, tr("What did the earlier copy keep?", "之前的副本保留了什么？"), 19)
    if not mobile:
        d.text(x + 22, y + 296, tr("Synthetic normalized operations", "合成的规范化操作"), 16, BLUE)
    x, y, w, h = positions[1]
    d.box(x, y, w, h, "#fafbf9", GREEN)
    d.text(x + 22, y + 39, tr("02  Select + compile", "02  选取证据并编译"), 25, GREEN, True)
    d.box(x + 18, y + 61, w - 36, 83, MINT, GREEN, 8)
    d.text(x + 34, y + 93, tr("Task-specific records", "任务相关记录"), 25, GREEN, True)
    d.text(
        x + 34, y + 123, tr("State / key–value / relation / count", "状态 / 键值 / 关系 / 计数"), 17
    )
    d.box(x + 18, y + 161, w - 36, 83, SKY, BLUE, 8)
    d.text(x + 34, y + 193, tr("Raw evidence", "原文证据"), 25, BLUE, True)
    d.text(x + 34, y + 223, tr("Keep relevant source wording", "保留任务需要的原始措辞"), 17)
    d.text(
        x + 22,
        y + 285,
        tr("Pack selected memory to a budget", "将所选记忆装入 token 预算"),
        19,
        GREEN,
        True,
    )
    d.text(x + 22, y + 311, tr("Training-free; reader unchanged", "无需训练；reader 模型不变"), 17)
    x, y, w, h = positions[2]
    _, result = sample_result()
    values = {r.key: r.value for r in result.ledger}
    d.box(x, y, w, h, MINT, GREEN)
    d.text(x + 22, y + 39, tr("03  Task-ready memory", "03  任务所需的记忆"), 25, GREEN, True)
    for i, key in enumerate(("backup_drink", "drink")):
        d.text(x + 22, y + 86 + i * 80, key, 19, mono=True)
        d.text(x + 22, y + 116 + i * 80, values[key], 26, AMBER if i == 0 else GREEN, True)
    d.text(x + 22, y + 236, tr("Memory → LLM reader", "记忆 → 大模型 reader"), 23, GREEN, True)
    if not mobile:
        d.text(
            x + 22,
            y + 279,
            tr("Selected rows from the actual output", "实际编译输出中的部分状态行"),
            16,
        )
        d.text(x + 22, y + 306, tr("Source links travel with the state", "状态附带来源指针"), 18)
    if mobile:
        for i in (0, 1):
            d.arrow(260, positions[i][1] + positions[i][3] + 12, 260, positions[i + 1][1] - 15)
        fy = 1140
        d.box(32, fy, 456, 143, SAND, AMBER)
        for j, line in enumerate(
            [
                tr("Keep the evidence inspectable", "保留可检查的来源证据"),
                "u0: drink = tea",
                "u2: backup_drink copies drink",
                tr("Inspector outside the reader budget", "来源检查面板不计入 reader 预算"),
            ]
        ):
            d.text(
                50,
                fy + 32 + j * 29,
                line,
                20 if j == 0 else 18,
                AMBER if j == 0 else INK,
                j == 0,
                j in (1, 2),
            )
    else:
        d.arrow(394, 320, 439, 320)
        d.arrow(818, 320, 863, 320)
        d.box(32, 528, 1216, 92, SAND, AMBER)
        d.text(54, 564, tr("Evidence stays inspectable", "来源证据始终可以核对"), 24, AMBER, True)
        d.text(
            54,
            596,
            tr(
                "Separate source inspector · outside the reader budget",
                "独立来源检查面板 · 不计入 reader 预算",
            ),
            17,
        )
        d.text(720, 564, "u0: drink = tea", 18, mono=True)
        d.text(720, 596, "u2: backup_drink copies drink", 18, mono=True)
        d.arrow(206, 493, 206, 514, True)
        d.arrow(1064, 493, 1064, 514, True)
    suffix = ("_zh" if zh else "") + ("_mobile" if mobile else "")
    d.write(f"project_overview{suffix}.svg")


def snapshot(zh=False, mobile=False):
    def tr(en, cn):
        return cn if zh else en

    sample, result = sample_result()
    values = {r.key: r.value for r in result.ledger}
    d = Drawing(
        520 if mobile else 1280,
        1080 if mobile else 560,
        tr("A snapshot preserves the earlier value", "快照保留复制时的值"),
        tr(
            "An actual synthetic compilation: backup_drink remains tea after drink changes to decaf tea. The copy depends on sources u0 and u2.",
            "真实合成编译结果：drink 更新为 decaf tea 后，backup_drink 仍为 tea，依据来源 u0 和 u2。",
        ),
    )
    d.text(32, 44, tr("TOMC  /  SNAPSHOT SEMANTICS", "TOMC  /  快照复制语义"), 15, BLUE, True)
    d.text(
        32,
        89,
        tr("Copy now. Update the source later.", "先复制，再更新来源。"),
        28 if mobile else 36,
        bold=True,
    )
    positions = (
        [(32, 130 + i * 180, 456, 140) for i in range(3)]
        if mobile
        else [(32 + i * 424, 142, 368, 173) for i in range(3)]
    )
    labels = [
        tr("1. Set the original", "1. 设置初始值"),
        tr("2. Capture a snapshot", "2. 复制当时的快照"),
        tr("3. Update the source", "3. 更新来源的当前值"),
    ]
    source_id = 0
    for i, ((x, y, w, h), m) in enumerate(zip(positions, sample["messages"])):
        color, fill = [(BLUE, SKY), (AMBER, SAND), (GREEN, MINT)][i]
        d.box(x, y, w, h, fill, color)
        d.text(x + 18, y + 36, labels[i], 23, color, True)
        for j, line in enumerate(m["content"].splitlines()):
            d.text(
                x + 18,
                y + 78 + j * 32,
                f"u{source_id}  {line}",
                17 if not mobile else 20,
                mono=True,
            )
            source_id += 1
        if i < 2:
            if mobile:
                d.arrow(260, y + h + 8, 260, positions[i + 1][1] - 13)
            else:
                d.arrow(x + w + 10, y + 85, positions[i + 1][0] - 16, y + 85)
    result_positions = (
        [(32, 710, 456, 125), (32, 858, 456, 125)]
        if mobile
        else [(248, 379, 400, 121), (816, 379, 432, 121)]
    )
    for i, (x, y, w, h) in enumerate(result_positions):
        key = "backup_drink" if i == 0 else "drink"
        color, fill = (AMBER, SAND) if i == 0 else (GREEN, MINT)
        d.box(x, y, w, h, fill, color)
        d.text(x + 20, y + 34, key, 23, color, True, True)
        d.text(x + 20, y + 73, values[key], 29, color, True)
        row = next(r for r in result.ledger if r.key == key)
        d.text(x + 20, y + 103, tr("Evidence: ", "依据来源：") + ", ".join(row.sources), 17)
    if not mobile:
        d.arrow(640, 325, 448, 366, True)
        d.arrow(1064, 325, 1032, 366, True)
        d.text(
            32,
            544,
            tr(
                f"Actual selected rows · {result.stats.input_tokens} → {result.stats.output_tokens} estimated tokens: provenance adds overhead on this tiny example.",
                f"真实输出中的部分状态行 · {result.stats.input_tokens} → {result.stats.output_tokens} 个估算 token：短例子的来源标记会增加开销。",
            ),
            17,
        )
    else:
        d.text(
            32,
            1026,
            tr(
                f"{result.stats.input_tokens} → {result.stats.output_tokens} estimated tokens",
                f"{result.stats.input_tokens} → {result.stats.output_tokens} 个估算 token",
            ),
            21,
            BLUE,
            True,
        )
        d.text(
            32,
            1057,
            tr("Tiny example; source metadata adds overhead.", "短例子会因来源标记增加开销。"),
            18,
        )
    suffix = ("_zh" if zh else "") + ("_mobile" if mobile else "")
    d.write(f"snapshot_semantics{suffix}.svg")


def agent_ledger(zh=False, mobile=False):
    """Show actual included observations and an actually omitted verifier record."""

    def tr(en, cn):
        return cn if zh else en

    sample = json.loads((ROOT / "src/tomc/data/agent.json").read_text())
    result = compile_memory(
        sample["messages"], sample["query"], sample["budget"], sample["strategy"]
    )
    wanted = [("TEST_ERROR", "u26"), ("TEST_ERROR", "u30"), ("GOAL", "u31")]
    selected = [
        next(r for r in result.ledger if r.kind == kind and sid in r.sources)
        for kind, sid in wanted
    ]
    assert all(r.included for r in selected)
    verifier = next(r for r in result.ledger if r.kind == "VERIFIER")
    assert not verifier.included
    evidence = {u.source_id: u.text for u in result.evidence}
    d = Drawing(
        520 if mobile else 1280,
        1390 if mobile else 690,
        tr("TOMC2: preserve observations for the next step", "TOMC2：为下一步保留观察记录"),
        tr(
            "Actual synthetic agent ledger: failure and test reports remain observations, full-suite status is unknown, and the verifier is omitted from reader memory at this budget.",
            "真实合成 Agent ledger：保留失败与测试报告，全量测试状态仍未知，验证命令在当前预算下未进入 reader 记忆。",
        ),
    )
    d.text(
        32,
        44,
        tr("APPLICATION / TOMC2 TRACE ADAPTER", "应用扩展 / TOMC2 软件轨迹适配器"),
        15,
        BLUE,
        True,
    )
    d.text(
        32,
        87,
        tr("Carry observations forward.", "带上观察记录，继续下一步。"),
        29 if mobile else 36,
        bold=True,
    )
    lx, ly, lw, lh = (32, 130, 456, 457) if mobile else (32, 136, 520, 422)
    rx, ry, rw = (32, 643, 456) if mobile else (638, 136, 610)
    d.box(lx, ly, lw, lh, SKY, BLUE)
    d.text(lx + 22, ly + 38, tr("Source excerpts", "原始轨迹节选"), 25, BLUE, True)
    cursor = ly + 77
    for _, sid in wanted:
        d.text(lx + 22, cursor, sid, 18, BLUE, True)
        cursor += 27
        for line in textwrap.wrap(
            evidence[sid], width=39 if mobile else 43, break_long_words=False
        ):
            d.text(lx + 22, cursor, line, 17, mono=True)
            cursor += 25
        cursor += 17
    if mobile:
        d.arrow(260, ly + lh + 9, 260, ry - 12)
    else:
        d.arrow(569, 341, 622, 341)
    row_height = 158 if mobile else 125
    for i, ((kind, sid), row) in enumerate(zip(wanted, selected)):
        y = ry + i * (row_height + 14)
        d.box(rx, y, rw, row_height, MINT, GREEN)
        d.text(rx + 19, y + 31, f"{kind} · {sid}", 22, GREEN, True)
        cursor = y + 59
        for line in textwrap.wrap(
            evidence[sid], width=40 if mobile else 59, break_long_words=False
        ):
            d.text(rx + 19, cursor, line, 17)
            cursor += 23
        d.text(
            rx + 19,
            y + row_height - 13,
            tr("Included in memory · heuristic observation", "已进入记忆 · 启发式观察记录"),
            15,
            GREEN,
        )
    fy = 1180 if mobile else 580
    d.box(32, fy, 456 if mobile else 1216, 135 if mobile else 70, SAND, AMBER)
    d.text(50, fy + 30, tr("VERIFIER · budget omitted", "VERIFIER · 因预算未保留"), 21, AMBER, True)
    d.text(50 if mobile else 570, fy + (65 if mobile else 30), verifier.value, 19, mono=True)
    d.text(
        50,
        fy + (107 if mobile else 55),
        tr("Audit metadata only; not sent to the reader.", "仅在审计记录中可见，未送入 reader。"),
        17,
    )
    footer = tr(
        f"Synthetic trace · {result.stats.input_tokens} → {result.stats.output_tokens} estimated tokens · budget {sample['budget']}",
        f"合成轨迹 · {result.stats.input_tokens} → {result.stats.output_tokens} 个估算 token · 预算 {sample['budget']}",
    )
    d.text(32, 1344 if mobile else 677, footer, 16)
    if mobile:
        d.text(
            32,
            1376,
            tr(
                "Reports are extracted; tests are not re-run.",
                "提取的是报告，不代表重新执行或验证测试。",
            ),
            16,
        )
    suffix = ("_zh" if zh else "") + ("_mobile" if mobile else "")
    d.write(f"agent_ledger{suffix}.svg")
    return {
        "source": "src/tomc/data/agent.json",
        "sha256": hashlib.sha256((ROOT / "src/tomc/data/agent.json").read_bytes()).hexdigest(),
        "input_tokens": result.stats.input_tokens,
        "output_tokens": result.stats.output_tokens,
        "token_budget": sample["budget"],
        "included_rows": [
            {"kind": r.kind, "value": r.value, "sources": r.sources} for r in selected
        ],
        "omitted_verifier": {
            "value": verifier.value,
            "sources": verifier.sources,
            "included": verifier.included,
        },
    }


def evidence():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rows = list(csv.DictReader((ROOT / "benchmarks/aggregate_results/beam_readers.csv").open()))
    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 11, "svg.hashsalt": "tomc-project-evidence-v1"}
    )
    fig, (ax, bar) = plt.subplots(
        1,
        2,
        figsize=(12, 6.1),
        gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.37},
        facecolor="white",
    )
    fig.subplots_adjust(left=0.24, right=0.96, bottom=0.28, top=0.75)
    n_sig = sum(float(r["p_value"]) < 0.05 for r in rows)
    fig.text(
        0.045,
        0.935,
        f"BEAM  /  {len(rows)} readers, {n_sig} significant configurations",
        fontsize=19,
        weight="bold",
        color=INK,
    )
    fig.text(
        0.045,
        0.88,
        "Frozen benchmark-specific TOMC vs BGE hybrid-RAG · 60 conversations per configuration",
        fontsize=11,
        color="#506071",
    )
    for i, r in enumerate(rows):
        x = float(r["full_grid_difference"]) * 100
        lo, hi = float(r["ci_low"]) * 100, float(r["ci_high"]) * 100
        slo, shi = float(r["sensitivity_ci_low"]) * 100, float(r["sensitivity_ci_high"]) * 100
        color = GREEN if float(r["p_value"]) < 0.05 else AMBER
        ax.plot([slo, shi], [i, i], color=color, alpha=0.2, lw=11, solid_capstyle="round")
        ax.errorbar(
            x,
            i,
            xerr=[[x - lo], [hi - x]],
            fmt="o",
            color=color,
            capsize=5,
            markersize=7,
            mfc=color if float(r["p_value"]) < 0.05 else "white",
            zorder=3,
        )
        ax.text(
            x,
            i - 0.23,
            f"+{x:.2f}" + ("  n.s." if float(r["p_value"]) >= 0.05 else ""),
            ha="center",
            fontsize=10,
            color=color,
            weight="bold",
        )
        reduction = float(r["input_reduction"]) * 100
        bar.barh(i, reduction, height=0.42, color="#adcce7", edgecolor=BLUE, linewidth=0.7)
        bar.text(
            reduction + 1,
            i,
            f"{reduction:.2f}%",
            va="center",
            fontsize=10,
            color=BLUE,
            weight="bold",
        )
    labels = [r["reader"] for r in rows]
    ax.set_yticks(np.arange(4), labels)
    bar.set_yticks(np.arange(4), [""] * 4)
    for a in (ax, bar):
        a.set_ylim(3.55, -0.55)
        a.tick_params(axis="both", length=0, pad=8, labelsize=10)
        for side in ("top", "right", "left"):
            a.spines[side].set_visible(False)
        a.spines["bottom"].set_color("#ccd3db")
        a.set_axisbelow(True)
        a.grid(axis="x", color="#ebeff3")
    ax.axvline(0, color="#82909e", lw=1, ls="--")
    ax.set_xlim(-3, 12)
    ax.set_xticks([0, 5, 10])
    ax.set_xlabel("Full-grid score difference (pp)", fontsize=10, labelpad=10)
    ax.set_title(
        "Answer score difference", loc="left", fontsize=13, pad=22, weight="bold", color=GREEN
    )
    bar.set_xlim(0, 48)
    bar.set_xticks([0, 20, 40])
    bar.set_xlabel("Reader input reduction (%)", fontsize=10, labelpad=10)
    bar.set_title(
        "Reader input reduction", loc="left", fontsize=13, pad=22, weight="bold", color=BLUE
    )
    fig.text(
        0.045,
        0.155,
        "Thin: cluster bootstrap 95% CI    Wide: missingness-expanded interval    n.s.: not significant",
        fontsize=10,
        color="#506071",
    )
    fig.text(
        0.045,
        0.105,
        "Flash is positive but not significant. Pro and Flash share a provider family; judge settings vary by run.",
        fontsize=10,
        color=INK,
    )
    fig.text(
        0.045,
        0.055,
        "Evidence is task-specific: IterCOMP is a negative result. Demo adapters differ from the frozen evaluation.",
        fontsize=10,
        color=INK,
    )
    svg_path = OUT / "results_overview.svg"
    fig.savefig(svg_path, metadata={"Date": None})
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n"
    )
    fig.savefig(
        OUT / "results_overview.png", dpi=150, metadata={"Software": "TOMC frozen-evidence figure"}
    )
    plt.close(fig)
    data = {
        "source": "benchmarks/aggregate_results/beam_readers.csv",
        "sha256": hashlib.sha256(
            (ROOT / "benchmarks/aggregate_results/beam_readers.csv").read_bytes()
        ).hexdigest(),
        "effect_column": "full_grid_difference",
        "rows": rows,
    }
    sample, result = sample_result()
    data["synthetic_example"] = {
        "source": "src/tomc/data/snapshot.json",
        "sha256": hashlib.sha256((ROOT / "src/tomc/data/snapshot.json").read_bytes()).hexdigest(),
        "compiled_memory": result.compiled_memory,
        "input_tokens": result.stats.input_tokens,
        "output_tokens": result.stats.output_tokens,
    }
    (OUT / "figure_data.json").write_text(json.dumps(data, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    mark()
    for zh in (False, True):
        for mobile in (False, True):
            overview(zh, mobile)
            snapshot(zh, mobile)
            agent_data = agent_ledger(zh, mobile)
    evidence()
    data = json.loads((OUT / "figure_data.json").read_text())
    data["agent_example"] = agent_data
    (OUT / "figure_data.json").write_text(json.dumps(data, indent=2) + "\n")
    if args.render:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page()
            for name in (
                "project_overview",
                "project_overview_zh",
                "snapshot_semantics",
                "snapshot_semantics_zh",
                "agent_ledger",
                "agent_ledger_zh",
            ):
                page.goto((OUT / f"{name}.svg").as_uri())
                size = page.locator("svg").bounding_box()
                page.set_viewport_size({"width": int(size["width"]), "height": int(size["height"])})
                page.screenshot(path=str(OUT / f"{name}.png"))
            b.close()
    print(
        "Built original project diagrams, bilingual mobile variants and evidence from frozen CSV."
    )


if __name__ == "__main__":
    main()
