# Current paper results

Synced 2026-09-28 from manuscript commit `7399657`. The report uses recorded benchmark measurements.

## BEAM: three readers and six baseline configurations

**Each score cell is Baseline / TOMC (0–100).** Within a pair, the same reader answers the same questions using memory from the named baseline or memory from TOMC. Bold marks the TOMC score for easy scanning. Combining TOMC with a baseline is a separate configuration that these comparisons do not test.

Questions and scoring are matched within each comparison. The matched set and scoring protocol can differ across rows, so compare the two scores within a cell. Input change measures TOMC relative to that baseline; negative means fewer API input tokens. The mean averages the three readers' percentage changes equally.

Each method/reader comparison planned 600 questions covering ten memory abilities: 60 conversations, with 20 at each of 100K, 500K and 1M history tokens. Memory is capped at 8,192 cl100k_base tokens. API input also includes the question and prompt overhead; the history lengths label the original conversations.

LLMLingua-2-D and -H are the direct and hierarchical configurations. The direct 1M run has 200 empty memories before its final budget check. Their scores remain included, and the cause is unresolved. Its low token count therefore includes failed memory construction.

### Overall

| Baseline memory | GPT-5.1<br>Baseline / TOMC | Rednote preview<br>Baseline / TOMC | DeepSeek 4.1 Flash<br>Baseline / TOMC | Mean input change |
|---|---:|---:|---:|---:|
| LLMLingua-2-D | 37.69 / **60.16** | 34.30 / **54.49** | 33.13 / **57.29** | +7.87% |
| LongLLMLingua | 35.43 / **55.03** | 34.34 / **50.28** | 39.01 / **57.18** | -9.32% |
| BRIEF-Pro | 36.40 / **54.71** | 35.30 / **51.03** | 40.17 / **57.18** | +275.45% |
| LLMLingua-2-H | 44.67 / **60.45** | 39.47 / **56.16** | 37.13 / **57.09** | -34.35% |
| BEAM-RAG | 52.47 / **59.25** | 51.63 / **55.90** | 51.57 / **56.91** | +12.96% |
| LIGHT | 53.75 / **59.48** | 51.75 / **55.90** | 55.65 / **56.91** | -34.77% |

### 100K

| Baseline memory | GPT-5.1<br>Baseline / TOMC | Rednote preview<br>Baseline / TOMC | DeepSeek 4.1 Flash<br>Baseline / TOMC | Mean input change |
|---|---:|---:|---:|---:|
| LLMLingua-2-D | 51.70 / **62.78** | 45.03 / **56.24** | 44.73 / **58.22** | -18.54% |
| LongLLMLingua | 39.23 / **57.29** | 35.36 / **50.53** | 43.55 / **57.63** | +13.24% |
| BRIEF-Pro | 36.67 / **55.90** | 34.54 / **52.18** | 44.43 / **57.63** | +342.06% |
| LLMLingua-2-H | 53.37 / **63.58** | 45.19 / **58.53** | 45.05 / **56.65** | -18.85% |
| BEAM-RAG | 53.58 / **62.26** | 53.48 / **58.25** | 51.57 / **58.21** | +44.86% |
| LIGHT | 60.50 / **62.26** | 57.05 / **58.25** | 61.01 / **58.21** | -18.07% |

### 500K

| Baseline memory | GPT-5.1<br>Baseline / TOMC | Rednote preview<br>Baseline / TOMC | DeepSeek 4.1 Flash<br>Baseline / TOMC | Mean input change |
|---|---:|---:|---:|---:|
| LLMLingua-2-D | 36.68 / **58.99** | 33.96 / **56.71** | 30.49 / **59.22** | -27.09% |
| LongLLMLingua | 34.36 / **56.82** | 34.86 / **54.54** | 36.54 / **59.43** | -19.81% |
| BRIEF-Pro | 37.42 / **55.18** | 35.71 / **54.00** | 39.49 / **59.43** | +277.64% |
| LLMLingua-2-H | 37.31 / **59.00** | 37.13 / **57.94** | 33.53 / **59.58** | -41.73% |
| BEAM-RAG | 53.09 / **59.10** | 52.88 / **56.04** | 53.08 / **59.46** | -0.18% |
| LIGHT | 49.48 / **59.60** | 52.38 / **56.04** | 54.78 / **59.46** | -42.00% |

