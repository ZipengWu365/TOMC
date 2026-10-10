"""Render the README BEAM table in the paper's Table 1 format, extended with the 10M follow-up.

Inputs are public: per-tier aggregates in benchmarks/current_paper/beam_comparisons.csv and the
10M per-question pairs in benchmarks/beam_10m_20261010/paired_scores_10m.csv. Overall pools the
original valid pairs with the 10M pairs within each reader and baseline. Relative changes are
100 * (TOMC / baseline - 1); the mean column averages the three readers before rounding.

    python scripts/make_beam_table.py          # rewrite the marked blocks in README.md / README_zh.md
    python scripts/make_beam_table.py --check  # fail if a README block is out of date
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "benchmarks/current_paper/beam_comparisons.csv"
TEN_M = ROOT / "benchmarks/beam_10m_20261010/paired_scores_10m.csv"
READERS = ["gpt51", "dots3", "flash"]
METHODS = [
    ("llmlingua2_full_history_b8192_v1", "LLMLingua-2-D (2024)"),
    ("longllmlingua_recovery_b8192", "LongLLMLingua (2024)"),
    ("hybrid_brief_pro_auto_b8192", "BRIEF-Pro (2026)"),
    ("llmlingua2_hier64k_full_history_b8192_v1", "LLMLingua-2-H (2024)"),
    ("rag", "BEAM-RAG (2026)"),
    ("light", "LIGHT (2026)"),
]
ABLATION = "beam_compilation_block_off_fixed_raw_v1"
GAIN, LOSS = "#176B47", "#B43B32"


def load():
    """Return {(cohort, method, reader, tier): cell} with n, baseline, tomc and input sums."""
    cells = {}
    for r in csv.DictReader(AGG.open(encoding="utf-8")):
        if r["ability"] != "all" or r["cohort"] not in ("current_main", "ablation_P0_Pro"):
            continue
        n, u = int(r["valid_pairs"]), int(r["usage_complete_pairs"])
        cells[(r["cohort"], r["method"], r["reader"], r["tier"])] = {
            "n": n,
            "b": float(r["baseline_mean_score_0_100"]) * n,
            "t": float(r["tomc_mean_score_0_100"]) * n,
            "u": u,
            "bi": float(r["baseline_mean_input"]) * u,
            "ti": float(r["tomc_mean_input"]) * u,
        }
    for r in csv.DictReader(TEN_M.open(encoding="utf-8")):
        if r["status"] != "valid":
            continue
        c = cells.setdefault(
            ("current_main", r["method"], r["reader"], "10M"),
            {"n": 0, "b": 0.0, "t": 0.0, "u": 0, "bi": 0.0, "ti": 0.0},
        )
        c["n"] += 1
        c["u"] += 1
        c["b"] += 100 * float(r["baseline_score"])
        c["t"] += 100 * float(r["tomc_score"])
        c["bi"] += float(r["baseline_reader_input_tokens"])
        c["ti"] += float(r["tomc_reader_input_tokens"])
    for m, _ in METHODS:  # Overall = original 600-question overall pooled with 10M
        for rd in READERS:
            old, new = (
                cells[("current_main", m, rd, "Overall")],
                cells[("current_main", m, rd, "10M")],
            )
            cells[("current_main", m, rd, "all")] = {k: old[k] + new[k] for k in old}
    return cells


def rel(c):
    return 100 * (c["t"] / c["b"] - 1)


def input_change(cells, m, tier):
    return sum(
        100 * (c["ti"] / c["bi"] - 1)
        for c in (cells[("current_main", m, rd, tier)] for rd in READERS)
    ) / len(READERS)


def arrow(x):
    color, sym = (GAIN, "uparrow") if x >= 0 else (LOSS, "downarrow")
    return f"${{\\color{{{color}}}\\{sym}}}$ {abs(x):.1f}"


def pair(c):
    b, t = round(c["b"] / c["n"], 2), round(c["t"] / c["n"], 2)
    bs, ts = f"{b:.2f}", f"{t:.2f}"
    return f"{'**' + bs + '**' if b >= t else bs} / {'**' + ts + '**' if t >= b else ts}"


def row(label, cs):
    cells = [x for c in cs for x in (pair(c), arrow(rel(c)))]
    return f"| {label} | " + " | ".join(cells) + f" | {arrow(sum(rel(c) for c in cs) / len(cs))} |"


def group(cells, tier, title, ablation_label, with_ablation=True):
    lines = [f"| **{title}** |" + " |" * 7]
    for m, label in METHODS:
        lines.append(row(label, [cells[("current_main", m, rd, tier)] for rd in READERS]))
    abl_tier = "Overall" if tier == "all" else tier
    if with_ablation:
        lines.append(
            row(
                f"*{ablation_label}*",
                [cells[("ablation_P0_Pro", ABLATION, rd, abl_tier)] for rd in READERS],
            )
        )
    return lines


TEXT = {
    "en": {
        "head": "| Baseline | GPT-5.1<br>Base. / TOMC | Δ (%) | Rednote preview<br>Base. / TOMC | Δ (%) | DeepSeek 4.1 Flash<br>Base. / TOMC | Δ (%) | Mean<br>Δ (%) |",
        "groups": {
            "all": "Overall (all lengths)",
            "100K": "100K tokens",
            "500K": "500K tokens",
            "1M": "1M tokens",
            "10M": "10M tokens",
        },
        "ablation": "TOMC w/o compilation",
        "details": "100K, 500K and 1M tokens",
        "input_head": "| Baseline | Overall input change | 10M input change |",
    },
    "zh": {
        "head": "| 基线 | GPT-5.1<br>基线 / TOMC | Δ (%) | Rednote preview<br>基线 / TOMC | Δ (%) | DeepSeek 4.1 Flash<br>基线 / TOMC | Δ (%) | 平均<br>Δ (%) |",
        "groups": {
            "all": "整体（全部长度）",
            "100K": "100K tokens",
            "500K": "500K tokens",
            "1M": "1M tokens",
            "10M": "10M tokens",
        },
        "ablation": "TOMC w/o compilation（去掉编译记录）",
        "details": "100K、500K 和 1M tokens",
        "input_head": "| 基线 | 整体输入变化 | 10M 输入变化 |",
    },
}
ALIGN = "|---|---:|:---|---:|:---|---:|:---|:---|"


def render(lang):
    cells, t = load(), TEXT[lang]
    main = [t["head"], ALIGN, *group(cells, "all", t["groups"]["all"], t["ablation"])]
    main += group(cells, "10M", t["groups"]["10M"], t["ablation"], with_ablation=False)
    tiers = [t["head"], ALIGN]
    for tier in ("100K", "500K", "1M"):
        tiers += group(cells, tier, t["groups"][tier], t["ablation"])
    inputs = [t["input_head"], "|---|---:|---:|"]
    for m, label in METHODS:
        inputs.append(
            f"| {label} | {input_change(cells, m, 'all'):+.2f}% | {input_change(cells, m, '10M'):+.2f}% |"
        )
    return "\n".join(
        [
            *main,
            "",
            f"<details>\n<summary>{t['details']}</summary>\n",
            *tiers,
            "\n</details>",
            "",
            *inputs,
        ]
    )


def replace_block(text, block):
    start, end = "<!-- BEAM_TABLE_START -->", "<!-- BEAM_TABLE_END -->"
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{block}\n{end}{tail}"


def main():
    stale = []
    for path, lang in ((ROOT / "README.md", "en"), (ROOT / "README_zh.md", "zh")):
        text = path.read_text(encoding="utf-8")
        new = replace_block(text, render(lang))
        if new != text:
            stale.append(path.name)
            if "--check" not in sys.argv:
                path.write_bytes(new.encode("utf-8"))
    if "--check" in sys.argv and stale:
        sys.exit(
            f"BEAM table out of date in {', '.join(stale)}; run python scripts/make_beam_table.py"
        )
    print(
        "BEAM table",
        "checked" if "--check" in sys.argv else f"written ({', '.join(stale) or 'unchanged'})",
    )


if __name__ == "__main__":
    main()
