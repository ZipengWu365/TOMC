# Reproducibility

This repository supports three kinds of checks: running synthetic compiler examples, verifying frozen aggregates, and making new reader calls on your own data.

## Run the compiler offline

Launch `make demo` or call `compile_memory`. The five bundled scenarios are original synthetic examples. `scripts/generate_examples.py` regenerates them byte for byte.

Tests cover snapshot-copy semantics, declared relation composition, count scope, provenance, budget compliance, CLI behavior and mocked optional integrations. Built-in output is deterministic for fixed input and configuration; measured latency varies.

The regex counter requires no external assets. BPE encodings and official learned compressors have separate installation or download requirements.

## Verify current paper aggregates

```bash
python benchmarks/reproduce/current.py
```

This checks the snapshot and rebuilds [the result report](paper_results.md). It verifies hashes, row counts, paired score/input arithmetic, equal-reader changes, long-history pooling, common-set ability means and the repaired NIAH pair. The Gradio evidence tab uses the same report code.

The aggregates come from manuscript commit `7399657`; sources and exported fields are recorded in `benchmarks/current_paper/manifest.json`. Resource data retain their original stage boundaries and time units.

The snapshot contains no raw questions or answers. Aggregate verification therefore checks the exported arithmetic, rather than rerunning scoring or reconstructing every current confidence interval and p value.

Authors with source access can refresh the export:

```bash
python scripts/sync_paper.py --paper-repo /path/to/writing-checkout
```

The script reads selected tracked artifacts, requires them to match the supplied commit, and checks BEAM protocols, pair counts and scores against the main-table source. It exports allowlisted aggregates without API calls. Review the resulting changes, then regenerate the report.

## Reconstruct the historical four-reader analysis

```bash
python benchmarks/reproduce/results.py
```

This reads `beam_readers.csv` and `beam_clusters.csv`, reconstructs the historical effects, uncertainty intervals, p values and input reductions, and checks the full-precision freeze. It rebuilds `benchmarks/HISTORICAL_BEAM.md` and its SVG/PNG plot. `make reproduce-results` runs both this reconstruction and current aggregate verification.

Each historical reader configuration has 60 conversation clusters and 600 planned questions. The cluster export contains an ordinal index, history tier, observed/missing counts, summed scores and summed paired differences. It retains first-observed order for seeded resampling, with no original cluster IDs or cross-reader identity join.

The score columns use available-pair means. Inference divides each cluster's observed difference sum by ten; missing differences enter as zero midpoints, not observed zero scores. The procedure uses:

- 10,000 tier-stratified bootstrap resamples, seed 2026080901, with the original nearest-order quantile.
- 100,000 cluster sign flips, seed 2026080902, with the plus-one p correction.
- Missingness-expanded endpoints adjusted by missing pairs / 600.
- Provider totals for paired reader-input reduction.
- Verification tolerances of absolute 1e-12 and relative 1e-10.

Vectorized sign flips preserve Python's original random-bit stream. Near-threshold ties use the original `statistics.mean` convention. Plot bytes can vary with plotting and font versions, so regenerated images need not match historical PNG hashes. Dependency lockfiles and `THIRD_PARTY_LOCK.json` record the staging environment.

Other archived boundary findings are source-hashed transcriptions of the experiment matrix. Their statistical tests are not reconstructed by this command.

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

This harness compiles and reads your data. It does not include the private BEAM adapter, original data, job grids, provider aliases/endpoints or full judge harness. Historical API experiments cannot be reproduced with a single command here, and model aliases may change between runs.

## Obtain third-party data

Download from the official project and record its license, immutable revision and file hash. `benchmarks/download_scripts/download_verified.py` accepts an explicit HTTPS URL and required SHA-256, verifies the download, then installs it atomically. It performs no default download and does not extract arbitrary archives.
