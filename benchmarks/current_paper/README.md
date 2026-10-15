# Current manuscript evidence snapshot

Exported on 2026-09-28 from writing commit `7399657`. `manifest.json` records the full commit, relative source paths, source hashes and exported-file hashes. Only aggregate evidence and the approved method/BEAM figures are copied; no benchmark text, original question IDs, reader answers, credentials or private endpoints are included.

| File | Content |
|---|---|
| `beam_comparisons.csv` | 72 main comparison rows (6 baselines × 3 readers × 4 length summaries), plus 12 separately labeled Pro-judged compilation-ablation rows |
| `beam_abilities.csv` | Baseline-specific ability aggregates and separate compilation-ablation aggregates |
| `beam_three_reader.csv` | 24 equal-reader main summaries |
| `beam_common_abilities.csv` | Common-valid TOMC/RAG/LIGHT ability scores for 500K, 1M and their equal mean |
| `beam_long_history.json` | Within-reader pooled 500K/1M summaries and aggregation definitions |
| `ruler_conditions.csv` | Archived RULER-derived condition aggregates, including input tokens and savings |
| `niah_repaired.csv` | Separate repaired NIAH ablation, three readers, 100 paired examples each |
| `construction.json` | Construction time and GPU/process RAM measurements with source notes |

Reader keys: `gpt51` = GPT-5.1; `dots3` = Rednote preview; `flash` = DeepSeek 4.1 Flash in these current tables. Do not confuse these with the older four-reader archive or infer a model version from a key shared by different batches.

Scores in `beam_comparisons.csv` are on 0–100; `beam_long_history.json` stores its reader score means on 0–1 and relative changes in percent. `quality_delta_pp` is a percentage-point difference. Negative `input_change_pct` means TOMC uses fewer reader input tokens; positive `input_saving_pct` means savings. `protocol` and `valid_pairs` identify each paired comparison's evaluation scope. CSV method IDs preserve archive names; the result report maps them to readable labels.

The direct LLMLingua-2 1M run has 200 empty memories. The archived NIAH table contains packing failures; use the repaired batch only for its separately controlled ablation. Source hashes document lineage, not proof of correctness by themselves. [Results and interpretation](../RESULTS.md).

Run `python benchmarks/reproduce/current.py` from the repo root to verify hashes and aggregate arithmetic, then regenerate `benchmarks/RESULTS.md` and `docs/paper_results.md`. The check does not recompute current statistical tests from raw answers. To update from an author-accessible manuscript checkout, run `python scripts/sync_paper.py --paper-repo /path/to/writing-checkout`, review the snapshot changes, then regenerate and validate. No API calls are made.
