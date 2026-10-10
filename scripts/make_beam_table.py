"""Build the README BEAM tables in the paper's Table 1 format, extended with the 10M follow-up.

Inputs are public: per-tier aggregates in benchmarks/current_paper/beam_comparisons.csv and the
10M per-question pairs in benchmarks/beam_10m_20261010/paired_scores_10m.csv. Overall pools the
original valid pairs with the 10M pairs within each reader and baseline. Relative changes are
100 * (TOMC / baseline - 1); the mean column averages the three readers before rounding.

The script writes booktabs LaTeX sources to assets/beam_table/ and the README blocks (the table
images plus a collapsible text copy). With --render it also compiles the sources with pdflatex and
converts them to SVG/PNG with Poppler; rendering needs a local LaTeX installation.

    python scripts/make_beam_table.py --render  # rewrite sources, README blocks and images
    python scripts/make_beam_table.py --check   # fail if sources, README or images are stale
"""

from __future__ import annotations

import csv
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGG = ROOT / "benchmarks/current_paper/beam_comparisons.csv"
TEN_M = ROOT / "benchmarks/beam_10m_20261010/paired_scores_10m.csv"
OUT = ROOT / "assets/beam_table"
READERS = ["gpt51", "dots3", "flash"]
READER_NAMES = ["GPT-5.1", "Rednote preview", "DeepSeek 4.1 Flash"]
METHODS = [
    ("llmlingua2_full_history_b8192_v1", "LLMLingua-2-D (2024)"),
    ("longllmlingua_recovery_b8192", "LongLLMLingua (2024)"),
    ("hybrid_brief_pro_auto_b8192", "BRIEF-Pro (2026)"),
    ("llmlingua2_hier64k_full_history_b8192_v1", "LLMLingua-2-H (2024)"),
    ("rag", "BEAM-RAG (2026)"),
    ("light", "LIGHT (2026)"),
]
TIERS = [
    ("all", "Overall (all lengths)"),
    ("100K", "100K tokens"),
    ("500K", "500K tokens"),
    ("1M", "1M tokens"),
    ("10M", "10M tokens"),
]
ABLATION = "beam_compilation_block_off_fixed_raw_v1"
ABLATION_LABEL = "TOMC w/o compilation"
GAIN, LOSS = "176B47", "B43B32"


def load():
    """Return {(cohort, method, reader, tier): cell} with n, score sums and input sums."""
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


def input_rel(c):
    return 100 * (c["ti"] / c["bi"] - 1)


def scores(c):
    return round(c["b"] / c["n"], 2), round(c["t"] / c["n"], 2)


def rows(cells):
    """Yield (tier_title, label, reader_cells, is_ablation) in table order."""
    for tier, title in TIERS:
        for m, label in METHODS:
            yield title, label, [cells[("current_main", m, rd, tier)] for rd in READERS], False
        if tier != "10M":  # the 10M compilation ablation is not yet available
            abl = "Overall" if tier == "all" else tier
            yield (
                title,
                ABLATION_LABEL,
                [cells[("ablation_P0_Pro", ABLATION, rd, abl)] for rd in READERS],
                True,
            )


# ---------- LaTeX (paper format) ----------

DASH = r"\noalign{\vskip2pt\hbox to\linewidth{\leaders\hbox{\vrule width2.5pt height.35pt\hskip2pt}\hfill}\vskip2pt}"
DOC_HEAD = r"""\documentclass[border=10pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{times}
\usepackage{amsmath,amssymb,booktabs,xcolor}
\definecolor{beamgain}{HTML}{%s}
\definecolor{beamloss}{HTML}{%s}
\begin{document}
\begin{minipage}{5.5in}
""" % (GAIN, LOSS)
DOC_TAIL = "\\end{minipage}\n\\end{document}\n"


def tex_delta(x):
    color, arrow = ("beamgain", "uparrow") if x >= 0 else ("beamloss", "downarrow")
    return f"\\textcolor{{{color}}}{{$\\{arrow}{abs(x):.1f}$}}"


def tex_pair(c):
    b, t = scores(c)
    bs = f"\\textbf{{{b:.2f}}}" if b >= t else f"{b:.2f}"
    ts = f"\\textbf{{{t:.2f}}}" if t >= b else f"{t:.2f}"
    return f"{bs}\\,/\\,{ts}"


