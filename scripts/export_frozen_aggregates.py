"""Author-side allowlist export. Never copies source text, labels, IDs or API payloads.

Readers of the staging repository use the bundled aggregates; this optional exporter
requires the author's local frozen evidence root and performs read-only extraction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, OrderedDict
from pathlib import Path
from statistics import mean

RUNS = [
    ("pro", "DeepSeek-V4-Pro", "beam_fresh_v4pro_headline_v1", "deepseek_v4_pro_0813", None),
    (
        "uob",
        "UOB GPT-5.1",
        "beam_fresh_uob_reader_replication_v1",
        "uob_gpt51_20260813",
        "deepseek_v4pro_judge_v1",
    ),
    (
        "rednote",
        "Rednote dots3-note-prev",
        "beam_fresh_rednote_reader_replication_v1",
        "rednote_dots3_note_prev_20260902",
        "deepseek_v4pro_judge_v3",
    ),
    (
        "flash",
        "DeepSeek V4 Flash",
        "beam_fresh_deepseek_flash_reader_replication_v1",
        "deepseek_v4_flash_20260902",
        "deepseek_v4pro_judge_v3",
    ),
]


def read_rows(path: Path) -> list[dict]:
    """Load private rows only inside the exporter process; never print contents."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def export(root: Path, output: Path) -> None:
    """Export numeric per-conversation sufficient statistics and allowlisted summary fields."""
    summaries, clusters, provenance = [], [], []
    repro = root / "experiments/repro"
    for reader_id, reader_name, folder, sub, judge in RUNS:
        run = repro / "runs" / folder / sub
        analysis_path = run / (
            "headline_analysis.machine.json"
            if judge is None
            else "replication_analysis.machine.json"
        )
        plan_path = run / ("uob_judge_plan.json" if judge is None else f"{judge}/plan.json")
        analysis = json.loads(analysis_path.read_text())
        plan = json.loads(plan_path.read_text())
        job_path = repro / plan["jobs_path"]
        result_path = run / (
            "uob_judge_state/judge_results.method_blind.jsonl"
            if judge is None
            else f"{judge}/state/judge_results.method_blind.jsonl"
        )
        jobs = [j for j in read_rows(job_path) if j["kind"] == "primary_grouped"]
        results = {str(r["job_key"]): r for r in read_rows(result_path)}
        groups: dict[str, dict] = OrderedDict()
        missing_counts: Counter[str] = Counter()
        for job in jobs:
            result = results[str(job["job_key"])]
            if str(result.get("outcome_status", "")).startswith("missing_"):
                missing_counts[str(job["cluster_id"])] += 1
                continue
            # Match the frozen first-observed-cluster order, which affects seeded resampling.
            group = groups.setdefault(
                str(job["cluster_id"]), {"tier": str(job["tier"]), "scores": [], "missing": 0}
            )
            scores = {
                method: mean(float(v) for v in result["scores_by_label"][label])
                for label, method in job["candidate_method_by_label"].items()
            }
            group["scores"].append(
                (scores["beam_tomc_stabilized_v2"], scores["beam_hybrid_rag_v2"])
            )
        assert len(groups) == 60 and len(jobs) == 600
        for cluster_id, group in groups.items():
            group["missing"] = missing_counts[cluster_id]
        for index, group in enumerate(groups.values()):
            observed = group["scores"]
            assert len(observed) + group["missing"] == 10
            clusters.append(
                {
                    "reader_id": reader_id,
                    "cluster_ordinal": index,
                    "tier": group["tier"],
                    "observed": len(observed),
                    "missing": group["missing"],
                    "tomc_score_sum": sum(x[0] for x in observed),
                    "rag_score_sum": sum(x[1] for x in observed),
                    "paired_difference_sum": sum(x[0] - x[1] for x in observed),
                }
            )
        p, e = analysis["primary"], analysis["reader_efficiency"]
        s = {
            "reader_id": reader_id,
            "reader": reader_name,
            "judge": analysis["judge_model"],
            "tomc": p["complete_case_tomc_mean"],
            "hybrid_rag": p["complete_case_hybrid_rag_mean"],
            "difference": p["complete_case_difference"],
            "full_grid_difference": p["zero_midpoint_full_grid_difference"],
            "ci_low": p["zero_midpoint_cluster_stratified_bootstrap_95ci"][0],
            "ci_high": p["zero_midpoint_cluster_stratified_bootstrap_95ci"][1],
            "sensitivity_ci_low": p["missingness_sensitivity_expanded_95ci"][0],
            "sensitivity_ci_high": p["missingness_sensitivity_expanded_95ci"][1],
            "p_value": p["paired_cluster_sign_flip_p_value"],
            "conversations": 60,
            "questions": 600,
            "observed_questions": p["observed_questions"],
            "missing_questions": p["missing_questions"],
            "tomc_input_tokens": e["beam_tomc_stabilized_v2"]["provider_input_tokens"],
            "rag_input_tokens": e["beam_hybrid_rag_v2"]["provider_input_tokens"],
            "input_reduction": analysis["tomc_input_token_reduction_vs_hybrid_rag_fraction"],
        }
        summaries.append(s)
        for path in (analysis_path, plan_path, job_path, result_path):
            provenance.append(
                {
                    "reader_id": reader_id,
                    "source_role": "aggregate"
                    if path == analysis_path
                    else "private_input_not_distributed",
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [("beam_readers.csv", summaries), ("beam_clusters.csv", clusters)]:
        with (output / name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "source_hashes.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        f"Exported {len(summaries)} reader summaries and {len(clusters)} numeric cluster aggregates."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks/aggregate_results",
    )
    args = parser.parse_args()
    export(args.evidence_root, args.output)
