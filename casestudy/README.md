# TOMC in Practice: Three Real Projects

Updated: 2026-10-20. This record brings together measurements from three completed projects, using each project's original reporting cutoff.

**TOMC saved 45,754 tokens in matched Xiaohongshu calls and 115,529 tokens in a research-slide workflow. For a Kuaishou video, five paired background-text packets became 42.15% smaller.** These projects used TOMC without a dedicated token-saving skill. Ordinary content, video-editing and research skills were part of the production workflows, with TOMC as the only tool specifically used for token optimization.

## Results at a glance

| Real task | Deliverable and conversation | Comparison scope | Without TOMC → With TOMC | Aggregate savings | Best single round |
| --- | --- | --- | --- | --- | --- |
| Xiaohongshu / Rednote post | 20 pages, 6 groups, 4 chapters, 19 user messages | 12 matched model-call pairs, 24 calls total | 886,936 → 841,182 tokens | 45,754 tokens, 5.16% | 8.36% of total tokens |
| Kuaishou short video | Approximately 5:12 video plus cover, 5 user messages | 5 paired text-packet comparisons | 27,104 → 15,681 proxy tokens | 11,423 tokens, 42.15% | 54.46% of packet tokens |
| Research literature slides | 10 papers, 28 English slides and Chinese speaker notes, 25 user messages across the broader project | 12 matched pairs for the current 10-paper workflow, 24 calls total | 560,736 → 445,207 tokens | 115,529 tokens, 20.60% | 27.66% of total tokens |

User-message counts describe human inputs. One message can lead to multiple model requests, tool calls and revisions. The research project's 25 messages cover a broader scope, including 12 messages during the TOMC comparison phase. They do not correspond one-to-one with the selected model-call pairs.

Xiaohongshu and research figures use actual model-reported usage. Kuaishou has a paired A/B comparison of the same external text before and after preparation, counted with the `o200k_base` proxy tokenizer. Its 42.15% describes packet-token reduction. Best-round rates describe individual comparisons, while aggregate rates use the sums across all selected rounds.

## Settings: default mode and strength 80

| Project | User-reported setup | Parameters visible in saved records | Preparation frequency and method |
| --- | --- | --- | --- |
| Xiaohongshu | Default mode, described by the user as default strength 60 | `prepare_context(history, task)` with the default budget, retaining approximately 80% of lexical material | External context prepared before each measured B request, with essential facts protected separately |
| Kuaishou | Default mode, described by the user as default strength 60 | Explicit lexical budgets of 2,800, 3,000, 3,600, 2,300 and 3,500 across five rounds | One MCP `prepare_context` call per round, using `rag` for the first two and `tomc_raw` for the last three |
| Research slides | Compression strength 80, preparation before every call | The original experiment report records a 60% external-material retention target before each B request | Official Python entry point sharing the MCP compression core, called before each measured B request |

**The user confirmed that 80 means compression strength, not 80% material retention.** User-facing strength labels and logged budgets are recorded separately. The logs do not independently establish a mapping from strength 80 to 60% retention. The projects also differ in task and material, so they do not isolate the effect of changing strength alone.

All three projects record `gpt-6.1-sol` with `high` reasoning effort. Xiaohongshu and research comparisons used separate temporary `codex exec` sessions, with no additional tool calls inside each measured generation. Kuaishou used MCP context preparation within the actual production conversation. TOMC processed explicitly supplied external material. The host managed the active chat context.

## Case 1: A 20-page Xiaohongshu post

<img src="xiaohongshu/post.png" alt="Actual Xiaohongshu post cover" width="420">

### Task and versions

A comparison of six sixth-generation K-pop girl groups, delivered as a 20-page post with 4 chapters. The completed-post project contained 19 user messages, including 13 content-edit requests. The primary comparison uses the 12 matched pairs in `R03–R14`, with 12 model calls per arm. Later promotional graphics and additional revisions are outside this snapshot.

The installation record lists plugin package `0.1.2`, core `0.1.0` and source commit `7380ca04adcd41e3c949fb35458771e46c02596e`. Codex CLI was `0.163.0-alpha.10.2`. The post snapshot cutoff was 2026-10-18 09:03:50.804, Asia/Shanghai.

