"""Build the launch brief and original SVG; optionally render its PNG with Playwright."""

from __future__ import annotations

import argparse
import json
import re
from html import escape
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]


def build_assets(render: bool = False) -> None:
    """Use the bundled operations and actual ledger, never invented demo results."""
    from tomc import compile_memory

    sample = json.loads((ROOT / "src/tomc/data/snapshot.json").read_text())
    result = compile_memory(
        sample["messages"], sample["query"], sample["budget"], sample["strategy"]
    )
    left = []
    for i, message in enumerate(sample["messages"]):
        y = 260 + i * 77
        left.append(f'<text x="80" y="{y}" class="micro">0{i + 1} / UPDATE</text>')
        for j, line in enumerate(message["content"].splitlines()):
            left.append(f'<text x="80" y="{y + 23 + j * 21}" class="code">{escape(line)}</text>')
    right = []
    for i, row in enumerate(result.ledger):
        y = 249 + i * 82
        right.append(
            f'<rect x="650" y="{y}" width="548" height="72" rx="6" fill="#edf2ea"/>'
            f'<text x="668" y="{y + 26}" class="code">{escape(row.key)}</text>'
            f'<text x="1178" y="{y + 26}" text-anchor="end" class="value">{escape(row.value)}</text>'
            f'<text x="668" y="{y + 52}" class="micro">SOURCE {escape(", ".join(row.sources))}</text>'
        )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" role="img" aria-labelledby="title desc">
<title id="title">TOMC: LLM memory. State you can trace.</title>
<desc id="desc">A synthetic snapshot copy keeps tea after drink changes to decaf tea. Real compiler output with provenance; metadata expands this tiny input.</desc>
<style>text {{ font-family: Arial, sans-serif; fill: #172a27; }} .micro {{ font-size: 12px; letter-spacing: 1px; fill: #506558; }} .code {{ font: 17px monospace; }} .value {{ font-size: 21px; font-weight: bold; fill: #1b604a; }}</style>
<rect width="1280" height="640" fill="#f5f4ed"/>
<path d="M56 52H1224" stroke="#c6d4c7"/>
<text x="56" y="38" font-size="24" font-weight="bold">TOMC</text>
<text x="1224" y="36" text-anchor="end" class="micro">CPU ONLY / NO MODEL / NO API KEY</text>
<text x="56" y="112" font-size="46" font-weight="bold" letter-spacing="-2">LLM memory. State you can trace.</text>
<text x="56" y="150" font-size="19">Compile memory for the task. This state example keeps update and snapshot evidence.</text>
<text x="56" y="204" class="micro">01 / HISTORY</text>
<text x="626" y="204" class="micro">02 / COMPILED MEMORY</text>
<rect x="56" y="220" width="508" height="300" rx="8" fill="#fffef9" stroke="#c6d4c7"/>
<rect x="626" y="220" width="598" height="300" rx="8" fill="#fffef9" stroke="#c6d4c7"/>
{"".join(left)}{"".join(right)}
<text x="588" y="380" font-size="30" text-anchor="middle" fill="#1b604a">→</text>
<text x="56" y="558" font-size="15">A copy preserves the value at that moment. Open a state row in the demo to inspect its sources.</text>
<text x="56" y="587" font-size="12" fill="#506558">Synthetic normalized operations · {result.stats.input_tokens} → {result.stats.output_tokens} estimated tokens · provenance adds overhead on this tiny input.</text>
<text x="56" y="618" class="micro">github.com/ZipengWu365/TOMC</text>
</svg>"""
    (ROOT / "assets/social_preview.svg").write_text(svg)

    build_brief()
    if render:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 640}, device_scale_factor=1)
            page.goto((ROOT / "assets/social_preview.svg").as_uri())
            page.screenshot(path=str(ROOT / "assets/social_preview.png"))
            page.goto((ROOT / "launch/brief.html").as_uri())
            assert page.locator("section").count() == 4
            assert page.locator("#competitors").inner_text().find("LLMLingua") >= 0
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth") == width
            browser.close()
        assert (ROOT / "assets/social_preview.png").stat().st_size < 1_000_000
    print("Built launch brief and share card from the bundled snapshot example.")


def build_brief() -> None:
    """Refresh the launch prose without changing the share card or scientific figures."""
    plan = (ROOT / "launch/PLAN_ZH.md").read_text(encoding="utf-8")
    updated = re.search(r"更新：(\d{4}-\d{2}-\d{2})", plan)
    date_label = updated.group(1) if updated else "更新日期见计划"
    chunks = re.split(r"(?=^## )", plan, flags=re.MULTILINE)
    groups = [
        ("overview", "首页说明", "".join(chunks[:2])),
        ("competitors", "相关项目", chunks[2]),
        ("guidance", "接入、结果与发布", "".join(chunks[3:-1])),
        ("sources", "来源与后续事项", chunks[-1]),
    ]
    nav = "".join(f'<a href="#{key}">{label}</a>' for key, label, _ in groups)
    sections = "".join(
        f'<section id="{key}">{markdown.markdown(body, extensions=["tables", "fenced_code"])}</section>'
        for key, _, body in groups
    )
    report = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TOMC · Demo 说明与发布草稿</title><style>
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f5f4ed;color:#172a27;font:16px/1.85 system-ui,sans-serif}}
header,main{{max-width:1120px;margin:auto;padding:28px}}header{{border-bottom:1px solid #c6d4c7}}header p{{margin:0;color:#506558;font-size:13px}}nav{{display:flex;flex-wrap:wrap;gap:10px 24px;margin-top:14px}}
a{{color:#1b604a;text-underline-offset:3px}}h1{{font-size:32px;line-height:1.3}}h2{{font-size:23px;margin-top:32px}}section{{scroll-margin-top:20px;padding-bottom:16px}}table{{display:block;max-width:100%;overflow:auto;border-collapse:collapse;font-size:14px;margin:20px 0}}th,td{{border:1px solid #c6d4c7;padding:12px;min-width:135px;vertical-align:top}}th{{background:#e4ece0;text-align:left}}code{{background:#e4ece0;padding:2px 4px;overflow-wrap:anywhere}}pre{{white-space:pre-wrap}}li{{margin:8px 0}}footer{{max-width:1120px;margin:auto;padding:28px;border-top:1px solid #c6d4c7;font-size:13px}}
@media(max-width:600px){{header,main,footer{{padding:18px}}h1{{font-size:26px}}body{{font-size:15px}}}}@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}
</style><header><b>TOMC / LAUNCH DRAFTS</b><p>{date_label} · 私有准备 · 帖子尚未发布</p><nav>{nav}</nav></header><main>{sections}</main><footer>素材：<a href="CONTENT_KIT.md">中英文发布草稿</a> · <a href="RELEASE_CHECKLIST.md">发布清单</a> · <a href="PILOT_ZH.md">私测任务卡</a>。尚未发送推广内容。</footer></html>"""
    (ROOT / "launch/brief.html").write_text(report, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Use optional Playwright for PNG")
    parser.add_argument("--brief-only", action="store_true", help="Refresh HTML prose only")
    args = parser.parse_args()
    if args.brief_only:
        build_brief()
        print("Built launch brief; image assets unchanged.")
    else:
        build_assets(args.render)
