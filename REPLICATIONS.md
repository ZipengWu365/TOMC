# Independent replications

This page lists every rerun of TOMC Memory's published numbers by someone other than the authors. Failed and partial reruns are listed too, with the same weight as successful ones. A rerun that disagrees with us is useful: it tells us which claim needs a closer look.

| Date | Who | Version or commit | OS and hardware | What was run | Result | Link |
|---|---|---|---|---|---|---|
| — | — | — | — | No independent replications yet. | — | — |

Result: ✓ the numbers matched · ✗ they did not match · partial: some steps matched, some did not or could not run.

## What you can rerun

- **Offline, free, under a minute:** `make reproduce`. It recomputes the paper snapshot arithmetic, the BEAM table (including the 10M follow-up and its session-level intervals), the historical four-reader statistics, the nine synthetic test histories, the v0.3 stale-value benchmark, the adaptive-selection suite and the two documented examples. What each step checks is in [docs/reproducibility.md](docs/reproducibility.md).
- **With your own model account (costs money):** the Codex and Claude Code tests on the synthetic histories (`scripts/benchmarks/codex_retention_cases.py` regenerates them), or `scripts/replicate.py` on your own data. Model names change over time, so say which model and date you used.
- **Not possible from this repository yet:** rebuilding TOMC memory on BEAM. The BEAM adapters, original data files and judge pipeline are not published here.

## How to submit

1. Open a [Replication report](https://github.com/ZipengWu365/TOMC/issues/new?template=replication_report.yml) issue.
2. Include:
   - the version (`python -c "import tomc; print(tomc.__version__)"`) and the commit (`git rev-parse HEAD`);
   - OS, Python version, CPU (and GPU or RAM if relevant);
   - the exact commands you ran;
   - the full output of `make reproduce`, or of the steps you ran;
   - the numbers you got next to the numbers we published, with a link to where we published them;
   - for paid runs: the model, the date, the budget and the number of runs. If a judge model scored answers, name it.
3. Remove anything private (keys, paths, real conversations) before posting.

We add every report to the table above, whether it agrees with us or not. If a report shows one of our numbers is wrong, we correct the number where it appears and link the report from the correction.
