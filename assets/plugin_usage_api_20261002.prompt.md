# TOMC API-input usage illustration — 2026-10-02

Mode: built-in image generation, editing the previous context-representation illustration. The new landscape image leads with preparing compact context before the next model request. It keeps the TOMC identity and assistant-plugin entry, with Python API integration alongside it.

Final asset: `plugin_usage_api_20261002.png`, with a byte-identical documentation copy. This is a conceptual workflow, not a client screenshot, benchmark result or billing claim. Savings depend on the history, task and retained content. The application sends prepared context in place of the original history for the next request; installing an MCP tool does not erase an existing host conversation.

The method remains grounded in the final 20-page manuscript, SHA-256 `f336e8e5d730ab116d494e82656c1c1a470900f4a5af419201ee7019a378d1ed`, Section 3.1's `Compress(M, q, B)` and Sections 3.2–3.4's records plus selected source text.

## Exact prompt

Input: `plugin_usage_context_20261002.png` (edit target and identity/style reference).

```text
Use case: infographic-diagram.
Asset type: updated landscape GitHub README product-use illustration for TOMC.
Input 1 is the edit target: the previous TOMC context-representation product diagram. Preserve its clean friendly flat illustration, linked-card TOMC mark and wordmark, Codex/Cursor/Claude Desktop identifiers, three numbered blue/teal/orange outlined panels, white background, readable large headings, restrained small icons and horizontal layout. This revision emphasizes reducing the context sent in the NEXT LLM API request through task-oriented context preparation; do not depict automatic interception or deletion of an existing chat.
Replace title with exact: "Send less context to your LLM API"
Subtitle exact: "Prepare task records + source text before the next request."
Panel 1 exact title: "1  Connect TOMC". Keep the three client names and illustrated identifiers exactly "Codex", "Cursor", "Claude Desktop", installation box and plug. Footer exact: "Assistant plugins or Python API".
Panel 2 exact title: "2  Prepare context". Keep three inputs labeled "History", "Task", "Token budget" feeding the TOMC compiler. Keep operation chips exact "Select evidence", "Compile records", "Keep source text". Small footer exact: "Supported rule-based operations".
Panel 3 exact title: "3  Send the context". Show a compact request context card titled exact "Next model request", with two clearly separate areas exact "Task records" and "Source text" joined by plus sign. Arrow from this card into a simple API-window icon labeled exact "Your LLM API". Small footer exact: "Use the model you already have". The arrow means the application sends prepared context in place of its original history for that next request; do not depict appending context to an unchanged long history. No cloud storage or notebook.
Bottom secondary strip: exact headline "Try the demo"; subtitle exact "Inspect input before and after". Three badges exact "CPU only", "No training", "No auxiliary model". These apply to TOMC context preparation. Small readable note "Savings depend on your history and task".
No numeric savings, performance scores, model logos beyond the three client identifiers, lossless guarantees, automatic-capture claims, price claims, watermark or microtext. Maintain the existing logo identity. Conceptual workflow illustration, not a client screenshot or measured benchmark. Opaque white background.
```
