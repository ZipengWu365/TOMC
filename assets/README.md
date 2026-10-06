# Project figures

## Current product identity — 2026-10-02

`tomc_logo_20261002.png` is the new transparent horizontal product logo: linked note cards, a return arrow and a TOMC wordmark. It replaces the earlier indexed-card mark in the homepage header. The README uses a larger functional heading and a separate short subtitle below it.

`plugin_usage_api_20261003.png` is the current landscape usage illustration: `plugin_usage_api_20261002.png` with an added "& Claude Code" line under the Claude Desktop label ([edit record](plugin_usage_api_20261003.prompt.md)). `plugin_usage_api_20261002.png` is the unedited source. It shows preparing context before the next LLM API request, with assistant plugins or Python API entry points and task records plus source text as the output. Its exact prompt and paper authority are in [the API illustration record](plugin_usage_api_20261002.prompt.md). It is a conceptual workflow; savings depend on the history and task, and an MCP tool does not erase an existing host conversation.

`plugin_usage_context_20261002.png` is the preceding context-representation illustration. It leads with the stateless compiler and keeps notebook storage optional. It remains a historical asset with its [generation record](plugin_usage_context_20261002.prompt.md).

The current logo and context illustration have byte-identical copies in `docs/assets/` so the documentation site builds without external image paths. These are conceptual product assets, not client screenshots or measured results. Short histories can remain intact; supported operations and source-retention choices depend on the route.

`plugin_usage_20261002_v2.png` is the earlier notebook-oriented illustration with the new identity. Its source is preserved in [the brand refresh record](tomc_brand_20261002.prompt.md); it is no longer the primary product introduction. The earlier logo and generated notebook illustrations remain available as historical assets.

## Plugin usage illustration — 2026-10-02

`plugin_usage_20261002.png` is the earlier landscape illustration: installation, explicit saving to a named local notebook, and recall in a new assistant chat. The author selected that layout before the context-representation revision; its `v2` variant later updated the TOMC identity. Both remain historical assets. It was produced with the built-in image generation tool; the exact prompts and exploratory phone-layout prompt are in [the generation record](plugin_usage_20261002.prompt.md).

This is a conceptual illustration with a synthetic coding example, not a screenshot or measured plugin outcome. The client icons identify Codex, Cursor and Claude Desktop; they are illustrative marks. Setup differs by client. The browser demo is the secondary context-preparation preview, while the plugin supplies persistent local notebooks.

## Current manuscript figures — 2026-09-28

`paper_method.png` and `paper_beam.svg/png` are byte-for-byte copies of the author-approved method overview and combined BEAM results figure from writing commit `7399657`. Their hashes and source filenames are recorded in `benchmarks/current_paper/manifest.json`. The latter includes pooled long-history comparisons, common-set ability radars and separate compilation-ablation batches. The [result report](../benchmarks/RESULTS.md) explains each aggregation and evaluated configuration.

These figures are refreshed with `scripts/sync_paper.py`, not the synthetic-diagram generator. Provider and method marks appearing in the supplied figures retain their respective ownership and do not imply endorsement. The overview uses the exact supplied PNG rather than its 9 MB SVG. The BEAM SVG has a clickable PNG alternative in both READMEs.

## Original demo diagrams and historical result plots

The earlier demo figures below are original SVG diagrams and a Matplotlib evidence plot. Their labels and layout were informed by an inspection of the official LLMLingua README and figures; no upstream logo, figure, screenshot or model-provider mark is included in these assets.

| Asset | Purpose | Source |
|---|---|---|
| `tomc_mark.svg` | Original mark: indexed state cards connected to source nodes | Code-native vector shapes |
| `project_overview*.svg` | Selected history → task-conditioned records + raw evidence → LLM memory | Paper representation flow, illustrated by selected synthetic STATE rows; scope in `docs/paper_scope.md` |
| `snapshot_semantics*.svg` | Operation order and snapshot dependencies | `src/tomc/data/snapshot.json`, executed by `compile_memory` |
| `agent_ledger*.svg` | Archived software-trace compatibility example; outside the paper method and evaluation | `src/tomc/data/agent.json`, executed by the [legacy adapter](../docs/legacy_extensions.md) at its bundled budget |
| `results_overview.svg` / `.png` | Full-grid effects with uncertainty beside reader input reductions | Frozen `benchmarks/aggregate_results/beam_readers.csv` |
| `figure_data.json` | Exact inputs, source hashes and actual synthetic memory used by the figures | Generated alongside the figures |

`_zh` diagrams use Chinese labels. `_mobile` diagrams stack panels vertically and are selected through README `<picture>` elements; the default remains a regular SVG for renderers without that feature. All figures have an opaque white background and dark text, including when viewed inside GitHub dark mode. Figures carry text alternatives in the README and SVG title/description metadata.

Regenerate with `make project-assets`. Install the optional Playwright/Chromium browser tools and run `python scripts/project_figures.py --render` to export the six desktop explanatory PNGs. Statistical PNG/SVG exports use Matplotlib directly. Run `make reproduce-results` first when validating the frozen data; it independently reconstructs the underlying statistics. The original `beam_readers` figure remains available.

The historical `results_overview` plot uses **full-grid** effects and corresponding bootstrap intervals. The historical result table uses **available-pair** scores. Do not silently swap those estimates or attach one estimand's interval to the other. Flash is marked nonsignificant, missingness-expanded intervals are visible, and task boundaries remain adjacent to the graph.

Earlier `social_preview` assets are the separate 1280×640 launch-card draft; `demo_desktop` / `demo_mobile` are real application screenshots, not architecture figures. No promotional image establishes answer quality on its own.