Each pair matched task, source-history and protected-evidence hashes, model and reasoning effort. Each round's external history had a lexical estimate of 22,126. The default budget was 17,701, with approximately 17,695–17,701 retained. Data tables and essential facts were kept outside the compression region in both arms.

### Token comparison

| Metric | A: without TOMC | B: with TOMC | A−B |
| --- | --- | --- | --- |
| Input tokens, including cached input | 766,119 | 725,644 | 40,475 |
| Cached input, included above | 166,016 | 161,280 | 4,736 |
| Uncached input | 600,103 | 564,364 | 35,739 |
| Output tokens, including reasoning | 120,817 | 115,538 | 5,279 |
| Total tokens | 886,936 | 841,182 | 45,754 |

Aggregate total-token savings were **5.16%**, with input reduced by **5.28%**. The best single round was R03, from 67,466 to 61,826 total tokens, saving 5,640 tokens or **8.36%**.

| Round | A total tokens | B total tokens | Tokens saved | Reduction | A request seconds | B request seconds |
| --- | --- | --- | --- | --- | --- | --- |
| R03 | 67,466 | 61,826 | 5,640 | 8.36% | 194.951 | 161.552 |
| R04 | 72,933 | 72,780 | 153 | 0.21% | 175.601 | 207.613 |
| R05 | 67,976 | 64,846 | 3,130 | 4.60% | 112.781 | 95.753 |
| R06 | 72,951 | 68,179 | 4,772 | 6.54% | 212.758 | 180.427 |
| R07 | 77,778 | 74,826 | 2,952 | 3.80% | 163.707 | 164.705 |
| R08 | 80,618 | 76,932 | 3,686 | 4.57% | 179.130 | 151.675 |
| R09 | 75,410 | 70,243 | 5,167 | 6.85% | 115.156 | 92.102 |
| R10 | 84,313 | 78,822 | 5,491 | 6.51% | 175.218 | 150.510 |
| R11 | 50,352 | 48,192 | 2,160 | 4.29% | 77.976 | 90.297 |
| R12 | 77,336 | 73,036 | 4,300 | 5.56% | 118.124 | 116.020 |
| R13 | 52,502 | 50,018 | 2,484 | 4.73% | 54.489 | 58.493 |
| R14 | 107,301 | 101,482 | 5,819 | 5.42% | 359.052 | 320.115 |

Earlier round `R00a` used a different treatment, and `R01/R02` had contaminated comparisons. They are excluded from the savings calculation above. The historical ledger retains all 15 calls per arm before promotional work: A used 1,037,437 tokens and B used 980,203. That ledger is separate from the 12 valid matched pairs.

### Time, CPU and memory

| Metric | A: without TOMC | B: with TOMC | Observed difference or scope |
| --- | --- | --- | --- |
| Cumulative wall time for 12 model requests | 1,938.942 s | 1,789.262 s | 149.680 s less, approximately 7.72% |
| Cumulative outer preparation wall time | 11.829 s | 5.700 s | Includes process startup and scheduling |
| Requests plus outer preparation wall time | 1,950.771 s | 1,794.962 s | 155.810 s less |
| Cumulative internal preparation-worker wall time | 0.875201 s | 2.620329 s | B used 1.745128 s more |
| Cumulative preparation-worker CPU time | 0.890625 CPU s | 3.218750 CPU s | B used 2.328125 CPU s more |
| Maximum single-worker peak memory | 16,101,376 B (15.355 MiB) | 24,440,832 B (23.309 MiB) | B used 8,339,456 B more |
| Model-client CPU and peak memory | Not collected | Not collected | Resource measurements above cover the preparation worker |
| Local CPU utilization percentage | Not collected | Not collected | Distinct from cumulative CPU seconds |

CPU and memory measurements cover an isolated preparation process, including the Python interpreter and imports. Outer preparation time already includes internal worker time. Arm A also used a preparation worker to read the uncompressed material. In this observation, cumulative model waiting time fell while local preparation used slightly more CPU and memory.

These figures cover accumulated request and preparation time. Human review, layout, rendering and parallel production activities were not independently replayed for each arm. Whole-project labor-time savings were not measured.

