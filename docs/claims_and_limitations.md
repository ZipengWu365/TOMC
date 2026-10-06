# Results and limitations

The current snapshot was exported on 2026-09-28 from manuscript commit `7399657`. [Paper results](paper_results.md) contains the complete tables and source references.

## What the experiments show

| Evidence | Finding | Conditions |
|---|---|---|
| BEAM answer quality | Higher TOMC means in all 18 overall and all 36 long-history comparisons at 500K/1M | Three readers, six evaluated baseline configurations; these are mean comparisons |
| BEAM reader input | Overall savings of 34.77% vs LIGHT and 34.35% vs LLMLingua-2-H | Equal mean of reader-wise ratios on matched valid questions |
| Ten BEAM abilities | Higher TOMC means than BEAM-RAG and LIGHT for temporal reasoning, extraction, contradiction resolution, multi-session reasoning and event ordering | Three-way common valid set; equal mean of 500K/1M ability scores |
| Construction | 4.21 s/call on CPU, no auxiliary neural inference; 3.75 GiB peak process RSS | Six replays; imports, input loading and tokenizer warm-up excluded |
| Repaired NIAH pair | Mean F1 of 87.28 with extra source and 82.26 without it; removal saves about 43%–44% input | Separate batch with byte-identical compiled records |
| VT state diagnostic | 100% item recall for all three readers | Full-history state replay, including after candidate removal |

Construction does not require changing or retraining the reader. Answer quality and input length depend on the task, selected evidence and reader.

## Baseline memory and TOMC memory

The main BEAM comparisons use **the same reader model** on both sides. Each score pair is **Baseline / TOMC**: the named baseline's memory and TOMC's memory, evaluated on matched questions with matched scoring.

TOMC's API integration lets an existing model read the prepared context. It is separate from combining TOMC with another memory method, which these comparisons do not evaluate.

The **compilation ablation** asks a different question. It compares **Full TOMC / TOMC w/o compilation**, removing reader-visible records and their instructions while keeping source text and upstream routing fixed, without refilling the budget.

The RULER component tests are also separate. They remove extra source on NIAH/QA2 or candidate rows on VT. VT remains a state-route diagnostic.

## Compare paired cells

BEAM plans 600 questions per method and reader: 60 conversations, three history lengths and ten abilities. Each baseline comparison has its own valid paired set and scoring protocol. Compare within a score pair; TOMC's absolute numbers across protocol rows are not one shared scoring scale.

The memory cap is 8,192 `cl100k_base` tokens. API reader input also includes the question and prompt overhead. “1M history” describes the original history, not a million-token reader request.

Input changes average reader-wise ratios equally. The long-history summary pools valid questions within each reader before averaging relative changes. Ability plots instead average the 500K and 1M ability means equally.

BEAM-RAG is the evaluated BGE single-route dense-retrieval configuration with pair chunks, top-five retrieval and budget packing. It differs from the demo's line-level BM25 `rag` and the historical Hybrid-RAG control. BRIEF-Pro uses archived hybrid-retrieval candidates. LIGHT uses writer/filter, remote summarization and budget packing.

## Results that limit the interpretation

- At 100K, Flash's mean scores are 61.01 for LIGHT and 58.21 for TOMC. On the common long-history ability set, TOMC trails both controls on instruction following, BEAM-RAG on abstention and LIGHT on summarization.
- Direct LLMLingua-2 has 200 empty memories at 1M, already empty before its guard. Their scores remain included. The low input reflects this unresolved failure, rather than effective compression.
- The BEAM compilation ablation changes mean quality by +1.20 points for GPT-5.1, −0.91 for Rednote and +3.01 for Flash. These protocol-matched results use separate dated batches. Temporal reasoning improves for all three, while event ordering declines for all three.
- Archived NIAH packing removed compiled blocks from the full condition as well as the source-removal condition. The full condition's 88.30 mean F1 therefore reflects retained source text; the removal's zero is a packing failure. The repaired pair is a separate batch. Flash's 100→99 repaired gap comes from one prespecified non-needle sample; both conditions score 100 on the other 99.
- Full-history VT replay reaches 100% recall with or without candidate rows. Compilation from selected evidence alone reaches about 20.4–20.6%, exposing missing dependencies.
- On QA2, raw text from the same selected evidence outperforms records alone and records plus raw for all three readers. Full TOMC scores 40.85 versus Query's 47.49; removing extra source lowers mean F1 to 8.44.

Higher means do not establish significance in every comparison. TOMC also uses more input than several baselines. Quality and input are separate measurements.

## Construction measurements

The table records per-call, per-conversation and batch construction stages. Ratios describe those stages; they are not matched end-to-end speedups.

GPU allocation and process RSS are separate observed maxima. LIGHT's worker measurement includes its KV pool and excludes BGE and remote summarization. It is not a minimum GPU requirement. LLMLingua-2 was measured on CUDA but can be configured differently. TOMC does not have the lowest host RAM measurement. Reader inference and judging are outside the construction measurements.

## Demo limitations

The normalized parser supports defined operations rather than arbitrary natural-language state extraction. The router uses keyword rules; BM25 uses lexical overlap. Negation, paraphrases and ambiguous references can lead to missed evidence or an unsuitable route.

Source references make a retained record inspectable, but do not establish that its interpretation is correct. Row caps and budget packing can omit information. Check sources for important updates and retain raw text when wording matters.

Demo token counts and caller-supplied prices estimate memory size and cost. They do not measure reader accuracy or actual billing. The audit ledger is outside the reader request. Model aliases can change, so a new API run may use a different model snapshot.

## Historical results

The September 4 four-reader Hybrid-RAG batch remains in `benchmarks/HISTORICAL_BEAM.md`, with its original scores, intervals and missingness analysis. It is separate from the current main comparisons.

Older boundary summaries remain in `benchmarks/aggregate_results/boundaries.csv`: IterCOMP multihop favors the control; LongMemEval-V2 ties BGE hybrid at 0.1074; LongBench-v2 full 503 scores 33.0%; UltraLongMix differences are nonsignificant. These are archived summaries, not newly recomputed current-paper results.