### 1M

| Baseline memory | GPT-5.1<br>Baseline / TOMC | Rednote preview<br>Baseline / TOMC | DeepSeek 4.1 Flash<br>Baseline / TOMC | Mean input change |
|---|---:|---:|---:|---:|
| LLMLingua-2-D | 24.67 / **58.69** | 23.90 / **50.54** | 24.56 / **54.47** | +3475.88% |
| LongLLMLingua | 32.66 / **50.91** | 32.81 / **45.75** | 36.94 / **54.47** | -21.75% |
| BRIEF-Pro | 35.10 / **53.03** | 35.66 / **46.88** | 36.58 / **54.47** | +205.43% |
| LLMLingua-2-H | 43.34 / **58.78** | 36.01 / **51.97** | 32.74 / **55.10** | -43.00% |
| BEAM-RAG | 50.75 / **56.38** | 48.51 / **53.40** | 50.05 / **53.06** | -4.93% |
| LIGHT | 51.25 / **56.59** | 45.83 / **53.40** | 51.15 / **53.06** | -44.29% |

### Pair counts and scoring protocols

Each cell below gives overall valid pairs / scoring protocol. Every comparison planned 600 questions.

| Baseline | GPT-5.1 | Rednote preview | DeepSeek 4.1 Flash |
|---|---:|---:|---:|
| LLMLingua-2-D | 599 / C | 599 / E | 592 / D |
| LongLLMLingua | 593 / B | 595 / B | 600 / D |
| BRIEF-Pro | 595 / B | 596 / B | 600 / D |
| LLMLingua-2-H | 600 / C | 592 / C | 573 / D |
| BEAM-RAG | 598 / A | 600 / A | 600 / A |
| LIGHT | 599 / A | 600 / A | 600 / A |

A: current RAG/LIGHT, native single-answer Flash scoring. B: archived Pro grouped scoring. C: archived Flash grouped scoring. D: archived Flash-reader answers, native single-answer Flash scoring. E: Rednote direct LLMLingua-2 follow-up, native single-answer Flash scoring. Scoring protocol is shared within a pair, but differs across these groups.

TOMC has higher quality means in all **36 reader × baseline × length comparisons at 500K/1M**, and in all 18 overall comparisons. At 100K, Flash with LIGHT is an exception. These are comparisons of mean quality; significance and individual abilities need separate analysis.

Against LIGHT and hierarchical LLMLingua-2, overall equal-reader input savings are **34.77% and 34.35%**, respectively. Reader input is not end-to-end cost.

### Pooled long histories (500K and 1M)

Within each reader, pool matched questions from 500K and 1M, then calculate quality and input changes. Average the three readers' changes equally.

| Baseline | Relative quality gain | Reader input saving |
|---|---:|---:|
| LLMLingua-2-D | +94.63% | -40.65% |
| LongLLMLingua | +54.66% | +20.77% |
| BRIEF-Pro | +46.77% | -238.50% |
| LLMLingua-2-H | +56.44% | +42.36% |
| BEAM-RAG | +9.42% | +2.57% |
| LIGHT | +11.00% | +43.15% |

Negative saving means TOMC uses more input. BRIEF-Pro uses the archived candidates from hybrid retrieval. BEAM-RAG uses BGE dense retrieval; historical Hybrid-RAG is a separate control. LIGHT uses the documented writer/filter, API summarization and 8K packing configuration. These results apply to those study configurations.

### Ten memory abilities