### Files and installation footprint

| Logical file sizes across 12 rounds | A | B | A−B |
| --- | --- | --- | --- |
| external_history.txt | 825,744 B | 825,744 B | 0 B |
| prepared_context.txt | 825,744 B | 652,464 B | 173,280 B |
| prompt.txt | 1,904,119 B | 1,730,839 B | 173,280 B |
| response.txt | 220,085 B | 235,348 B | -15,263 B |

The saved `prepared_context.txt` files and the complete `prompt.txt` files containing that context each decreased by 173,280 B. They are separately stored files. UTF-8 reply bytes and model output tokens use different units, and B's reply files were larger in bytes. The 20 delivered PNGs totaled **12,870,832 B**, representing the shared final production output. Separate A/B image-storage savings were not measured.

Historical installation measurements were 157,379,705 B for the source checkout, 46,193,604 B for the plugin package and environment, and 33,628,251 B for the uv executable. These are logical file sizes at the measurement point, including environment or development files. They do not represent a minimum plugin download size. Complete initial installation time, CPU and download traffic were not collected.

### What this case suggests

Repeatedly carrying long background material can accumulate savings even with a conservative default budget. This task also needed substantial protected data and creative output, so total-token savings were smaller than the external-history reduction. Essential facts were protected separately after early omissions. Research background and historical explanations were suitable compression targets, while numbers and citations stayed intact.

## Case 2: A Kuaishou video and cover

![Actual Kuaishou video cover](kuaishou/cover.png)

### Task and comparison

A meeting-room discussion was edited from approximately 11 minutes 40 seconds of source footage into a 312.366667-second video, approximately 5:12, at 1080×1920 with H.264/AAC, plus a cover. The production phase contained 5 user messages, including editing revisions and account-workflow updates.

**All five rounds saved paired A/B text packets using the same source material and task.** A contained the full packet, and B contained TOMC-selected context. Both were counted with the same proxy tokenizer. The actual production conversation separately contained 113 model requests. Those requests do not constitute 113 A/B pairs.

Versions were plugin `0.1.2`, Python `3.12.14` and tiktoken `0.14.0`. The production measurement window was 2026-10-18 05:46:34.846 to 08:19:21.748, Asia/Shanghai. The main case includes rounds 001–005, with later promotional revisions recorded separately.

### Five-round token comparison and settings

| Round | A packet tokens | B packet tokens | Tokens saved | Reduction | TOMC service seconds |
| --- | --- | --- | --- | --- | --- |
| 001 | 4,200 | 2,899 | 1,301 | 30.98% | 0.0240093 |
| 002 | 5,523 | 3,076 | 2,447 | 44.31% | 0.0155380 |
| 003 | 6,644 | 3,724 | 2,920 | 43.95% | 0.0182711 |
| 004 | 5,143 | 2,342 | 2,801 | 54.46% | 0.0193568 |
| 005 | 5,594 | 3,640 | 1,954 | 34.93% | 0.2132424 |

The aggregate was **27,104 → 15,681**, saving **11,423** packet proxy tokens or **42.15%**. Round 004 reached **54.46%**.

| Round | Method | Lexical budget | Lexical input | Lexical output | Actual retention |
| --- | --- | --- | --- | --- | --- |
| 001 | rag | 2,800 | 4,032 | 2,693 | 66.79% |
| 002 | rag | 3,000 | 5,474 | 3,000 | 54.80% |
| 003 | tomc_raw | 3,600 | 6,540 | 3,599 | 55.03% |
| 004 | tomc_raw | 2,300 | 5,126 | 2,299 | 44.85% |
| 005 | tomc_raw | 3,500 | 6,097 | 3,499 | 57.39% |

Lexical estimates control TOMC's budget. The proxy tokenizer measures packet length. These are separate counting methods. Actual model requests also include task instructions, host history and tool records beyond the prepared material.

### Actual production-conversation usage

| Metric | Recorded production-phase usage |
| --- | --- |
| User messages | 5 |
| Model requests | 113 |
| Input tokens | 20,044,994 |
| Cached input, included above | 19,305,856 |
| Uncached input | 739,138 |
| Output tokens | 143,639 |
| Reasoning output, included above | 58,294 |
| Input plus output | 20,188,633 |
| TOMC calls | 5, all successful |

