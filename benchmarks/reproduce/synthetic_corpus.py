"""Regenerate the nine synthetic Codex/Claude test histories and check them against the record.

Usage:
    python benchmarks/reproduce/synthetic_corpus.py

Offline, writes nothing. It rebuilds the corpus with
scripts/benchmarks/codex_retention_cases.py (in memory, encoded exactly as that script writes
it) and compares:

- the SHA-256 of the whole corpus file with ``provenance.corpus_sha256``,
- each history's SHA-256, character count and expected answers,
- each history's lexical token estimate (TOMC's ``regex`` counter),

against docs/validation_data/windows_codex_retention_20261005.json. It does not repeat the
model runs; their answers and usage are checked by
``scripts/benchmarks/codex_retention_report.py --verify-published``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/benchmarks"))
sys.path.insert(0, str(ROOT / "src"))

import codex_retention_cases  # noqa: E402

from tomc.tokenization import get_counter  # noqa: E402

RECORD = ROOT / "docs/validation_data/windows_codex_retention_20261005.json"


def main() -> int:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    data = codex_retention_cases.generate_cases()
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    corpus = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    problems = []
    if corpus != record["provenance"]["corpus_sha256"]:
        problems.append(
            f"corpus sha256 {corpus} != recorded {record['provenance']['corpus_sha256']}"
        )
    counter = get_counter("regex")
    if set(data["cases"]) != set(record["cases"]):
        problems.append("case IDs differ")
    for case_id, case in data["cases"].items():
        saved = record["cases"].get(case_id, {})
        history = case["history"]
        checks = {
            "history_sha256": hashlib.sha256(history.encode("utf-8")).hexdigest(),
            "history_characters": len(history),
            "history_lexical_tokens": counter.count(history),
            "expected": case["expected"],
        }
        for key, value in checks.items():
            if saved.get(key) != value:
                problems.append(f"{case_id}: {key} {value!r} != recorded {saved.get(key)!r}")
    if problems:
        print("Synthetic corpus differs from the record:", file=sys.stderr)
        for line in problems:
            print("  " + line, file=sys.stderr)
        return 1
    print(
        f"Regenerated {len(data['cases'])} synthetic histories; corpus sha256 {corpus[:12]}… "
        "and every history hash, length, token estimate and expected answer match the record."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
