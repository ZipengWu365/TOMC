# Benchmarks and evidence

[Current paper results](RESULTS.md) · [Snapshot and provenance](current_paper/README.md) · [Historical four-reader batch](HISTORICAL_BEAM.md) · [Interpretation](../docs/claims_and_limitations.md)

The current manuscript compares TOMC with six BEAM baseline configurations across three readers and three history lengths, then examines RULER-derived mechanisms/component ablations and construction resources. `current_paper/` contains aggregate evidence pinned to the writing-repository commit. It does not contain questions, answers or private endpoints. The synthetic demo parser did not generate these benchmark scores.

`make reproduce` runs every offline check in check mode and fails on any mismatch, without rewriting tracked files (under a minute, no model or network calls):

1. Current paper snapshot: hashes and aggregate arithmetic, compared with `RESULTS.md` and `docs/paper_results.md`.
2. Historical four-reader Hybrid-RAG batch: statistics, intervals and p values from 240 numeric conversation aggregates, compared with `HISTORICAL_BEAM.md` and `aggregate_results/recomputed.json`.
3. BEAM table with the 10M follow-up (`scripts/make_beam_table.py --check`).
4. Session-level bootstrap intervals for the 18 cells at 10M (`reproduce/beam10m_bootstrap.py`, saved in `beam_10m_20261010/bootstrap_ci.json`).
5. The nine synthetic Codex/Claude test histories, regenerated and compared by hash with the published record, plus an offline check of the saved Codex report.
6. The v0.3 stale-value benchmark (`stale/run.py --check`) and the adaptive-selection suite (`adaptive/run.py --check`).
7. The two offline examples quoted in the docs.

`make reproduce-results` rewrites the current report, `HISTORICAL_BEAM.md`, `recomputed.json` and the historical plot instead of comparing them.

The demo BM25 strategy differs from current BEAM-RAG and historical Hybrid-RAG. No official baseline weights or paid APIs are loaded by either evidence check. The optional LLMLingua adapter calls the installed official library only when explicitly configured; it never substitutes a fallback's output under an unavailable baseline name.

`scripts/replicate.py` accepts user-supplied JSONL and defaults to a cost-planning dry run. Its optional exact-match score is not the BEAM judge rubric. See [reproducibility](../docs/reproducibility.md) for what each level verifies. Independent reruns, including failed ones, are listed in [REPLICATIONS.md](../REPLICATIONS.md).
