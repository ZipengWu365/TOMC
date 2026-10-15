"""Export allowlisted aggregate evidence from an existing manuscript checkout. No APIs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks/current_paper"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-repo", type=Path, required=True)
    args = parser.parse_args()
    paper = args.paper_repo.resolve()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=paper, text=True).strip()
    OUT.mkdir(parents=True, exist_ok=True)
    sources, exports = {}, {}

    def source(name):
        path = paper / name
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", name],
            cwd=paper,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        # Do not attach a commit ID to uncommitted evidence.
        subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", name], cwd=paper, check=True)
        sources[name] = sha(path)
        return path

    def export_csv(name, origin, fields=None, predicate=lambda row: True):
        values = [r for r in read_csv(source(origin)) if predicate(r)]
        fields = fields or [k for k in values[0] if k not in {"source", "source_files"}]
        with (OUT / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows({k: r[k] for k in fields} for r in values)
        exports[name] = {"source": origin, "rows": len(values), "sha256": sha(OUT / name)}
        return values

    token = "experiments/beam_input_comparison_20260925/"
    rows = export_csv(
        "beam_comparisons.csv",
        token + "all_beam_reader_summary.csv",
        predicate=lambda r: r["cohort"] in {"current_main", "ablation_P0_Pro"},
    )
    export_csv(
        "beam_abilities.csv",
        token + "all_beam_ability_summary.csv",
        predicate=lambda r: r["cohort"] in {"current_main", "ablation_P0_Pro"},
    )
    export_csv("beam_three_reader.csv", token + "main_six_three_reader_summary.csv")
    quality = read_csv(
        source("experiments/light_final_20260919/data/beam_all_abilities_lengths.csv")
    )
    index = {(r["reader"], r["method"], r["tier"]): r for r in quality if r["ability"] == "all"}
    for row in rows:
        if row["cohort"] != "current_main":
            continue
        tier = "all" if row["tier"] == "Overall" else row["tier"]
        ref = index[row["reader"], row["method"], tier]
        assert int(ref["n"]) == int(row["valid_pairs"])
        assert ref["protocol"] == row["protocol"]
        for before, after in [
            ("tomc", "tomc_mean_score_0_100"),
            ("baseline", "baseline_mean_score_0_100"),
        ]:
            assert abs(float(ref[before]) - float(row[after])) < 1e-9
    export_csv("beam_common_abilities.csv", "figures/results_composite_ability_source.csv")
    composite = "figures/results_composite_sources.json"
    original = json.loads(source(composite).read_text())
    long_history = {
        k: original[k]
        for k in ["summary", "summary_aggregation", "radar_aggregation", "radar_protocol"]
    }
    (OUT / "beam_long_history.json").write_text(json.dumps(long_history, indent=2) + "\n")
    exports["beam_long_history.json"] = {
        "source": composite,
        "sha256": sha(OUT / "beam_long_history.json"),
    }
    export_csv(
        "ruler_conditions.csv",
        "experiments/evidence_update_20260918/data/ruler_uniform_metrics.csv",
    )
    export_csv(
        "niah_repaired.csv",
        "experiments/niah_packingfix_ablation_20260925/paired_comparisons.csv",
        fields=[
            "batch_id",
            "reader",
            "full_condition",
            "removal_condition",
            "common_valid_N",
            "full_f1",
            "removal_f1",
            "full_minus_removal_f1_pp",
            "full_em",
            "removal_em",
            "paired_input_usage_N",
            "mean_input_full",
            "mean_input_removal",
            "removal_token_savings_percent",
        ],
    )
    source("tables/beam_main_counts.tex")
    resource = "tables/construction_compact_sources.json"
    shutil.copyfile(source(resource), OUT / "construction.json")
    exports["construction.json"] = {"source": resource, "sha256": sha(OUT / "construction.json")}
    for section in ["00_abstract", "04_method", "06_experiments", "07_results", "10_conclusion"]:
        source(f"sections/{section}.tex")
    for name in [
        "appendices/15_construction_resources.tex",
        "appendices/16_beam_ablation.tex",
        "experiments/niah_packingfix_ablation_20260925/README.md",
    ]:
        source(name)
    for origin, name in [("tomc_overview", "paper_method"), ("results_composite", "paper_beam")]:
        # The supplied overview SVG embeds >9 MB of image data; retain its exact PNG.
        for ext in ["png"] if name == "paper_method" else ["svg", "png"]:
            relative = f"assets/{name}.{ext}"
            src = f"figures/{origin}.{ext}"
            shutil.copyfile(source(src), ROOT / relative)
            exports["../../" + relative] = {"source": src, "sha256": sha(ROOT / relative)}
    manifest = {
        "schema": "tomc-paper-aggregate-snapshot-v1",
        "synced_on": date.today().isoformat(),
        "paper_repository": "private manuscript repository",
        "paper_commit": commit,
        "sources": sources,
        "exports": exports,
        "api_calls": 0,
        "scope": "Aggregate numerical evidence and author-approved figures only; no manuscript PDF, question/answer text, original question IDs, private endpoints or credentials.",
        "verification": "Current BEAM summary scores, protocols and pair counts checked against the manuscript's frozen main-table source before export.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "docs/PAPER_SCOPE_SOURCES.json").write_text(
        json.dumps(
            {
                "reviewed_on": manifest["synced_on"],
                "paper_repository": manifest["paper_repository"],
                "paper_commit": commit,
                "source_sha256": sources,
                "implementation_note": "Demo kernels retain their separate original provenance; this sync updates evidence and presentation, not benchmark algorithms.",
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Exported {len(exports)} aggregate/figure files from manuscript {commit[:7]}.")


if __name__ == "__main__":
    main()
