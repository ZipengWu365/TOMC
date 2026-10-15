"""Verify and render the current manuscript's aggregate evidence without model calls."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "benchmarks/current_paper"
READERS = {"gpt51": "GPT-5.1", "dots3": "Rednote preview", "flash": "DeepSeek 4.1 Flash"}
METHODS = {
    "llmlingua2_full_history_b8192_v1": "LLMLingua-2-D",
    "longllmlingua_recovery_b8192": "LongLLMLingua",
    "hybrid_brief_pro_auto_b8192": "BRIEF-Pro",
    "llmlingua2_hier64k_full_history_b8192_v1": "LLMLingua-2-H",
    "rag": "BEAM-RAG",
    "light": "LIGHT",
}
TIERS = ["Overall", "100K", "500K", "1M"]


def csv_rows(name):
    with (DATA / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def close(a, b):
    if not math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-8):
        raise ValueError(f"Aggregate mismatch: {a} != {b}")


def comparisons(cohort="current_main", tier="Overall"):
    return [
        r for r in csv_rows("beam_comparisons.csv") if r["cohort"] == cohort and r["tier"] == tier
    ]


def verify():
    manifest = json.loads((DATA / "manifest.json").read_text())
    for name, ref in manifest["exports"].items():
        path = (DATA / name).resolve()
        if (
            not path.is_relative_to(ROOT)
            or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]
        ):
            raise ValueError(f"Snapshot hash mismatch: {name}")
        if "rows" in ref and len(csv_rows(name)) != ref["rows"]:
            raise ValueError(f"Row count mismatch: {name}")
    rows = csv_rows("beam_comparisons.csv")
    keys = [(r["cohort"], r["reader"], r["method"], r["tier"]) for r in rows]
    if len(keys) != len(set(keys)) or len(rows) != 84:
        raise ValueError("Expected 72 baseline and 12 Pro-judged ablation aggregates")
    for r in rows:
        if int(r["valid_pairs"]) != int(r["usage_complete_pairs"]):
            raise ValueError("Input and quality must use the same paired set")
        close(
            r["input_change_pct"],
            100 * (float(r["tomc_mean_input"]) / float(r["baseline_mean_input"]) - 1),
        )
        close(r["input_saving_pct"], -float(r["input_change_pct"]))
        close(
            r["quality_delta_pp"],
            float(r["tomc_mean_score_0_100"]) - float(r["baseline_mean_score_0_100"]),
        )
    for r in csv_rows("beam_three_reader.csv"):
        group = [x for x in comparisons(tier=r["tier"]) if x["method"] == r["method"]]
        if len(group) != 3 or {x["reader"] for x in group} != set(READERS):
            raise ValueError("Incomplete three-reader comparison")
        for aggregate, field in [
            ("mean_input_change_pct", "input_change_pct"),
            ("mean_input_saving_pct", "input_saving_pct"),
            ("mean_quality_delta_pp", "quality_delta_pp"),
        ]:
            close(r[aggregate], mean(float(x[field]) for x in group))
    long = json.loads((DATA / "beam_long_history.json").read_text())
    for item in long["summary"]:
        for r in item["readers"]:
            group = [
                x
                for x in rows
                if x["cohort"] == "current_main"
                and x["method"] == item["method"]
                and x["reader"] == r["reader"]
                and x["tier"] in {"500K", "1M"}
            ]
            n = sum(int(x["valid_pairs"]) for x in group)
            close(r["n"], n)
            for key, field, scale in [
                ("tomc_score", "tomc_mean_score_0_100", 0.01),
                ("baseline_score", "baseline_mean_score_0_100", 0.01),
                ("tomc_input_tokens", "tomc_mean_input", 1),
                ("baseline_input_tokens", "baseline_mean_input", 1),
            ]:
                close(
                    r[key], scale * sum(float(x[field]) * int(x["valid_pairs"]) for x in group) / n
                )
            close(r["gain"], 100 * (r["tomc_score"] / r["baseline_score"] - 1))
            close(r["saving"], 100 * (1 - r["tomc_input_tokens"] / r["baseline_input_tokens"]))
        close(item["gain"], mean(r["gain"] for r in item["readers"]))
        close(item["saving"], mean(r["saving"] for r in item["readers"]))
    for r in csv_rows("niah_repaired.csv"):
        close(r["full_minus_removal_f1_pp"], float(r["full_f1"]) - float(r["removal_f1"]))
        close(
            r["removal_token_savings_percent"],
            100 * (1 - float(r["mean_input_removal"]) / float(r["mean_input_full"])),
        )
    for r in csv_rows("beam_common_abilities.csv"):
        if r["tier"] == "500K/1M equal mean":
            group = [
                x
                for x in csv_rows("beam_common_abilities.csv")
                if x["reader"] == r["reader"]
                and x["method"] == r["method"]
                and x["ability"] == r["ability"]
                and x["tier"] in {"500K", "1M"}
            ]
            close(r["score"], mean(float(x["score"]) for x in group))
    return manifest


def beam_table(tier="Overall"):
    if tier not in TIERS:
        raise ValueError("Unknown history tier")
    rows = comparisons(tier=tier)
    index = {(r["method"], r["reader"]): r for r in rows}
    lines = [
        "| Baseline memory | GPT-5.1<br>Baseline / TOMC | Rednote preview<br>Baseline / TOMC | DeepSeek 4.1 Flash<br>Baseline / TOMC | Mean input change |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, label in METHODS.items():
        group = [index[method, rd] for rd in READERS]
        scores = [
            f"{float(r['baseline_mean_score_0_100']):.2f} / **{float(r['tomc_mean_score_0_100']):.2f}**"
            for r in group
        ]
        change = mean(float(r["input_change_pct"]) for r in group)
        lines.append(f"| {label} | " + " | ".join(scores) + f" | {change:+.2f}% |")
    return "\n".join(lines)


def beam_intro():
    return (
        "**Each score cell is Baseline / TOMC (0–100).** Within a pair, the same reader answers "
        "the same questions using memory from the named baseline or memory from TOMC. "
        "Bold marks the TOMC score for easy scanning. Combining TOMC with a baseline is "
        "a separate configuration that these comparisons do not test.\n\n"
        "Questions and scoring are matched within each comparison. The matched set and scoring "
        "protocol can differ across rows, so compare the two scores within a cell. "
        "Input change measures TOMC relative to that baseline; negative means fewer API input tokens. "
        "The mean averages the three readers' percentage changes equally.\n\n"
        "Each method/reader comparison planned 600 questions covering ten memory abilities: "
        "60 conversations, with 20 at each of 100K, 500K and 1M history tokens. "
        "Memory is capped at 8,192 cl100k_base tokens. API input also includes the question and "
        "prompt overhead; the history lengths label the original conversations.\n\n"
        "LLMLingua-2-D and -H are the direct and hierarchical configurations. The direct 1M run "
        "has 200 empty memories before its final budget check. Their scores remain included, "
        "and the cause is unresolved. Its low token count therefore includes failed memory construction."
    )


def protocol_text():
    rows = {(r["method"], r["reader"]): r for r in comparisons()}
    lines = [
        "Each cell below gives overall valid pairs / scoring protocol. Every comparison planned 600 questions.",
        "",
        "| Baseline | GPT-5.1 | Rednote preview | DeepSeek 4.1 Flash |",
        "|---|---:|---:|---:|",
    ]
    for method, name in METHODS.items():
        group = [rows[method, reader] for reader in READERS]
        cells = [f"{r['valid_pairs']} / {r['protocol'].split('_')[0]}" for r in group]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "A: current RAG/LIGHT, native single-answer Flash scoring. "
        "B: archived Pro grouped scoring. C: archived Flash grouped scoring. "
        "D: archived Flash-reader answers, native single-answer Flash scoring. "
        "E: Rednote direct LLMLingua-2 follow-up, native single-answer Flash scoring. "
        "Scoring protocol is shared within a pair, but differs across these groups.",
    ]
    return "\n".join(lines)


def ablation_text():
    lines = [
        "**What do the compiled records add?** This comparison removes the reader-visible "
        "records and accompanying instructions, keeping source text and upstream routing fixed. "
        "The freed space is left empty. Each pair uses matched Pro judging in a separate dated "
        "batch from the baseline comparisons above.",
        "",
        "| Reader | Pairs | Full TOMC / TOMC w/o compilation | Full − removal (points) | Full input change |",
        "|---|---:|---:|---:|---:|",
    ]
    index = {r["reader"]: r for r in comparisons("ablation_P0_Pro")}
    for rd, name in READERS.items():
        r = index[rd]
        lines.append(
            f"| {name} | {r['valid_pairs']} | {float(r['tomc_mean_score_0_100']):.2f} / {float(r['baseline_mean_score_0_100']):.2f} | {float(r['quality_delta_pp']):+.2f} | {float(r['input_change_pct']):+.2f}% |"
        )
    lines += [
        "",
        "Compiled records improve temporal reasoning for all three readers, while event ordering "
        "declines for all three. Overall changes also vary by reader. The table reports quality "
        "and input separately.",
    ]
    return "\n".join(lines)


def ruler_text():
    rows = csv_rows("ruler_conditions.csv")
    lines = [
        "These targeted tests use 100 examples per task from RULER generators, with a "
        "65,536-token sequence limit. NIAH and QA2 measure token F1; VT measures answer-item "
        "recall. Scores use the study's task-specific evaluation, on a 0–100 scale. "
        "Memory construction uses a budget of 4,096 tokens estimated from text length; "
        "reported API input is measured separately.",
        "",
        "| Archived task comparison | Query mean | Full/state mean | Input saved vs Query |",
        "|---|---:|---:|---:|",
    ]
    for task, method, label in [
        ("NIAH", "tomc_plus_raw", "NIAH · retained-source result¹"),
        ("VT", "tomc", "VT · state-route diagnostic"),
        ("QA2", "tomc_plus_raw", "QA2 · full TOMC"),
    ]:
        group = {(r["reader"], r["method"]): r for r in rows if r["task"] == task}
        query = [group[rd, "query_topk"] for rd in READERS]
        full = [group[rd, method] for rd in READERS]
        savings = mean(
            100 * (1 - float(t["input_tokens"]) / float(q["input_tokens"]))
            for t, q in zip(full, query)
        )
        lines.append(
            f"| {label} | {mean(float(r['score']) for r in query):.2f} | {mean(float(r['score']) for r in full):.2f} | {savings:.1f}% |"
        )
    lines += [
        "",
        "¹ A packing error removed the compiled blocks from the archived NIAH full memories. "
        "The 88.30 F1 therefore measures the retained source text. The archived source-removal "
        "condition scored zero after the same packing failure, so it cannot isolate the effect "
        "of removing source text.",
        "",
        "**NIAH after the packing fix.** A separate paired rerun keeps compiled records "
        "byte-identical and removes only the extra source block, leaving the freed space empty. "
        "Query and head–tail were not rerun, so comparisons with Query remain in the archived "
        "table above. The savings below use this rerun's full TOMC as the reference.",
        "",
        "| Reader | Pairs | Full TOMC F1 | TOMC w/o extra source F1 | Input saved vs full TOMC |",
        "|---|---:|---:|---:|---:|",
    ]
    repair = {r["reader"]: r for r in csv_rows("niah_repaired.csv")}
    for rd, name in READERS.items():
        r = repair[rd]
        lines.append(
            f"| {name} | {r['common_valid_N']} | {float(r['full_f1']):.2f} | {float(r['removal_f1']):.2f} | {float(r['removal_token_savings_percent']):.2f}% |"
        )
    lines += [
        "",
        "Flash's one-point gap comes from the single prespecified example with no needle; "
        "both conditions score 100 on the 99 needle examples. The differences are descriptive.",
        "",
        "**VT:** full-history state replay reaches 100% recall for all three readers, "
        "including after candidate rows are removed. This diagnostic uses the state route: "
        "operations are replayed over the full history. Replaying only selected evidence "
        "reaches about 20.4–20.6%, because selection can omit earlier dependencies.",
        "",
        "**QA2:** retaining original text from the same selected evidence outperforms records alone "
        "and records plus source for every reader. Removing the extra source block from full TOMC "
        "lowers mean F1 to 8.44. These questions need source wording to connect facts across passages.",
    ]
    return "\n".join(lines)


def resources_text():
    data = json.loads((DATA / "construction.json").read_text())
    times = {r[0]: r[3] for r in data["timing_rows"] if r[1] != "Query retrieval"}
    lines = [
        "| Method | Auxiliary neural stage | Recorded construction time | Peak GPU allocation (GiB) | Peak host RAM (RSS, GiB) |",
        "|---|---|---:|---:|---:|",
    ]
    for name, neural, gpu, ram in data["memory_rows"]:
        time = times["LIGHT" if name == "LIGHT (worker)" else name]
        lines.append(f"| {name} | {neural} | {time} | {gpu} | {ram} |")
    lines += [
        "",
        "TOMC averaged **4.21 s/call** over six CPU construction replays and used "
        "**3.75 GiB** peak host RAM (process RSS). Timing excludes imports, input loading "
        "and tokenizer warm-up.\n\n"
        "The recorded LongLLMLingua and BRIEF-Pro times measure construction stages per call. "
        "Other rows use per-conversation or full-batch times, as labeled. These measurements "
        "describe the recorded stages; they do not establish matched end-to-end speedups. "
        "BEAM-RAG reuses its index and separately averages 9.71 ms/query for retrieval.",
        "",
        "GPU allocation and host RAM are separate observed peaks. LIGHT's memory measurement "
        "covers one writer/filter worker, including its allocated KV pool; its 41.53 h timing "
        "covers the full 600-memory batch. The worker measurement excludes BGE and remote "
        "summarization, and BRIEF-Pro excludes candidate construction. LLMLingua-2 was measured "
        "with its CUDA implementation. Reader inference and judging are excluded throughout.",
    ]
    return "\n".join(lines)


def render_report():
    manifest = verify()
    lines = [
        "# Current paper results",
        "",
        f"Synced {manifest['synced_on']} from manuscript commit `{manifest['paper_commit'][:7]}`. "
        "The report uses recorded benchmark measurements.",
        "",
        "## BEAM: three readers and six baseline configurations",
        "",
        beam_intro(),
        "",
    ]
    for tier in TIERS:
        lines += [f"### {tier}", "", beam_table(tier), ""]
    lines += ["### Pair counts and scoring protocols", "", protocol_text(), ""]
    lines += [
        "TOMC has higher quality means in all **36 reader × baseline × length comparisons "
        "at 500K/1M**, and in all 18 overall comparisons. At 100K, Flash with LIGHT is an exception. "
        "These are comparisons of mean quality; significance and individual abilities need separate analysis.",
        "",
        "Against LIGHT and hierarchical LLMLingua-2, overall equal-reader input savings are "
        "**34.77% and 34.35%**, respectively. Reader input is not end-to-end cost.",
        "",
        "### Pooled long histories (500K and 1M)",
        "",
        "Within each reader, pool matched questions from 500K and 1M, then calculate quality "
        "and input changes. Average the three readers' changes equally.",
        "",
        "| Baseline | Relative quality gain | Reader input saving |",
        "|---|---:|---:|",
    ]
    for r in json.loads((DATA / "beam_long_history.json").read_text())["summary"]:
        lines.append(f"| {r['name']} | {r['gain']:+.2f}% | {r['saving']:+.2f}% |")
    lines += [
        "",
        "Negative saving means TOMC uses more input. BRIEF-Pro uses the archived candidates "
        "from hybrid retrieval. BEAM-RAG uses BGE dense retrieval; historical Hybrid-RAG is a "
        "separate control. LIGHT uses the documented writer/filter, API summarization and 8K "
        "packing configuration. These results apply to those study configurations.",
        "",
        "### Ten memory abilities",
        "",
        "TOMC, BEAM-RAG and LIGHT are compared on questions valid for all three methods "
        "within each reader and history tier. The 500K and 1M ability means receive equal weight. Cells below are "
        "**TOMC / BEAM-RAG / LIGHT**, all on 0–100 scales.",
        "",
        "| Ability | GPT-5.1 | Rednote preview | DeepSeek 4.1 Flash |",
        "|---|---:|---:|---:|",
    ]
    abilities = [
        r for r in csv_rows("beam_common_abilities.csv") if r["tier"] == "500K/1M equal mean"
    ]
    idx = {(r["reader"], r["ability"], r["method"]): float(r["score"]) for r in abilities}
    for ability in dict.fromkeys(r["ability"] for r in abilities):
        cells = [
            " / ".join(
                f"{idx[rd, ability, method]:.2f}" for method in ["TOMC", "BEAM-RAG", "LIGHT"]
            )
            for rd in READERS
        ]
        lines.append(
            "| " + ability.replace("_", " ").capitalize() + " | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "TOMC leads both controls on temporal reasoning, information extraction, contradiction "
        "resolution, multi-session reasoning and event ordering across these readers. It trails "
        "both on instruction following, BEAM-RAG on abstention, and LIGHT on summarization.",
        "",
        "## BEAM compilation ablation",
        "",
        ablation_text(),
        "",
        "## RULER-derived mechanisms and component ablations",
        "",
        ruler_text(),
        "",
        "## Construction efficiency and resources",
        "",
        resources_text(),
        "",
        "## Evidence and implementation scope",
        "",
        "The demo parses explicit operations and retrieves lines with BM25. The benchmark "
        "uses the archived task-specific selection, operations and packing configurations. "
        "In particular, paper BEAM-RAG uses BGE dense retrieval, and historical Hybrid-RAG "
        "is a separate method from the demo's automatic router. TOMC prepares text memory "
        "on CPU without auxiliary neural inference; your chosen model then reads that memory and answers.",
        "",
        "Run `python benchmarks/reproduce/current.py` to check file hashes and recalculate "
        "paired score/input changes, reader averages, pooled long-history results, common-question "
        "ability means and the repaired NIAH ablation. The script rebuilds this report from "
        "saved aggregate measurements. It makes no API calls or new statistical tests.",
        "",
        "[Snapshot and provenance](https://github.com/ZipengWu365/TOMC/tree/main/benchmarks/current_paper) · "
        "[Historical four-reader Hybrid-RAG results](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/HISTORICAL_BEAM.md)",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    report = render_report()
    (ROOT / "benchmarks/RESULTS.md").write_text(report, encoding="utf-8", newline="\n")
    (ROOT / "docs/paper_results.md").write_text(report, encoding="utf-8", newline="\n")
    print(
        "Verified current paper snapshot; rebuilt current BEAM, RULER and resource report. No API calls."
    )