This table records the actual single production workflow. The five-round A/B table measures the external packets. A complete independent production run without TOMC was not performed, so whole-workflow token, cost, time and CPU savings remain unmeasured. Round 003 also used cover-image generation, whose internal tokens and cost were not returned.

### Time, CPU and memory

| Metric | Recorded value | Scope |
| --- | --- | --- |
| Sum of 5 TOMC service-reported durations | 0.2904176 s | Per-call values appear above |
| Sum of 5 outer TOMC tool wall times | 0.293 s | Tool start-to-finish intervals, including scheduling |
| Sum of host active-task durations across 5 rounds | 2,887.639 s, approximately 48 min 8 s | Includes models, tools and waiting |
| Elapsed time from the first start to the end of round 5 | 9,166.902 s, approximately 2 h 32 min 47 s | Includes user review and gaps between rounds |
| Independent A/B whole-production time and time saved | Not measured | Paired packets and actual production time are recorded separately |
| TOMC CPU seconds, utilization percentage and peak memory | Not collected | Service duration does not measure CPU time |
| Whole-production CPU and memory, including FFmpeg | Not fully collected | No inference from video duration |

TOMC tool time is already part of host active-task time. Service calls were short, while transcription, editing, rendering and human review had their own costs. The available records keep those scopes separate.

### File footprint

| Item | Logical file size | Scope |
| --- | --- | --- |
| Five A full external-context text files | 84,903 B | Sum of `A_full_context.txt` files |
| Five B prepared-context text files | 46,818 B | Sum of `B_TOMC_context.txt` files |
| Reduction in saved external-context text | 38,085 B | Excludes task instructions counted in packet-token comparisons |
| Source video | 810,471,146 B | Original footage |
| Final video | 396,542,970 B | Edited and encoded deliverable |
| Cover included here | 153,944 B | The user's selected cover |
| Separate plugin installation footprint | Not collected | Other projects' environment sizes are not substituted |

The source-to-final video size difference comes from editing and encoding. It is separate from TOMC's context reduction.

### What this case suggests, including later records

When only part of a long transcript is relevant to an edit, selecting external context can substantially reduce the packet. This run also omitted some family-budget background and a compromise-budget window. Production returned to the full transcript and timecodes. A useful workflow is to retain the original transcript and word-level timing, use prepared context to locate relevant sections, then check the original material during precise editing.

Later promotional rounds used shorter packets, several of which remained unchanged after preparation. The broader 14-round record contains 16 user messages, 183 model requests and 35,600,221 host tokens. Of 15 TOMC attempts, 12 succeeded and 3 failed, with failures in rounds 007/008. The 12 available packet pairs totaled 31,059 → 19,636, a 36.78% reduction. These broader historical figures are separate from the five production rounds above.

## Case 3: Ten papers and 28 research slides

![Actual research literature-analysis slide](research-ppt/slide.png)

### Task and setup

A literature-analysis project on healthy aging and wearable world models produced detailed reviews of the first 10 papers, 28 English research slides and Chinese speaker notes. The original report counted 25 user messages across the project, including 12 during the TOMC comparison phase. The current 10-paper comparison uses batches 12–21, 76 and 77, totaling 12 pairs and 24 model calls.

The user described the setting as "compression strength 80, compress before every call." The experiment report records `prepare_context` before each B request, with a 60% external-material retention target. The saved arm name was `B_TOMC_60_every_call`. Both fields are retained with their original meanings.

Python was `3.12.14`, TOMC commit was `d848a4a2d53e000a96dca519c1e28dcf68813acb`, and the research-project commit was `cd745fe048983669a6a38e6e33a574f79a2bd88a`. The reporting cutoff was 2026-10-19 03:05:54.487, Asia/Shanghai.

Each pair used the same task hash, model and reasoning effort. Revisions could read each arm's own draft. The Chinese notes used the same frozen source packet. Each task ran once per arm, usually A before B. Batch 77 ran in parallel, and execution order was not randomized.

### Token comparison

