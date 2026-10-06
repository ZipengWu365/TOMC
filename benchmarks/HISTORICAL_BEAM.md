# Historical four-reader BEAM comparison

Historical Hybrid-RAG batch; superseded as the main result story by [current paper results](RESULTS.md). Rebuilt offline from [reader aggregates](aggregate_results/beam_readers.csv) and [240 numeric conversation aggregates](aggregate_results/beam_clusters.csv). Freeze: 2026-09-04.

| Reader | TOMC | hybrid-RAG | Δ pp | p | Reader input reduction |
|---|---:|---:|---:|---:|---:|
| DeepSeek-V4-Pro | 0.5535 | 0.5047 | +4.88 | 0.0106 | 35.47% |
| UOB GPT-5.1 | 0.5760 | 0.5117 | +6.42 | 0.00018 | 36.79% |
| Rednote dots3-note-prev | 0.5092 | 0.4572 | +5.20 | 0.00497 | 33.07% |
| DeepSeek V4 Flash | 0.4891 | 0.4708 | +1.83 | 0.269 | 35.47% |

All four directions are positive; three tests have p < 0.05. Flash is not significant. Pro and Flash share a provider family. UOB judges Pro; DeepSeek-V4-Pro judges the UOB, Rednote and Flash replications.

Each configuration has 60 independent conversations and 600 planned paired questions. Pro/UOB/Rednote/Flash have 2/9/6/5 missing paired judgments. Score columns and Δ above use available pairs. The inferential target is the conversation-balanced full-grid difference, assigning zero only as the midpoint of each missing difference's [-1,1] domain. The bootstrap is tier-stratified; the sign-flip test uses conversation clusters. Memory budgets and tokenizer/usage conventions differ from this synthetic demo.

| Reader | Full-grid Δ pp | Bootstrap 95% CI (pp) | Missingness-expanded CI (pp) | Judge |
|---|---:|---:|---:|---|
| DeepSeek-V4-Pro | 4.86 | [1.35, 8.23] | [1.02, 8.56] | UOB GPT-5.1 institutional alias |
| UOB GPT-5.1 | 6.33 | [3.26, 9.39] | [1.76, 10.89] | DeepSeek-V4-Pro-0813 |
| Rednote dots3-note-prev | 5.15 | [1.67, 8.47] | [0.67, 9.47] | DeepSeek-V4-Pro-0813 |
| DeepSeek V4 Flash | 1.82 | [-1.32, 4.96] | [-2.15, 5.79] | DeepSeek-V4-Pro-0813 |

10,000 bootstrap resamples (seed 2026080901); 100,000 sign flips (seed 2026080902), plus-one p correction. Input reduction is 1 − summed TOMC provider input / summed hybrid-RAG provider input; it is not the mean of per-sample compression ratios.

These results belong to the frozen BEAM-specific TOMC and BGE hybrid-RAG adapters, not the demo's normalized parser or lexical BM25 baseline. See [boundaries](../docs/claims_and_limitations.md).
