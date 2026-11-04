# Reproducibility

This repository supports three kinds of checks: running synthetic compiler examples, verifying frozen aggregates, and making new reader calls on your own data.

## One command: `make reproduce`

```bash
make install            # once: creates .venv with the demo, dev and MCP extras
make reproduce          # or: make reproduce PY=python  (use the active Python)
```

It runs offline, makes no model or network calls, and takes under a minute on a laptop (about 37 s on an Apple Silicon Mac). Every step runs in check mode: it recomputes a published number from the files in this repository, compares it with what is written down, and fails on any difference. It rewrites no tracked file, so `git status` is the same before and after. CI runs it on every push and checks `git status` afterwards.

| Step | What it recomputes | Compared with |
|---|---|---|
| `benchmarks/reproduce/current.py --check` | Paper snapshot (100K–1M): file hashes, row counts, paired score and input arithmetic, reader averages, long-history pooling, ability means, repaired NIAH pair | `benchmarks/RESULTS.md` and `docs/paper_results.md`, byte for byte |
| `benchmarks/reproduce/results.py --check` | Historical four-reader batch: effects, bootstrap intervals, sign-flip p values, input reductions | The frozen export, `benchmarks/HISTORICAL_BEAM.md` (exact) and `benchmarks/aggregate_results/recomputed.json` (relative tolerance 1e-12). The plot is drawn to a temporary folder; image bytes are not compared |
| `scripts/make_beam_table.py --check` | BEAM table including the 10M follow-up: every score pair, relative change, mean and input change | The LaTeX sources and image stamp in `assets/beam_table/` and the table blocks on the evidence pages |
| `benchmarks/reproduce/beam10m_bootstrap.py --check` | Session-level bootstrap intervals for the 18 cells at 10M (method below) | `benchmarks/beam_10m_20261010/bootstrap_ci.json` |
| `benchmarks/reproduce/synthetic_corpus.py` | The nine synthetic histories used in the Codex and Claude tests, regenerated from the seeded generator | Corpus SHA-256, per-history hash, length, token estimate and expected answers in `docs/validation_data/windows_codex_retention_20261005.json` |
| `scripts/benchmarks/codex_retention_report.py --verify-published …` | The saved Codex answers, usage accounting and aggregates | The same record (model output and provider usage are not regenerated) |
| `benchmarks/stale/run.py --check` | The v0.3 stale-value benchmark (144 questions per budget) with this checkout's code | `benchmarks/stale/results_after.json` |
| `benchmarks/adaptive/run.py --check` | Fill vs adaptive selection on the deterministic fact-recall suite; fails on any fact adaptive selection loses | `benchmarks/adaptive/expected.json` |
| `benchmarks/reproduce/examples_check.py` | `examples/snapshot.py` (31 → 36 estimated tokens) and `examples/api_context.py` (138 → 90; `framework = FastAPI`, `backup_framework = Flask`) | The numbers quoted in the docs |

To rewrite the generated reports after an intended change, run the scripts without `--check` (`make reproduce-results`, `python benchmarks/reproduce/beam10m_bootstrap.py --write`, `python benchmarks/stale/run.py`, `python benchmarks/adaptive/run.py --write-expected`, `python scripts/make_beam_table.py --render`) and review the diff.

### What `make reproduce` cannot check

- **Rebuilding TOMC memory on BEAM.** The BEAM adapters, the original BEAM data files used in the runs, the job grids and the judge pipeline are not published here, so the 100K–10M memories cannot be rebuilt from this repository. The checks above stop at the saved per-question scores (10M) and aggregates (100K–1M).
- **Paid model runs.** The Codex and Claude Code answers, the BEAM reader answers and all judge scores came from paid model calls. They are checked for internal consistency, not regenerated. `scripts/replicate.py` lets you make new reader calls on your own data.
- **Model aliases change.** A rerun with the same model name later may not use the same model.

