"""Public artifacts must retain source hashes and support claims numerically."""

import csv
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

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


def test_security_scanner_exemptions_are_exact():
    spec = importlib.util.spec_from_file_location("scan", ROOT / "scripts/security_scan.py")
    scan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scan)
    # Only the exact known-fake fixture is exempt; a real-looking token beside it is still found.
    assert not scan.inspect_blob(b'FAKE = "Bearer fixture-only-never-a-real-token"', "fixture")
    assert scan.inspect_blob(
        b"Bearer fixture-only-never-a-real-token " + b"Bearer " + b"c" * 30, "mixed"
    )
    # The default/current-file check never applies historical size exceptions.
    assert scan.inspect_blob(b"x" * 5_000_001, "large") == ["large: file larger than 5 MB"]


def _historical_scan_fixture(
    tmp_path,
    monkeypatch,
    data,
    *,
    listed=True,
    keep_current=False,
    baseline_bytes=None,
    legacy_path="legacy.bin",
):
    """Use real Git objects so removed history is tested independently of HEAD."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Scanner Fixture")
    git("config", "user.email", "scanner-fixture@example.invalid")
    legacy = root / legacy_path
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(data)
    git("add", legacy_path)
    git("commit", "-qm", "Historical fixture")
    oid = git("rev-parse", "HEAD:" + legacy_path)
    if not keep_current:
        legacy.unlink()
    record = {
        "oid": oid,
        "bytes": len(data) if baseline_bytes is None else baseline_bytes,
        "path": legacy_path,
        "reason": "Constructed historical regression fixture",
    }
    baseline = root / "scripts/security_history_size_baseline.json"
    baseline.parent.mkdir()
    baseline.write_text(
        json.dumps({"schema_version": 1, "historical_large_blobs": [record] if listed else []}),
        encoding="utf-8",
    )
    git("add", "-A")
    git("commit", "-qm", "Record exact fixture baseline")
    spec = importlib.util.spec_from_file_location("scan_fixture", ROOT / "scripts/security_scan.py")
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    monkeypatch.setattr(scanner, "ROOT", root)
    return scanner, oid


def test_security_scanner_accepts_only_audited_removed_large_history(tmp_path, monkeypatch, capsys):
    scanner, oid = _historical_scan_fixture(tmp_path, monkeypatch, b"x" * 5_000_001)
    result = scanner.scan()
    assert result["status"] == "pass"
    assert result["findings"] == []
    assert [row["oid"] for row in result["history_size_baseline_used"]] == [oid]
    assert json.loads(capsys.readouterr().out)["status"] == "pass"


def test_security_scanner_still_rejects_current_large_baseline_content(
    tmp_path, monkeypatch, capsys
):
    scanner, _ = _historical_scan_fixture(
        tmp_path, monkeypatch, b"x" * 5_000_001, keep_current=True
    )
    with pytest.raises(SystemExit, match="1"):
        scanner.scan()
    result = json.loads(capsys.readouterr().out)
    assert "legacy.bin: file larger than 5 MB" in result["findings"]


def test_security_scanner_still_rejects_credentials_in_audited_history(
    tmp_path, monkeypatch, capsys
):
    credential = b"gh" + b"p_" + b"A" * 36
    scanner, oid = _historical_scan_fixture(
        tmp_path, monkeypatch, b"x" * 5_000_001 + b"\n" + credential
    )
    with pytest.raises(SystemExit, match="1"):
        scanner.scan()
    output = capsys.readouterr().out
    assert credential.decode() not in output
    result = json.loads(output)
    assert f"history:{oid[:12]}: credential_token" in result["findings"]
    assert [row["oid"] for row in result["history_size_baseline_used"]] == [oid]


def test_security_scanner_still_rejects_excluded_names_in_audited_history(
    tmp_path, monkeypatch, capsys
):
    scanner, oid = _historical_scan_fixture(
        tmp_path, monkeypatch, b"x" * 5_000_001, legacy_path="FormalMATH/legacy.bin"
    )
    with pytest.raises(SystemExit, match="1"):
        scanner.scan()
    result = json.loads(capsys.readouterr().out)
    assert f"history:{oid[:12]}: excluded artifact" in result["findings"]


@pytest.mark.parametrize("listed,baseline_bytes", [(False, None), (True, 5_000_002)])
def test_security_scanner_rejects_unlisted_or_size_mismatched_large_history(
    tmp_path, monkeypatch, capsys, listed, baseline_bytes
):
    scanner, oid = _historical_scan_fixture(
        tmp_path,
        monkeypatch,
        b"x" * 5_000_001,
        listed=listed,
        baseline_bytes=baseline_bytes,
    )
    with pytest.raises(SystemExit, match="1"):
        scanner.scan()
    result = json.loads(capsys.readouterr().out)
    assert f"history:{oid[:12]}: file larger than 5 MB" in result["findings"]
    assert result["history_size_baseline_used"] == []


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
