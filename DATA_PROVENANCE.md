# Data provenance

## Current manuscript snapshot — 2026-09-28

`benchmarks/current_paper/manifest.json` pins writing-repository commit `7399657` and records source/export SHA-256 hashes. The snapshot includes BEAM baseline/ability/token aggregates, RULER-derived conditions, the separate repaired NIAH ablation, construction resource measurements, and approved manuscript method/BEAM figures. `scripts/sync_paper.py` performs the author-side export without APIs and checks main BEAM scores, protocols and pair counts against the manuscript's main-table source.

The current report is `benchmarks/RESULTS.md`, also rendered as `docs/paper_results.md`. The same verified tables power the interactive evidence tab. Only aggregates and figures are transferred; original question identifiers, dataset text, reader/judge answers, credentials, endpoints, manuscript PDF and private Git history are excluded. Relative artifact paths document lineage, not access to the source repository. See [snapshot schema](benchmarks/current_paper/README.md) and [scope](docs/claims_and_limitations.md).

The copied manuscript figures can contain method/provider marks identifying evaluated systems. Those marks retain their respective ownership; the project does not claim endorsement or relicense them.

## Historical freeze — 2026-09-04

The table below describes the preserved older four-reader Hybrid-RAG batch, whose report is now `benchmarks/HISTORICAL_BEAM.md`. These rows are not combined with the current main comparison.

| Artifact | Source | Transformation | Public content |
|---|---|---|---|
| `demo/examples/*.json`, `src/tomc/data/*.json` | Original scenarios in `scripts/generate_examples.py` | Deterministic generation | Synthetic text only; PolyForm Noncommercial 1.0.0 |
| `beam_readers.csv` | Four frozen BEAM primary machine analyses | Allowlisted scores, CIs, p values, provider totals and configuration names | Reader-level numerical aggregates |
| `beam_clusters.csv` | The same frozen judge jobs/results | Average criterion scores; sum within 60 conversations per reader; remove original IDs and all text | 240 numeric cluster aggregates and length tiers |
| `source_hashes.json` | Frozen analyses and inputs | File SHA-256 only | Hashes and source roles, no payload or paths |
| `boundaries.csv` | Frozen `paper/EXPERIMENT_MATRIX_20260904.csv` | Select approved mechanism/boundary rows; remove private evidence-location column | Summary statements only |
| `matrix_source.json` | Frozen matrix | SHA-256 and freeze date | Provenance metadata |
| `recomputed.json`, result card and BEAM plot | Bundled numeric aggregate CSVs | Offline statistical reconstruction | Derived statistics |
| Demo screenshots | Local Gradio app with original synthetic sample | Browser capture | No personal or benchmark input |

Freeze: 2026-09-04. The headline run used DeepSeek-V4-Pro with a UOB GPT-5.1 judge. UOB, Rednote and Flash reader replications used a DeepSeek-V4-Pro judge. Pro/UOB/Rednote/Flash have 598/591/594/595 observed paired questions out of 600 each; conversation clusters and full-grid denominators are preserved. Original cluster identifiers and cross-reader matching keys are absent.

The ordinal within each reader records first-observed-cluster order only, needed for exact seeded bootstrap reconstruction. No question, answer, per-criterion text, reference label, API header, private endpoint or original record key is exported. Per-conversation sums are aggregated over up to ten observed question pairs. We do not claim formal differential privacy or that arbitrary statistics are automatically safe under every auxiliary-data threat model.

Author-owned method source provenance lives in `docs/SOURCE_PROVENANCE.json`. No third-party datasets or weights are shipped. User-supplied Level 3 data remains the user's responsibility to obtain under its own terms. The private HF evidence dataset and full paper repository are not mirrored; only the selected current aggregates and figures described above are exported.
