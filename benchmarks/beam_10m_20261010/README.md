# BEAM 10M follow-up (2026-10-10)

This folder adds the 10M-token tier to the BEAM comparison on the [evidence page](../../docs/evidence.md#beam). It is a follow-up added after the paper snapshot (100K–1M, manuscript commit `7399657`, 2026-09-28) and uses a different scoring protocol. It holds per-question scores only: question and method IDs, answer hashes, reader-input token counts and scores. It contains no conversations, answers, request text or credentials.

- **Questions:** 200 official BEAM questions from 10 independent 10M-token sessions; each session covers the ten memory abilities with two questions each.
- **Pairs:** 3 readers × 6 baselines × 200 questions = 3,600 planned pairs; 3,596 are valid. The four invalid judgments (`missing_or_invalid_judge`) are excluded rather than scored as zero. All 18 reader × baseline cells passed the fixed reversed-order and single-answer calibration checks.
- **Scoring:** an anonymous, position-balanced pairwise rubric judged each baseline / TOMC pair. The 100K–1M rows keep their original scoring protocols, so the pooled Overall row combines protocols and dates. Treat it as a descriptive summary, not a single-judge estimate; the 10M rows are the directly comparable new result.
- **Baseline runs:** `source_run` separates the original 10M batch (`beam10m_paired_20261003/v1`, four baseline families) from the repaired LLMLingua-2 batch (`beam10m_ll2_repair_20261007/v1`), whose direct and hierarchical memories are non-empty. The repair reused identity-checked TOMC answers and re-judged anonymous pairs. BEAM-RAG keeps its 10M-adapted method ID in `actual_baseline_method`.
- **Not yet included:** as of 2026-10-10 the 10M compilation ablation was running in a separate batch; its results have not been published. The *TOMC w/o compilation* rows cover 100K–1M only.

The combined set covers 800 distinct questions in 70 sessions: the original 600 (one question per ability per session) and these 200 (two per ability per session). Overall is therefore weighted by valid questions, not by sessions. It is not a completed run of the full 2,000-question BEAM benchmark.

## Reproduce the table

```bash
python scripts/make_beam_table.py --check
```

The script reads this CSV and the per-tier aggregates in [`benchmarks/current_paper/beam_comparisons.csv`](../current_paper/beam_comparisons.csv). It recomputes every score pair, relative change, mean and input change, then checks that the booktabs LaTeX sources in [`assets/beam_table/`](../../assets/beam_table/), the table images rendered from them and the table blocks on the evidence pages are up to date. `python scripts/make_beam_table.py --render` rewrites them; rendering needs `pdflatex` and Poppler's `pdftocairo`/`pdftoppm`. It makes no network or model calls.

Per reader and baseline, Overall pools the original valid pairs with the 10M pairs before taking means. Δ is `100 × (TOMC / baseline − 1)`, and the mean column averages the three readers before rounding. Input change uses the same reader-wise ratio of mean API reader-input tokens, then an equal average across readers.
