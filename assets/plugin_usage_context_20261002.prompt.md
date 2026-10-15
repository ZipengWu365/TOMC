# TOMC context-representation usage illustration — 2026-10-02

Built-in image generation edited the earlier product illustration after a read-only audit of the latest 20-page manuscript PDF (SHA-256 `f336e8e5d730ab116d494e82656c1c1a470900f4a5af419201ee7019a378d1ed`). Section 3.1 defines `Compress(M, q, B)`; Sections 3.2–3.4 explain evidence selection, supported record operations, and records combined with source text. The stateless context compiler is the core; notebooks are one optional plugin history source.

Final file: `plugin_usage_context_20261002.png`; a byte-identical copy in `docs/assets/` supports the documentation build. This is a conceptual use diagram, not a client screenshot or measured performance result. Supported task routes are alternatives; short histories can remain intact. The previous notebook-use diagram remains as a historical asset.

## Prompt

Inputs: `plugin_usage_20261002_v2.png` (layout/style edit target), `tomc_logo_20261002.png` (brand identity reference).

```text
Use case: infographic-diagram.
Asset type: updated landscape GitHub README product-use illustration for TOMC.
Input 1 is the edit target/style/layout reference: the previous three-panel TOMC plugin illustration. Input 2 is the TOMC product logo identity reference. The previous drawing overemphasizes local notebook storage. Rebuild its content to show task-oriented context compression and representation construction, while retaining the same friendly flat illustration, landscape format, white background, three numbered blue/teal/orange outlined panels, restrained small icons, and recognizable Codex/Cursor/Claude Desktop identifiers. Use the new linked-card/return-arrow TOMC mark from input 2.
Title exact: "Task-oriented context compression"
Subtitle exact: "Your history + task + budget. Your existing assistant."
Panel 1 exact title: "1  Connect TOMC". Show the three assistant identifiers and names exactly "Codex", "Cursor", "Claude Desktop", installation box and plug. Bottom text: "Plugins or Python API". This is the main user entry.
Panel 2 exact title: "2  Prepare context". Show three clean input fields labeled "History", "Task", "Token budget" feeding a small TOMC brand mark. Below it show three short operation chips in a clear sequential flow: "Select evidence", "Compile records", "Keep source text". Small footer text: "Supported rule-based operations". Use visual history lines, a task-question icon and budget gauge. Do not show a local database or named notebook. Do not make state/relation/count look like three simultaneously required routes; they are alternative supported operations.
Panel 3 exact title: "3  Use the result". Show a compact plain-text context card containing two separate blue and green areas labeled exactly "Task records" and "Source text", joined by a plus sign. Show an arrow from this context card to the existing assistant chat-window illustration. Footer exact: "Your assistant writes the answer". No synthetic measured scores, no memory-saving percentages, no automatic chat-capture depiction.
Keep the demo as a smaller secondary strip at the bottom. Exact headline "Try the demo", with secondary text "Inspect the context TOMC prepares". Three badges only: "CPU only", "No training", "No auxiliary model". These construction badges apply to TOMC, not answer generation.
Typography: large highly legible headings and compact supporting labels, no microtext. Preserve clean thin rounded outlines and blue/teal/orange palette with pale fills. Opaque white background. No giant storage/notebook story, cloud, fake benchmarking results, lossless guarantee, extra brand names, watermark or technical clutter.
```
