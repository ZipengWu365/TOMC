# Assistant-trial result figures

The four SVG files show the Codex and Claude Code measurements reported on the English and Chinese evidence pages (`docs/evidence.md`, `docs/evidence_zh.md`). The numerical tables sit under each figure as copyable text. `data.json` contains the same displayed values.

## Regenerate

From the repository root, using Python 3.10 or later:

```bash
python scripts/render_readme_results.py
python scripts/render_readme_results.py --check
```

The renderer uses the Python standard library. It reads both evidence-page tables, checks that their numbers agree, and writes the SVGs and `data.json`. A changed result value stops generation so the evidence and captions can be reviewed before publication. No model requests are made.

## Measurement scope

Codex bars show mean total request input, including cached tokens, host instructions and tools. The reduction column uses the mean of nine paired history-level ratios; it is not calculated by dividing the plotted means. All four conditions scored 45/45 on the recorded synthetic latest-state questions. See the [Codex report](../../docs/codex_retention_20261005.md) and [source measurements](../../docs/validation_data/windows_codex_retention_20261005.json).

Claude bars show answering-request costs in USD for the 10K, 20K and 40K synthetic histories. Each displayed condition answered 5/5 questions. Percentages retain the original report's rounding. Its request protocol differs from the Codex experiment; neither figure establishes end-to-end savings for a complete coding session. See the [Claude validation record](../../docs/validation.md#claude-code-windows-validation).

SVGs contain text and shapes, with no embedded font files, scripts or external image dependencies. Each has a title and description; the evidence pages also provide alternative text, exact values and links to the experiment records.
