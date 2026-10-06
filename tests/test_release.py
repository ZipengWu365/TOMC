"""Public artifacts must retain source hashes and support claims numerically."""

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_preserved_research_sources():
    for record in json.loads((ROOT / "docs/SOURCE_PROVENANCE.json").read_text(encoding="utf-8")):
        assert hashlib.sha256((ROOT / record["file"]).read_bytes()).hexdigest() == record["sha256"]


def test_historical_claims_match_frozen_full_precision_aggregates():
    rows = list(
        csv.DictReader(
            (ROOT / "benchmarks/aggregate_results/beam_readers.csv").open(encoding="utf-8")
        )
    )
    assert len(rows) == 4
    assert all(float(r["difference"]) > 0 for r in rows)
    assert sum(float(r["p_value"]) < 0.05 for r in rows) == 3
    for r in rows:
        assert abs(float(r["tomc"]) - float(r["hybrid_rag"]) - float(r["difference"])) < 1e-12
        reduction = 1 - int(r["tomc_input_tokens"]) / int(r["rag_input_tokens"])
        assert abs(reduction - float(r["input_reduction"])) < 1e-12
        assert int(r["missing_questions"]) + int(r["observed_questions"]) == 600
        for readme in [ROOT / "benchmarks/HISTORICAL_BEAM.md"]:
            text = readme.read_text(encoding="utf-8")
            assert f"{float(r['tomc']):.4f}" in text
            assert f"{float(r['hybrid_rag']):.4f}" in text
            assert f"{float(r['difference']) * 100:.2f}" in text
            assert f"{reduction:.2%}" in text


def test_cluster_export_schema_contains_no_original_ids_or_payloads():
    rows = list(
        csv.DictReader(
            (ROOT / "benchmarks/aggregate_results/beam_clusters.csv").open(encoding="utf-8")
        )
    )
    assert len(rows) == 240
    assert set(rows[0]) == {
        "reader_id",
        "cluster_ordinal",
        "tier",
        "observed",
        "missing",
        "tomc_score_sum",
        "rag_score_sum",
        "paired_difference_sum",
    }
    assert {r["reader_id"] for r in rows} == {"pro", "uob", "rednote", "flash"}


def test_security_scanner_detects_constructed_credentials_but_not_blank_template():
    spec = importlib.util.spec_from_file_location("scan", ROOT / "scripts/security_scan.py")
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)
    assert scan.inspect_blob(b"gh" + b"p_" + b"A" * 36, "test")
    assert scan.inspect_blob(b"Bearer " + b"b" * 30, "test")
    assert scan.inspect_blob(b"TOMC_READER_API_KEY=" + b"a" * 30, "test")
    assert not scan.inspect_blob((ROOT / ".env.example").read_bytes(), "template")


def test_current_paper_snapshot_and_generated_reports():
    from benchmarks.reproduce.current import render_report, verify

    manifest = verify()
    assert manifest["api_calls"] == 0
    report = render_report()
    assert (ROOT / "benchmarks/RESULTS.md").read_text(encoding="utf-8") == report
    assert (ROOT / "docs/paper_results.md").read_text(encoding="utf-8") == report


def test_ruler_full_state_route_does_not_use_candidate_removal_input():
    from benchmarks.reproduce.current import csv_rows, ruler_text

    # Both VT conditions score 100, so quality alone cannot expose a swapped row.
    rows = [r for r in csv_rows("ruler_conditions.csv") if r["task"] == "VT"]
    full = {r["reader"]: r for r in rows if r["method"] == "tomc"}
    removal = {r["reader"]: r for r in rows if r["method"] == "tomc_state_only"}
    assert len(full) == len(removal) == 3
    for reader in full:
        assert float(full[reader]["score"]) == float(removal[reader]["score"]) == 100
        assert float(full[reader]["input_tokens"]) > float(removal[reader]["input_tokens"])

    # Independent reference: manuscript Table 2 / Figure 3 use full state input.
    rendered = next(line for line in ruler_text().splitlines() if line.startswith("| VT ·"))
    assert rendered == "| VT · state-route diagnostic | 46.80 | 100.00 | 89.2% |"


def test_release_manifest_has_platform_independent_path_order(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "release_manifest", ROOT / "scripts/release_manifest.py"
    )
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    names = ["docs/index.md", "README.md", "launch/brief.html", "LICENSE"]
    paths = []
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        paths.append(path)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "candidates", lambda: paths)

    entries = release.manifest()["files"]

    assert [entry["path"] for entry in entries] == sorted(names)
    assert all(
        entry["sha256"] == hashlib.sha256(entry["path"].encode()).hexdigest() for entry in entries
    )