def quality_tex(cells):
    out = [
        DOC_HEAD,
        "BEAM answer quality across history lengths. Cells pair baseline / full TOMC scores (0--100); "
        "dashed rows pair TOMC w/o compilation / full TOMC from separate matched batches. "
        "Bold marks the higher paired score.\\par\\medskip",
        "{\\small\\setlength{\\tabcolsep}{1pt}\\renewcommand{\\arraystretch}{1.12}",
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}lrlrlrll@{}}",
        "\\toprule",
        " & "
        + " & ".join(f"\\multicolumn{{2}}{{c}}{{{n}}}" for n in READER_NAMES)
        + " & Mean \\\\",
        "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}",
        "Baseline"
        + " & {\\fontsize{8}{9}\\selectfont Base. / TOMC} & $\\Delta$ (\\%)" * 3
        + " & $\\Delta$ (\\%) \\\\",
    ]
    current = None
    for title, label, cs, ablation in rows(cells):
        if title != current:
            out += ["\\midrule", f"\\multicolumn{{8}}{{l}}{{\\textbf{{{title}}}}}\\\\"]
            current = title
        if ablation:
            out.append(DASH)
        cols = [x for c in cs for x in (tex_pair(c), tex_delta(rel(c)))]
        out.append(f"{label} & " + " & ".join(cols) + f" & {tex_delta(sum(map(rel, cs)) / 3)} \\\\")
    out += [
        "\\bottomrule",
        "\\end{tabular*}}",
        "\\par\\smallskip{\\footnotesize\\raggedright",
        "\\textbf{Reading.} $\\Delta=100(T/B-1)$; Mean averages reader-wise changes before rounding. "
        "Green $\\uparrow$/red $\\downarrow$: improvement/decline. D/H: direct/hierarchical LLMLingua-2. "
        "\\textbf{Comparisons.} Overall pools each reader's valid pairs across the four lengths descriptively; "
        "paired sets and scoring protocols vary. w/o compilation removes compiled records/instructions, "
        "retaining source text and routing; compilation ablations cover 100K--1M only. "
        "10M: 200 questions from 10 sessions, 3,596 of 3,600 pairs valid.\\par}",
        DOC_TAIL,
    ]
    return "\n".join(out)


def signed(x):
    return f"$-${abs(x):.2f}" if x < 0 else f"$+${x:.2f}"


def input_tex(cells):
    out = [
        DOC_HEAD.replace("5.5in", "4.6in"),
        "Reader-input change of TOMC relative to each baseline (\\%). Negative values mean TOMC sends "
        "fewer API input tokens; Mean averages the three readers.\\par\\medskip",
        "{\\small\\setlength{\\tabcolsep}{1pt}\\renewcommand{\\arraystretch}{1.12}",
        "\\begin{tabular*}{\\linewidth}{@{\\extracolsep{\\fill}}lrrrr@{}}",
        "\\toprule",
        "Baseline & " + " & ".join(READER_NAMES) + " & Mean \\\\",
    ]
    for tier, title in (("all", "Overall (all lengths)"), ("10M", "10M tokens")):
        out += ["\\midrule", f"\\multicolumn{{5}}{{l}}{{\\textbf{{{title}}}}}\\\\"]
        for m, label in METHODS:
            vals = [input_rel(cells[("current_main", m, rd, tier)]) for rd in READERS]
            out.append(
                f"{label} & " + " & ".join(map(signed, vals)) + f" & {signed(sum(vals) / 3)} \\\\"
            )
    out += [
        "\\bottomrule",
        "\\end{tabular*}}",
        "\\par\\smallskip{\\footnotesize\\raggedright",
        "Input is mean API reader input, including prompt overhead. The direct LLMLingua-2 1M run produced "
        "200 empty memories, so its low input there is not successful compression.\\par}",
        DOC_TAIL,
    ]
    return "\n".join(out)


# ---------- Markdown (collapsible text copy) ----------


def md_pair(c):
    b, t = scores(c)
    return (
        f"{'**%.2f**' % b if b >= t else '%.2f' % b} / {'**%.2f**' % t if t >= b else '%.2f' % t}"
    )


def md_delta(x):
    return f"{'↑' if x >= 0 else '↓'} {abs(x):.1f}"


TEXT = {
    "en": {
        "alt_q": "BEAM answer quality across history lengths: baseline / TOMC score pairs and relative changes for three readers, six baselines and TOMC w/o compilation, at Overall, 100K, 500K, 1M and 10M tokens.",
        "alt_i": "Reader-input change of TOMC relative to each baseline, Overall and 10M.",
        "summary": "Tables as text",
        "head": "| Baseline | GPT-5.1 | Δ (%) | Rednote preview | Δ (%) | DeepSeek 4.1 Flash | Δ (%) | Mean Δ (%) |",
        "input_head": "| Baseline | Overall input change | 10M input change |",
    },
    "zh": {
        "alt_q": "BEAM 各历史长度的回答质量：三个模型、六种基线与 TOMC w/o compilation 的 基线 / TOMC 分数对及相对变化，分为整体、100K、500K、1M 和 10M。",
        "alt_i": "TOMC 相对各基线的模型输入变化，整体与 10M。",
        "summary": "表格文字版",
        "head": "| 基线 | GPT-5.1 | Δ (%) | Rednote preview | Δ (%) | DeepSeek 4.1 Flash | Δ (%) | 平均 Δ (%) |",
        "input_head": "| 基线 | 整体输入变化 | 10M 输入变化 |",
    },
}


