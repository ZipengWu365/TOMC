# README result figures

The four SVG files show the Codex and Claude Code measurements already reported in the English and Chinese READMEs. The numerical tables remain available under each figure as copyable text. `data.json` contains the same displayed values.

## Regenerate

From the repository root, using Python 3.10 or later:

```bash
python scripts/render_readme_results.py
python scripts/render_readme_results.py --check
```

The renderer uses the Python standard library. It reads both README tables, checks that their numbers agree, and writes the SVGs and `data.json`. A changed result value stops generation so the evidence and captions can be reviewed before publication. No model requests are made.

The optional `--update-readmes` flag embeds the figures, retains the original tables in expandable sections, and applies the associated onboarding copy edits. It checks that the Star header, paper section and fenced code blocks remain unchanged. Running it again leaves the same files:

```bash
python scripts/render_readme_results.py --check --update-readmes
```

## Measurement scope

Codex bars show mean total request input, including cached tokens, host instructions and tools. The reduction column uses the mean of nine paired history-level ratios; it is not calculated by dividing the plotted means. All four conditions scored 45/45 on the recorded synthetic latest-state questions. See the [Codex report](../../docs/codex_retention_20261005.md) and [source measurements](../../docs/validation_data/windows_codex_retention_20261005.json).

Claude bars show answering-request costs in USD for the 10K, 20K and 40K synthetic histories. Each displayed condition answered 5/5 questions. Percentages retain the original report's rounding. Its request protocol differs from the Codex experiment; neither figure establishes end-to-end savings for a complete coding session. See the [Claude validation record](../../docs/validation.md#claude-code-windows-validation).

SVGs contain text and shapes, with no embedded font files, scripts or external image dependencies. Each has a title and description; the READMEs also provide alternative text, exact values and links to the experiment records.