| Metric | A: without TOMC | B: with TOMC | A−B |
| --- | --- | --- | --- |
| Input tokens, including cached input | 492,661 | 371,918 | 120,743 |
| Cached input, included above | 15,360 | 30,336 | -14,976 |
| Uncached input | 477,301 | 341,582 | 135,719 |
| Output tokens, including reasoning | 68,075 | 73,289 | -5,214 |
| Total tokens | 560,736 | 445,207 | 115,529 |

Aggregate total-token savings were **20.60%**, with input reduced by **24.51%**. B produced 5,214 more output tokens. Both input and output determine the final savings. Batch 18 had the largest single-round percentage reduction: 61,862 → 44,751, saving 17,111 tokens or **27.66%**.

| Batch | A total tokens | B total tokens | Tokens saved | Reduction | A request seconds | B request seconds |
| --- | --- | --- | --- | --- | --- | --- |
| 12 | 41,920 | 32,448 | 9,472 | 22.60% | 161.671 | 97.352 |
| 13 | 40,290 | 32,539 | 7,751 | 19.24% | 161.672 | 107.794 |
| 14 | 37,435 | 31,304 | 6,131 | 16.38% | 127.404 | 100.626 |
| 15 | 65,632 | 47,743 | 17,889 | 27.26% | 98.766 | 132.021 |
| 16 | 43,136 | 34,363 | 8,773 | 20.34% | 103.514 | 129.400 |
| 17 | 31,296 | 26,957 | 4,339 | 13.86% | 84.118 | 122.319 |
| 18 | 61,862 | 44,751 | 17,111 | 27.66% | 97.850 | 112.481 |
| 19 | 35,522 | 28,741 | 6,781 | 19.09% | 118.264 | 93.771 |
| 20 | 34,177 | 29,954 | 4,223 | 12.36% | 91.453 | 112.694 |
| 21 | 44,292 | 34,194 | 10,098 | 22.80% | 117.652 | 137.330 |
| 76 | 57,632 | 47,915 | 9,717 | 16.86% | 184.586 | 221.443 |
| 77 | 67,542 | 54,298 | 13,244 | 19.61% | 348.403 | 370.164 |

### Per-call preparation size and overhead

| Batch | Lexical input | Lexical output | Preparation wall seconds | Preparation CPU seconds |
| --- | --- | --- | --- | --- |
| 12 | 18,872 | 11,317 | 0.122 | 0.121 |
| 13 | 16,988 | 10,186 | 0.104 | 0.104 |
| 14 | 15,727 | 9,436 | 0.090 | 0.090 |
| 15 | 38,311 | 22,986 | 0.119 | 0.118 |
| 16 | 20,073 | 12,040 | 0.085 | 0.085 |
| 17 | 10,323 | 6,193 | 0.059 | 0.059 |
| 18 | 31,106 | 18,661 | 0.140 | 0.140 |
| 19 | 13,563 | 8,133 | 0.082 | 0.082 |
| 20 | 13,198 | 7,918 | 0.078 | 0.077 |
| 21 | 19,905 | 11,938 | 0.115 | 0.114 |
| 76 | 32,440 | 19,461 | 0.438 | 0.436 |
| 77 | 33,436 | 20,061 | 0.724 | 0.719 |

Summing these rows gives **263,942 → 158,330** lexical units, approximately 60% retained. The 12 preparations used **2.156 s** of wall time and **2.145 CPU s**. These sums use the original report's per-batch values rounded to three decimal places.

### Request time, CPU and memory

| Metric | A: without TOMC | B: with TOMC | Observed difference |
| --- | --- | --- | --- |
| Cumulative model-request wall time | 1,695.353 s | 1,737.395 s | B took 42.042 s more, approximately 2.48% |
| Cumulative wall time with B preparation added | 1,695.353 s | 1,739.551 s | B took 44.198 s more |
| Cumulative model-client CPU time | 67.120 CPU s | 68.170 CPU s | B used 1.050 CPU s more |
| Cumulative CPU time with B preparation added | 67.120 CPU s | 70.315 CPU s | B used 3.195 CPU s more |
| Maximum sampled single-request peak RSS | 417,918,976 B (398.559 MiB) | 398,290,944 B (379.840 MiB) | B used 19,628,032 B less, approximately 4.70% |
| Local CPU utilization percentage | Not collected | Not collected | CPU seconds do not establish utilization percentage |

