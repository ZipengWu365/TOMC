"""Recompute frozen BEAM statistics from numeric cluster aggregates, without APIs."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def bootstrap(values: list[float], tiers: list[str]) -> tuple[float, float]:
    """Original tier-stratified 10,000-resample procedure, seed and nearest-order quantile."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, tier in zip(values, tiers):
        grouped[tier].append(value)
    rng = random.Random(2026080901)
    estimates = []
    for _ in range(10_000):
        estimates.append(
            mean(mean(rng.choice(grouped[t]) for _ in grouped[t]) for t in sorted(grouped))
        )
    estimates.sort()
    return estimates[round(0.025 * 9999)], estimates[round(0.975 * 9999)]


def sign_flip(values: list[float]) -> float:
    """Original 100,000 flips with exact seed; vectorized except near floating-point ties."""
    rng = random.Random(2026080902)
    observed = abs(mean(values))
    extreme = 0
    vector = np.asarray(values)
    for _ in range(100):
        signs = np.fromiter(
            (1 if rng.getrandbits(1) else -1 for _ in range(1000 * len(values))), dtype=np.int8
        ).reshape(1000, len(values))
        stats = np.abs(np.mean(signs * vector, axis=1))
        decisions = stats >= observed
        for i in np.flatnonzero(np.abs(stats - observed) < 1e-12):
            decisions[i] = (
                abs(mean(v if s == 1 else -v for v, s in zip(values, signs[i]))) >= observed
            )
        extreme += int(decisions.sum())
    return (extreme + 1) / 100001


def rebuild() -> list[dict]:
    """Verify every recomputed primary quantity against the full-precision frozen export."""
    with (ROOT / "benchmarks/aggregate_results/beam_readers.csv").open() as f:
        summaries = list(csv.DictReader(f))
    with (ROOT / "benchmarks/aggregate_results/beam_clusters.csv").open() as f:
        clusters = list(csv.DictReader(f))
    results = []
    for summary in summaries:
        rows = [r for r in clusters if r["reader_id"] == summary["reader_id"]]
        assert len(rows) == 60
        diffs = [float(r["paired_difference_sum"]) / 10 for r in rows]
        observed = sum(int(r["observed"]) for r in rows)
        missing = sum(int(r["missing"]) for r in rows)
        assert observed + missing == 600
        ci = bootstrap(diffs, [r["tier"] for r in rows])
        rebuilt = {
            "tomc": sum(float(r["tomc_score_sum"]) for r in rows) / observed,
            "hybrid_rag": sum(float(r["rag_score_sum"]) for r in rows) / observed,
            "difference": sum(float(r["paired_difference_sum"]) for r in rows) / observed,
            "full_grid_difference": mean(diffs),
            "ci_low": ci[0],
            "ci_high": ci[1],
            "sensitivity_ci_low": ci[0] - missing / 600,
            "sensitivity_ci_high": ci[1] + missing / 600,
            "p_value": sign_flip(diffs),
            "input_reduction": 1
            - int(summary["tomc_input_tokens"]) / int(summary["rag_input_tokens"]),
        }
        for key, value in rebuilt.items():
            if not math.isclose(value, float(summary[key]), rel_tol=1e-10, abs_tol=1e-12):
                raise ValueError(f"Frozen result mismatch: {summary['reader_id']}/{key}")
        results.append({**summary, **rebuilt})
        print(
            f"Verified {summary['reader']}: effect={rebuilt['difference'] * 100:.2f} pp, p={rebuilt['p_value']:.6g}",
            flush=True,
        )
    return results


