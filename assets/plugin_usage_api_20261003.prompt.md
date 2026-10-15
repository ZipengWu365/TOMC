# TOMC API-input usage illustration with Claude Code — 2026-10-03

Final asset: `plugin_usage_api_20261003.png`, with a byte-identical documentation copy in `docs/assets/`.

It is `plugin_usage_api_20261002.png` with one added line, "& Claude Code", centred under the "Claude Desktop" label in panel 1. Claude Desktop and Claude Code share the Claude identifier, so no fourth client tile was added. No image-generation model was used for this edit: `plugin_usage_api_20261003_edit.py` draws the line with Pillow in Segoe UI (regular, navy `#182248`) and only pixels inside the box (352, 466)–(499, 482) differ from the source. Everything else, including the conceptual-workflow caveats in [`plugin_usage_api_20261002.prompt.md`](plugin_usage_api_20261002.prompt.md), is unchanged.

```bash
python assets/plugin_usage_api_20261003_edit.py assets/plugin_usage_api_20261002.png assets/plugin_usage_api_20261003.png
```