CPU and RSS measurements cover the local model client, with preparation recorded separately. The RSS row compares each arm's maximum sampled single-request peak. This 10-paper workflow saved tokens while cumulative model-request time increased by 42.042 s. Some calls overlapped, so accumulated request times differ from project elapsed time. Shared retrieval, fact-checking, layout and human review were not independently timed as two complete workflows.

### Rendering, installation and storage

The original report retains 8 successful renders of the 28-slide deck. A had 5 renders totaling 50.917 s of wall time and 47.387 CPU s. B had 3 renders totaling 30.782 s and 27.890 CPU s. Each arm also had 2 Chinese-notes PDF exports: A totaled 9.496 s and 9.194 CPU s, while B totaled 9.319 s and 9.005 CPU s. Render counts and revision states differ, so these figures describe production overhead rather than a comparison at equal workload. Failed prototypes were not fully timed.

| Historical deliverable size | A | B | B−A |
| --- | --- | --- | --- |
| 28-slide PPTX | 1,251,373 B | 1,252,494 B | 1,121 B more |
| English-slide PDF | 1,710,707 B | 1,711,709 B | 1,002 B more |
| Chinese-notes PDF | 1,883,451 B | 1,886,289 B | 2,838 B more |
| Chinese-notes DOCX | 58,656 B | 59,470 B | 814 B more |
| Total of the four files | 4,904,187 B | 4,909,962 B | 5,775 B more |

These sizes come from the original report. This directory contains one slide screenshot, while the papers, full decks and notes remain with the project owner. Final file sizes depend on images, text and packaging as well as content, and B's files were slightly larger despite using fewer model-input tokens.

Historical installation sizes were 158,401,058 B for TOMC source, 46,463,758 B for the Python virtual environment and 11,124,117 B for cache. A successful MCP validation took 1.915 s. Complete installation wall time and CPU were not recorded. The original project also removed 150 obsolete output files totaling 102,465,226 B in a 2.053 s cleanup operation. That version cleanup is recorded separately from TOMC savings.

### Broader historical comparison and quality

Including an earlier overview and revisions, the delivered workflows contained 23 matched model-call pairs: 912,402 → 759,238 tokens, saving 153,164 or 16.79%. The current 12-pair, 10-paper workflow is a subset, so these savings cannot be added together. The broader experiment's 27 complete pairs also include deferred second-batch work. Unpaired and stopped calls are retained separately, without treating unfinished work as savings.

For the first 10 papers, original drafts contained 66 missing-information markers in A and 90 in B. Shared editing logged 208 entries for A and 435 for B. Both final decks had 28 slides after source checking, figure additions, content revision and layout work. These records preserve the review and repair effort alongside token savings.

## What do the saved tokens mean in dollars?

The original case estimates used rates recorded on 2026-10-19: US$2 per million uncached input tokens, US$0.10 per million cached input tokens and US$10 per million output tokens. The original pricing reference was the [GPT-6.1 Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol). These historical rates support reproduction of this record, rather than a forecast of future prices.

| Case | A equivalent per task | B equivalent per task | Difference per task | 100 similar tasks | 1,000 similar tasks |
| --- | --- | --- | --- | --- | --- |
| Xiaohongshu, 12 paired calls per arm | US$2.4249776 | US$2.3002360 | US$0.1247416 | 4,575,400 tokens, approximately US$12.47 | 45,754,000 tokens, approximately US$124.74 |
| Research, current 10-paper workflow | US$1.6368880 | US$1.4190876 | US$0.2178004 | 11,552,900 tokens, approximately US$21.78 | 115,529,000 tokens, approximately US$217.80 |
| Kuaishou, five background-text packets | US$0.054208 | US$0.031362 | US$0.022846 | 1,142,300 proxy tokens, approximately US$2.28 | 11,423,000 proxy tokens, approximately US$22.85 |

For Xiaohongshu and research, the formula is `(uncached input × 2 + cached input × 0.10 + output × 10) / 1,000,000`. Kuaishou estimates apply only the assumed US$2/M uncached input rate to packet proxy tokens, excluding output and host-cache effects.