TOMC, BEAM-RAG and LIGHT are compared on questions valid for all three methods within each reader and history tier. The 500K and 1M ability means receive equal weight. Cells below are **TOMC / BEAM-RAG / LIGHT**, all on 0–100 scales.

| Ability | GPT-5.1 | Rednote preview | DeepSeek 4.1 Flash |
|---|---:|---:|---:|
| Information extraction | 73.55 / 54.92 / 48.60 | 69.17 / 65.11 / 49.48 | 71.83 / 64.33 / 53.29 |
| Multi session reasoning | 62.36 / 51.98 / 50.61 | 63.49 / 53.35 / 56.86 | 61.20 / 50.90 / 54.78 |
| Knowledge update | 43.75 / 45.00 / 30.00 | 61.25 / 45.00 / 48.75 | 60.00 / 57.50 / 52.50 |
| Temporal reasoning | 62.96 / 26.97 / 40.00 | 70.42 / 30.83 / 54.17 | 63.75 / 28.33 / 42.50 |
| Abstention | 77.50 / 80.00 / 72.50 | 47.50 / 57.50 / 30.00 | 70.00 / 75.00 / 70.00 |
| Instruction following | 51.18 / 75.64 / 64.21 | 55.00 / 75.00 / 77.08 | 46.67 / 67.92 / 77.08 |
| Preference following | 92.50 / 91.88 / 88.54 | 86.88 / 94.58 / 82.29 | 87.50 / 91.04 / 83.54 |
| Contradiction resolution | 32.50 / 23.75 / 18.12 | 28.75 / 21.88 / 15.00 | 40.00 / 24.38 / 17.50 |
| Event ordering | 30.60 / 25.24 / 27.59 | 23.70 / 20.79 / 22.26 | 25.46 / 19.58 / 21.57 |
| Summarization | 52.51 / 45.29 / 61.37 | 41.05 / 42.94 / 55.17 | 36.21 / 36.69 / 56.88 |

TOMC leads both controls on temporal reasoning, information extraction, contradiction resolution, multi-session reasoning and event ordering across these readers. It trails both on instruction following, BEAM-RAG on abstention, and LIGHT on summarization.

## BEAM compilation ablation

**What do the compiled records add?** This comparison removes the reader-visible records and accompanying instructions, keeping source text and upstream routing fixed. The freed space is left empty. Each pair uses matched Pro judging in a separate dated batch from the baseline comparisons above.

| Reader | Pairs | Full TOMC / TOMC w/o compilation | Full − removal (points) | Full input change |
|---|---:|---:|---:|---:|
| GPT-5.1 | 597 | 56.20 / 55.00 | +1.20 | +9.46% |
| Rednote preview | 595 | 50.34 / 51.25 | -0.91 | +10.81% |
| DeepSeek 4.1 Flash | 598 | 52.74 / 49.74 | +3.01 | +9.55% |

Compiled records improve temporal reasoning for all three readers, while event ordering declines for all three. Overall changes also vary by reader. The table reports quality and input separately.

## RULER-derived mechanisms and component ablations

These targeted tests use 100 examples per task from RULER generators, with a 65,536-token sequence limit. NIAH and QA2 measure token F1; VT measures answer-item recall. Scores use the study's task-specific evaluation, on a 0–100 scale. Memory construction uses a budget of 4,096 tokens estimated from text length; reported API input is measured separately.

| Archived task comparison | Query mean | Full/state mean | Input saved vs Query |
|---|---:|---:|---:|
| NIAH · retained-source result¹ | 80.91 | 88.30 | 51.8% |
| VT · state-route diagnostic | 46.80 | 100.00 | 89.2% |
| QA2 · full TOMC | 47.49 | 40.85 | 25.5% |

¹ A packing error removed the compiled blocks from the archived NIAH full memories. The 88.30 F1 therefore measures the retained source text. The archived source-removal condition scored zero after the same packing failure, so it cannot isolate the effect of removing source text.