def readme_block(cells, lang):
    t = TEXT[lang]
    md, current = [t["head"], "|---|---:|:---|---:|:---|---:|:---|:---|"], None
    for title, label, cs, _ in rows(cells):
        if title != current:
            md.append(f"| **{title}** |" + " |" * 7)
            current = title
        cols = [x for c in cs for x in (md_pair(c), md_delta(rel(c)))]
        md.append(f"| {label} | " + " | ".join(cols) + f" | {md_delta(sum(map(rel, cs)) / 3)} |")
    md += ["", t["input_head"], "|---|---:|---:|"]
    for m, label in METHODS:
        overall, ten = (
            sum(input_rel(cells[("current_main", m, rd, tier)]) for rd in READERS) / 3
            for tier in ("all", "10M")
        )
        md.append(f"| {label} | {overall:+.2f}% | {ten:+.2f}% |")
    return "\n".join(
        [
            '<a href="assets/beam_table/beam_quality.png">',
            f'  <img src="assets/beam_table/beam_quality.svg" alt="{t["alt_q"]}" width="900">',
            "</a>",
            "",
            '<a href="assets/beam_table/beam_input.png">',
            f'  <img src="assets/beam_table/beam_input.svg" alt="{t["alt_i"]}" width="760">',
            "</a>",
            "",
            f"<details>\n<summary>{t['summary']}</summary>\n",
            *md,
            "\n</details>",
        ]
    )


def replace_block(text, block):
    start, end = "<!-- BEAM_TABLE_START -->", "<!-- BEAM_TABLE_END -->"
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{block}\n{end}{tail}"


# ---------- rendering ----------


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(name, tex):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / f"{name}.tex").write_text(tex, encoding="utf-8", newline="\n")
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(["pdftocairo", "-svg", f"{name}.pdf", f"{name}.svg"], cwd=tmp, check=True)
        subprocess.run(
            ["pdftoppm", "-r", "250", "-png", "-singlefile", f"{name}.pdf", name],
            cwd=tmp,
            check=True,
        )
        svg = (tmp / f"{name}.svg").read_text(encoding="utf-8")
        # White page so the table stays readable in GitHub's dark theme.
        svg = re.sub(
            r"(<svg[^>]*>)", r'\1\n<rect width="100%" height="100%" fill="#ffffff"/>', svg, count=1
        )
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8", newline="\n")
        shutil.copyfile(tmp / f"{name}.png", OUT / f"{name}.png")


def main():
    check, do_render = "--check" in sys.argv, "--render" in sys.argv
    cells = load()
    sources = {"beam_quality": quality_tex(cells), "beam_input": input_tex(cells)}
    stamp = "".join(f"{sha(tex)}  {name}.tex\n" for name, tex in sources.items())
    stale = []
    OUT.mkdir(parents=True, exist_ok=True)
    for name, tex in sources.items():
        path = OUT / f"{name}.tex"
        if not path.exists() or path.read_text(encoding="utf-8") != tex:
            stale.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.write_text(tex, encoding="utf-8", newline="\n")
    for path, lang in ((ROOT / "README.md", "en"), (ROOT / "README_zh.md", "zh")):
        text = path.read_text(encoding="utf-8")
        new = replace_block(text, readme_block(cells, lang))
        if new != text:
            stale.append(path.name)
            if not check:
                path.write_bytes(new.encode("utf-8"))
    stamp_path = OUT / "RENDERED_FROM.sha256"
    images = [OUT / f"{n}.{ext}" for n in sources for ext in ("svg", "png")]
    if (
        not stamp_path.exists()
        or stamp_path.read_text(encoding="utf-8") != stamp
        or not all(p.exists() for p in images)
    ):
        if do_render:
            for name, tex in sources.items():
                render(name, tex)
            stamp_path.write_text(stamp, encoding="utf-8", newline="\n")
        else:
            stale.append("table images (run with --render)")
    if check and stale:
        sys.exit(
            "BEAM tables out of date: "
            + ", ".join(stale)
            + "; run python scripts/make_beam_table.py --render"
        )
    print("BEAM tables", "checked" if check else f"updated ({', '.join(stale) or 'unchanged'})")


if __name__ == "__main__":
    main()
