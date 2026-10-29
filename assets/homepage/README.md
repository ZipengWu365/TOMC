# Homepage UI tour

These assets show the desktop companion and context library from this source tree.

| File | Content |
|---|---|
| `cat-work-forms.gif` | Four work forms painted by `tomc.pet_art.PetArt`; example length bands from `tomc.pet_growth.request_stage`. |
| `contexts-en.png`, `contexts-zh.png` | Native context-library widgets with three synthetic example projects. The selected project shows the supported framework / backup-copy operation. |
| `analysis-en.png`, `analysis-zh.png` | The analysis view over those same example preparations. |
| `render-metadata.json` | Example input/output estimates, counter names and rendering scope. |

The UI images carry a demo label. Each example goes through `prepare_context` locally, then enters an isolated temporary database. There are no reader calls or live assistant connections. Dollar displays use a demo input rate of $2 per million tokens. The animation illustrates the four input-length bands, independently of the example preparations.

## Re-render

From an activated environment with the package's `widget` extra and Pillow:

```bash
python scripts/render_homepage_assets.py
```

The script renders application widgets offscreen and writes only the assets above. It uses temporary example data, redirects host discovery to temporary folders, and makes no desktop captures. On Linux, Noto Sans CJK SC is substituted for Microsoft YaHei UI in the preview. No font files are distributed here.

## Directory links checked for this homepage update

Checked on 2026-10-29:

- [MCPRush: TOMC Memory](https://mcprush.com/zipengwu365/tomc-memory-mcp): the public listing names TOMC Memory and links to `ZipengWu365/TOMC`.
- [SpaceRing Harness: TOMC Memory](https://spacering.net/harness/zipengwu365/tomc-memory): the public catalogue contains `zipengwu365/tomc-memory`. Its [read-only API result](https://spacering.net/api/harness/v1/items?q=TOMC) and catalogue page resolve to that entry.

The homepage describes these as directory listings and directs installations to the current repository guides.
