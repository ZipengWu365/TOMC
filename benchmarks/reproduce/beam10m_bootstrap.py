"""Session-level bootstrap intervals for the BEAM 10M follow-up (2026-10-10).

Usage:
    python benchmarks/reproduce/beam10m_bootstrap.py           # print the table
    python benchmarks/reproduce/beam10m_bootstrap.py --check   # also compare with the saved JSON
    python benchmarks/reproduce/beam10m_bootstrap.py --write   # rewrite the saved JSON

Input: benchmarks/beam_10m_20261010/paired_scores_10m.csv (valid pairs only).
For each reader × baseline cell:

- difference = mean over valid pairs of (TOMC score − baseline score) × 100, which equals the
  TOMC mean minus the baseline mean on the table's 0–100 scale;
- the 200 questions come from 10 sessions, and questions from one session are not independent,
  so the interval resamples whole sessions: draw 10 sessions with replacement, pool their valid
  pairs, recompute the difference; 10,000 resamples; the random generator is re-seeded with
  2026102901 for every cell; 95% percentile interval (sorted estimates at positions
  round(0.025 × 9,999) and round(0.975 × 9,999)).

With only 10 sessions this is a rough interval. It makes no API calls and uses only the
standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "benchmarks/beam_10m_20261010/paired_scores_10m.csv"
SAVED = ROOT / "benchmarks/beam_10m_20261010/bootstrap_ci.json"
SEED = 2026102901
RESAMPLES = 10_000
READERS = [("gpt51", "GPT-5.1"), ("dots3", "Rednote preview"), ("flash", "DeepSeek 4.1 Flash")]
METHODS = [
    ("llmlingua2_full_history_b8192_v1", "LLMLingua-2-D"),
    ("longllmlingua_recovery_b8192", "LongLLMLingua"),
    ("hybrid_brief_pro_auto_b8192", "BRIEF-Pro"),
    ("llmlingua2_hier64k_full_history_b8192_v1", "LLMLingua-2-H"),
    ("rag", "BEAM-RAG"),
    ("light", "LIGHT"),
]


def load():
    cells = defaultdict(lambda: defaultdict(list))
    with DATA.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["status"] != "valid":
                continue
            diff = float(row["tomc_score"]) - float(row["baseline_score"])
            cells[(row["reader"], row["method"])][row["cluster_id"]].append(diff)
    return cells


def interval(sessions: dict[str, list[float]]) -> tuple[float, float, float]:
    keys = sorted(sessions)
    pooled = [d for k in keys for d in sessions[k]]
    point = 100 * sum(pooled) / len(pooled)
    rng = random.Random(SEED)
    estimates = []
    for _ in range(RESAMPLES):
        total = count = 0
        for _ in keys:
            values = sessions[rng.choice(keys)]
            total += sum(values)
            count += len(values)
        estimates.append(100 * total / count)
    estimates.sort()
    return (
        point,
        estimates[round(0.025 * (RESAMPLES - 1))],
        estimates[round(0.975 * (RESAMPLES - 1))],
    )


def compute() -> dict:
    cells = load()
    rows = []
    for reader, reader_name in READERS:
        for method, method_name in METHODS:
            sessions = cells[(reader, method)]
            point, low, high = interval(sessions)
            rows.append(
                {
                    "reader": reader_name,
                    "baseline": method_name,
                    "sessions": len(sessions),
                    "valid_pairs": sum(len(v) for v in sessions.values()),
                    "difference": round(point, 4),
                    "ci_low": round(low, 4),
                    "ci_high": round(high, 4),
                    "excludes_zero": low > 0 or high < 0,
                }
            )
    return {
        "source": "benchmarks/beam_10m_20261010/paired_scores_10m.csv",
        "method": "session (cluster) bootstrap of the mean paired score difference, TOMC minus "
        "baseline, on the 0-100 scale; valid pairs only; 10 sessions resampled with replacement; "
        f"{RESAMPLES} resamples; seed {SEED} re-seeded per cell; 95% percentile interval",
        "cells": rows,
        "cells_excluding_zero": sum(r["excludes_zero"] for r in rows),
    }


def table(result: dict) -> str:
    lines = [
        "| Reader | Baseline | Valid pairs | TOMC − baseline (points) | 95% session-bootstrap interval |",
        "|---|---|---:|---:|---:|",
    ]
    for r in result["cells"]:
        mark = "" if r["excludes_zero"] else " (includes 0)"
        lines.append(
            f"| {r['reader']} | {r['baseline']} | {r['valid_pairs']} | {r['difference']:+.2f} | "
            f"[{r['ci_low']:+.2f}, {r['ci_high']:+.2f}]{mark} |"
        )
    lines.append("")
    lines.append(
        f"{result['cells_excluding_zero']} of {len(result['cells'])} intervals exclude zero."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare with the saved JSON")
    mode.add_argument("--write", action="store_true", help="rewrite the saved JSON")
    args = parser.parse_args()
    result = compute()
    print(table(result))
    if args.write:
        SAVED.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
        return 0
    if args.check:
        saved = json.loads(SAVED.read_text(encoding="utf-8"))
        if saved != json.loads(json.dumps(result)):
            print(f"Bootstrap result differs from {SAVED.name}", file=sys.stderr)
            return 1
        print(f"Matches {SAVED.relative_to(ROOT).as_posix()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