If you rerun anything, successful or not, please add it to the [replications list](https://github.com/ZipengWu365/TOMC/blob/main/REPLICATIONS.md) with the *Replication report* issue form.

## Run the compiler offline

Launch `make demo` or call `compile_memory`. The five bundled scenarios are original synthetic examples. `scripts/generate_examples.py` regenerates them byte for byte.

Tests cover snapshot-copy semantics, declared relation composition, count scope, provenance, budget compliance, CLI behavior and mocked optional integrations. Built-in output is deterministic for fixed input and configuration; measured latency varies.

The regex counter requires no external assets. BPE encodings and official learned compressors have separate installation or download requirements.

## Verify current paper aggregates

```bash
python benchmarks/reproduce/current.py --check   # compare only
python benchmarks/reproduce/current.py           # rebuild the reports
```

This checks the snapshot and compares or rebuilds [the result report](paper_results.md). It verifies hashes, row counts, paired score/input arithmetic, equal-reader changes, long-history pooling, common-set ability means and the repaired NIAH pair. The Gradio evidence tab uses the same report code.

The aggregates come from manuscript commit `7399657`; sources and exported fields are recorded in `benchmarks/current_paper/manifest.json`. Resource data retain their original stage boundaries and time units.

The snapshot contains no raw questions or answers. Aggregate verification therefore checks the exported arithmetic, rather than rerunning scoring or reconstructing every current confidence interval and p value.

Authors with source access can refresh the export:

```bash
python scripts/sync_paper.py --paper-repo /path/to/writing-checkout
```

The script reads selected tracked artifacts, requires them to match the supplied commit, and checks BEAM protocols, pair counts and scores against the main-table source. It exports allowlisted aggregates without API calls. Review the resulting changes, then regenerate the report.

## Reconstruct the historical four-reader analysis

```bash
python benchmarks/reproduce/results.py --check   # compare only; writes nothing tracked
python benchmarks/reproduce/results.py           # rewrite the card, JSON and plot
```

This reads `beam_readers.csv` and `beam_clusters.csv`, reconstructs the historical effects, uncertainty intervals, p values and input reductions, and checks the full-precision freeze. Without `--check` it rebuilds `benchmarks/HISTORICAL_BEAM.md`, `recomputed.json` and the SVG/PNG plot; the last floating-point digit in `recomputed.json` and the PNG bytes can change between machines, which is why `make reproduce` uses `--check`. `make reproduce-results` rewrites both this reconstruction and the current report.

Each historical reader configuration has 60 conversation clusters and 600 planned questions. The cluster export contains an ordinal index, history tier, observed/missing counts, summed scores and summed paired differences. It retains first-observed order for seeded resampling, with no original cluster IDs or cross-reader identity join.

The score columns use available-pair means. Inference divides each cluster's observed difference sum by ten; missing differences enter as zero midpoints, not observed zero scores. The procedure uses:

- 10,000 tier-stratified bootstrap resamples, seed 2026080901, with the original nearest-order quantile.
- 100,000 cluster sign flips, seed 2026080902, with the plus-one p correction.
- Missingness-expanded endpoints adjusted by missing pairs / 600.
- Provider totals for paired reader-input reduction.
- Verification tolerances of absolute 1e-12 and relative 1e-10.

Vectorized sign flips preserve Python's original random-bit stream. Near-threshold ties use the original `statistics.mean` convention. Plot bytes can vary with plotting and font versions, so regenerated images need not match historical PNG hashes. Dependency lockfiles and `THIRD_PARTY_LOCK.json` record the staging environment.

Other archived boundary findings are source-hashed transcriptions of the experiment matrix. Their statistical tests are not reconstructed by this command.

## Session-level intervals for the 10M follow-up

```bash
python benchmarks/reproduce/beam10m_bootstrap.py --check
```

The BEAM table reports mean scores only. For the 10M follow-up the repository has per-question scores, so this script adds a rough interval for each of the 18 reader × baseline cells:

- The difference is the mean over valid pairs of (TOMC score − baseline score) × 100, which equals the TOMC mean minus the baseline mean on the table's 0–100 scale. The four invalid judgments are left out, as in the table.
- The 200 questions come from 10 sessions, and questions from the same session are not independent. The script therefore resamples whole sessions: it draws 10 sessions with replacement, pools their valid pairs and recomputes the difference. It does this 10,000 times, re-seeding Python's `random` with 2026102901 for every cell, and reports the 95% percentile interval.
- With only 10 sessions the interval is rough. It covers the 10M follow-up only; the 100K–1M paper rows have aggregates, not per-question scores, so no comparable interval can be computed here.

The result is saved in `benchmarks/beam_10m_20261010/bootstrap_ci.json`, and the script prints it as a table.

## Run a reader on your own data

Create a JSONL file containing text you are authorized to use:

```json
{"messages":[{"role":"user","content":"A = 1\nA = 2"}],"query":"What is the current A?","reference_answer":"2"}
```

The harness defaults to a dry run. Supply prices in one currency; zero prices below are placeholders for planning:

```bash
python scripts/replicate.py examples/replication.jsonl \
  --strategies raw tomc tomc_raw hybrid --budget 512 \
  --input-price 0 --output-price 0 --dry-run
```

The plan records the input hash, version, model, generation settings, request prompt hashes, budget, timestamp, token estimates, attempts and estimated cost at the output cap. It needs no credentials and makes no reader requests. Its default output directory is ignored by Git.

For actual calls, set the variables in `.env.example`, supply your rates and an estimated `--max-cost`, and add `--execute`. It cannot be combined with `--dry-run`. The harness defaults to zero transport retries because failed or timed-out requests may still be billed.

The cost estimate is not a billing cap. Tokenizer differences, hidden tokens and provider behavior can change actual charges. The connector supports bounded retries when explicitly configured.

A run saves a local manifest, usage, response model, finish reason and answer hash. `--save-answers` also writes an ignored private JSONL file. A supplied `reference_answer` enables local exact match; that metric differs from the BEAM judge rubric.

This harness compiles and reads your data. It does not include the unpublished BEAM adapter, original data, job grids, provider aliases/endpoints or full judge harness. Historical API experiments cannot be reproduced with a single command here, and model aliases may change between runs.

## Obtain third-party data

Download from the official project and record its license, immutable revision and file hash. `benchmarks/download_scripts/download_verified.py` accepts an explicit HTTPS URL and required SHA-256, verifies the download, then installs it atomically. It performs no default download and does not extract arbitrary archives.