def render(results: list[dict]) -> None:
    """Regenerate the result card and an exportable plot with uncertainty."""
    lines = [
        "# Historical four-reader BEAM comparison",
        "",
        "Historical Hybrid-RAG batch; superseded as the main result story by [current paper results](RESULTS.md). "
        "Rebuilt offline from [reader aggregates](aggregate_results/beam_readers.csv) and "
        "[240 numeric conversation aggregates](aggregate_results/beam_clusters.csv). Freeze: 2026-09-04.",
        "",
        "| Reader | TOMC | hybrid-RAG | Δ pp | p | Reader input reduction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['reader']} | {r['tomc']:.4f} | {r['hybrid_rag']:.4f} | +{r['difference'] * 100:.2f} | {r['p_value']:.3g} | {r['input_reduction']:.2%} |"
        )
    lines += [
        "",
        "All four directions are positive; three tests have p < 0.05. Flash is not significant. "
        "Pro and Flash share a provider family. UOB judges Pro; DeepSeek-V4-Pro judges the UOB, Rednote and Flash replications.",
        "",
        "Each configuration has 60 independent conversations and 600 planned paired questions. "
        "Pro/UOB/Rednote/Flash have 2/9/6/5 missing paired judgments. Score columns and Δ above use available pairs. "
        "The inferential target is the conversation-balanced full-grid difference, assigning zero only as the midpoint "
        "of each missing difference's [-1,1] domain. The bootstrap is tier-stratified; the sign-flip test uses conversation clusters. "
        "Memory budgets and tokenizer/usage conventions differ from this synthetic demo.",
        "",
        "| Reader | Full-grid Δ pp | Bootstrap 95% CI (pp) | Missingness-expanded CI (pp) | Judge |",
        "|---|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['reader']} | {r['full_grid_difference'] * 100:.2f} | [{r['ci_low'] * 100:.2f}, {r['ci_high'] * 100:.2f}] | "
            f"[{r['sensitivity_ci_low'] * 100:.2f}, {r['sensitivity_ci_high'] * 100:.2f}] | {r['judge']} |"
        )
    lines += [
        "",
        "10,000 bootstrap resamples (seed 2026080901); 100,000 sign flips (seed 2026080902), "
        "plus-one p correction. Input reduction is 1 − summed TOMC provider input / summed hybrid-RAG provider input; "
        "it is not the mean of per-sample compression ratios.",
        "",
        "These results belong to the frozen BEAM-specific TOMC and BGE hybrid-RAG adapters, not the demo's "
        "normalized parser or lexical BM25 baseline. See [boundaries](../docs/claims_and_limitations.md).",
        "",
    ]
    (ROOT / "benchmarks/HISTORICAL_BEAM.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )
    (ROOT / "benchmarks/aggregate_results/recomputed.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "svg.hashsalt": "tomc-beam-v1"}
    )
    fig, ax = plt.subplots(figsize=(9, 3.7), facecolor="#f5f4ed")
    ax.set_facecolor("#f5f4ed")
    for i, r in enumerate(results):
        x = r["full_grid_difference"] * 100
        color = "#236148" if r["p_value"] < 0.05 else "#8a7960"
        ax.plot(
            [r["sensitivity_ci_low"] * 100, r["sensitivity_ci_high"] * 100],
            [i, i],
            color=color,
            alpha=0.35,
            lw=7,
        )
        ax.errorbar(
            x,
            i,
            xerr=[[x - r["ci_low"] * 100], [r["ci_high"] * 100 - x]],
            fmt="o",
            color=color,
            capsize=4,
        )
    ax.axvline(0, color="#879188", linestyle="--", lw=1)
    ax.set_yticks(range(4), [r["reader"] for r in results])
    ax.invert_yaxis()
    ax.set_xlabel("TOMC − hybrid-RAG · full-grid score difference (percentage points)")
    ax.set_title("BEAM / Four reader configurations", loc="left", weight="bold", pad=18)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", alpha=0.15)
    fig.text(
        0.03,
        0.015,
        "Thin: cluster bootstrap 95% CI  ·  Wide: missingness-expanded interval  ·  Frozen evidence, 2026-09-04",
        fontsize=8,
    )
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(ROOT / "assets/beam_readers.svg", metadata={"Date": None})
    fig.savefig(
        ROOT / "assets/beam_readers.png",
        dpi=180,
        metadata={"Software": "TOMC results reconstruction"},
    )
    plt.close(fig)


if __name__ == "__main__":
    render(rebuild())
