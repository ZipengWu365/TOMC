# Benchmarks and evidence

[Current paper results](RESULTS.md) · [Snapshot and provenance](current_paper/README.md) · [Historical four-reader batch](HISTORICAL_BEAM.md) · [Interpretation](../docs/claims_and_limitations.md)

The current manuscript compares TOMC with six BEAM baseline configurations across three readers and three history lengths, then examines RULER-derived mechanisms/component ablations and construction resources. `current_paper/` contains aggregate evidence pinned to the writing-repository commit. It does not contain questions, answers or private endpoints. The synthetic demo parser did not generate these benchmark scores.

`make reproduce-results` performs two separate offline checks:

1. Verify current snapshot hashes and aggregate arithmetic, then rebuild the current result report, including separate repaired NIAH results.
2. Reconstruct the historical four-reader Hybrid-RAG statistics, uncertainty intervals and p values from 240 numeric conversation aggregates. This writes `HISTORICAL_BEAM.md`, leaving the current report intact.

The demo BM25 strategy differs from current BEAM-RAG and historical Hybrid-RAG. No official baseline weights or paid APIs are loaded by either evidence check. The optional LLMLingua adapter calls the installed official library only when explicitly configured; it never substitutes a fallback's output under an unavailable baseline name.

`scripts/replicate.py` accepts user-supplied JSONL and defaults to a cost-planning dry run. Its optional exact-match score is not the BEAM judge rubric. See [reproducibility](../docs/reproducibility.md) for what each level verifies.