The 100-task and 1,000-task projections multiply the unrounded single-case results, assuming the same workload, rates and cache/output mix. These are API-equivalent estimates. Actual subscription billing was not available. Labor, hardware, image-model and energy costs are outside the estimates. Best-round percentages are not applied to whole tasks.

## Practical lessons from these three projects

1. **Start with long background material that gets read repeatedly.** Literature notes, transcripts, external project history and old-version explanations were useful targets. The research workflow removed 120,743 input tokens, showing how repeated preparation can accumulate savings.
2. **Protect exact evidence separately.** Keep numerical tables, citations, verbatim speech, timecodes, formulas and current task requirements intact. Compress background, then retrieve precise evidence when needed.
3. **Start with defaults and tune using omissions and final usage.** The first two projects used the user's reported default mode. Research used strength 80 and preparation before every call. Material length, relevance, output size, caching and repair work all affect the result.
4. **Short inputs may need no preparation.** Several later Kuaishou packets remained unchanged. Repeated preparation offers limited benefit when the new instruction is brief and the material is already compact.
5. **Track tokens, time and machine resources separately.** Xiaohongshu's cumulative requests took approximately 150 s less, while research took approximately 42 s more. Fewer tokens do not guarantee shorter waits. Local CPU, cloud inference and video rendering have different resource scopes.
6. **Test a token-saving skill combination as a separate experiment.** None of these cases measured that combination. A useful next comparison would hold task, material and quality requirements fixed while testing TOMC, a dedicated skill and both together.

These observations come from one user's three real projects. Each generation task had one run per arm rather than repeated randomized trials. The figures retain their task and configuration scope.

## Measurement definitions and provenance

Total tokens equal input plus output. Cached input is already included in input, and reasoning output is already included in output. Reduction rates use `(A−B)/A`. CPU seconds measure accumulated process CPU time, while wall seconds measure elapsed time. One MiB equals 1,048,576 B. Directory sizes are logical file bytes. Allocated disk space, system-wide CPU utilization, cloud CPU/GPU usage, power, energy and complete network traffic were not measured.

This directory publishes measurement fields and three user-selected deliverable images. Private conversations, transcripts, model replies, full papers and credentials remain local. The source labels and hashes below identify the owner's retained records. They are provenance entries rather than repository-relative file links.

| Source record | SHA256 |
| --- | --- |
| Xiaohongshu stage-usage report, v14 | `4de4fe4427325f5bf8c32fa6325f3bd4f33a677131679c0b2c47bd4bf64a0dfc` |
| Kuaishou per-round context-comparison CSV | `db34ce7db9cf902c644d906536263658b80e6e3a62e96a732f09f78547aa1133` |
| Kuaishou extended audit, `audit_summary.json` | `dd01ca7392da548fa1fd372815197ed0661bfb9fc1ca15c5ef647a0277681a57` |
| Research complete TOMC comparison report | `aa3afec4fa6542c29d7e1416b434335c9970e192bd3d4905a8e150907bca87d1` |

The Kuaishou source CSV includes later promotional iterations. This case selects the first five production rounds. Xiaohongshu timing and resources were recalculated from `R03–R14` records in `result.json` and `preparation_metrics.json`, with file sizes summed from the associated files. Research tokens, time, CPU, rendering and deliverable sizes come from the original report. Normalized per-call CSVs were also used to check token totals. This documentation update did not run new paid A/B model experiments.

### Images included here

| Project | File | Bytes | SHA256 |
| --- | --- | --- | --- |
| Xiaohongshu | `xiaohongshu/post.png` | 1,585,626 | `d0aa2e7685427b2ffc65bb6b1dc4bf51050671548f101b349478936d71b52684` |
| Kuaishou | `kuaishou/cover.png` | 153,944 | `3ee75c547d6e5417fbd01214db2a1c40b38a37ea231ca8d748fcd4fb597d61cd` |
| Research slides | `research-ppt/slide.png` | 89,265 | `92637f03413d0ed83bbad17fb259cc6678287e7a2b992b8de8320d0210982900` |