**NIAH after the packing fix.** A separate paired rerun keeps compiled records byte-identical and removes only the extra source block, leaving the freed space empty. Query and head–tail were not rerun, so comparisons with Query remain in the archived table above. The savings below use this rerun's full TOMC as the reference.

| Reader | Pairs | Full TOMC F1 | TOMC w/o extra source F1 | Input saved vs full TOMC |
|---|---:|---:|---:|---:|
| GPT-5.1 | 100 | 85.00 | 79.03 | 43.78% |
| Rednote preview | 100 | 76.84 | 68.76 | 43.95% |
| DeepSeek 4.1 Flash | 100 | 100.00 | 99.00 | 43.33% |

Flash's one-point gap comes from the single prespecified example with no needle; both conditions score 100 on the 99 needle examples. The differences are descriptive.

**VT:** full-history state replay reaches 100% recall for all three readers, including after candidate rows are removed. This diagnostic uses the state route: operations are replayed over the full history. Replaying only selected evidence reaches about 20.4–20.6%, because selection can omit earlier dependencies.

**QA2:** retaining original text from the same selected evidence outperforms records alone and records plus source for every reader. Removing the extra source block from full TOMC lowers mean F1 to 8.44. These questions need source wording to connect facts across passages.

## Construction efficiency and resources

| Method | Auxiliary neural stage | Recorded construction time | Peak GPU allocation (GiB) | Peak host RAM (RSS, GiB) |
|---|---|---:|---:|---:|
| TOMC | None | 4.21 s/call | 0 (CPU) | 3.75 |
| BEAM-RAG | BGE-small | 23.94 s/conversation | 0 (CPU) | 1.45 |
| LongLLMLingua | 7B compressor | 72.07 s/call | 18.50 | 10.24 |
| BRIEF-Pro | 3B compressor | 47.94 s/call | 11.81 | 5.45 |
| LIGHT (worker) | 32B AWQ writer/filter | 41.53 h/batch | 80.82 | 6.04 |
| LLMLingua-2 (direct) | BERT compressor | 9.16 s/conversation | 1.55 | 1.85 |
| LLMLingua-2 (hier.) | BERT compressor | 10.19 s/conversation | 1.55 | 1.62 |

TOMC averaged **4.21 s/call** over six CPU construction replays and used **3.75 GiB** peak host RAM (process RSS). Timing excludes imports, input loading and tokenizer warm-up.

The recorded LongLLMLingua and BRIEF-Pro times measure construction stages per call. Other rows use per-conversation or full-batch times, as labeled. These measurements describe the recorded stages; they do not establish matched end-to-end speedups. BEAM-RAG reuses its index and separately averages 9.71 ms/query for retrieval.

GPU allocation and host RAM are separate observed peaks. LIGHT's memory measurement covers one writer/filter worker, including its allocated KV pool; its 41.53 h timing covers the full 600-memory batch. The worker measurement excludes BGE and remote summarization, and BRIEF-Pro excludes candidate construction. LLMLingua-2 was measured with its CUDA implementation. Reader inference and judging are excluded throughout.

## Evidence and implementation scope

The demo parses explicit operations and retrieves lines with BM25. The benchmark uses the archived task-specific selection, operations and packing configurations. In particular, paper BEAM-RAG uses BGE dense retrieval, and historical Hybrid-RAG is a separate method from the demo's automatic router. TOMC prepares text memory on CPU without auxiliary neural inference; your chosen model then reads that memory and answers.

Run `python benchmarks/reproduce/current.py` to check file hashes and recalculate paired score/input changes, reader averages, pooled long-history results, common-question ability means and the repaired NIAH ablation. The script rebuilds this report from saved aggregate measurements. It makes no API calls or new statistical tests.

[Snapshot and provenance](https://github.com/ZipengWu365/TOMC/tree/main/benchmarks/current_paper) · [Historical four-reader Hybrid-RAG results](https://github.com/ZipengWu365/TOMC/blob/main/benchmarks/HISTORICAL_BEAM.md)
