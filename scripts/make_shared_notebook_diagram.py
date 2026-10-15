"""Draw the explicit same-machine notebook handoff; no model or remote assets."""

from __future__ import annotations

from copy import deepcopy
from html import escape
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
INK = "#172a27"
PINE = "#1b604a"
LINE = "#d8ded5"


def text(x: int, y: int, value: str, size: int = 22, weight: int = 500) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{INK}">{escape(value)}</text>'
    )


def mark(x: int, y: int, size: int) -> str:
    original = ElementTree.parse(ROOT / "assets/tomc_mark.svg").getroot()
    for item in list(original):
        if item.tag.rsplit("}", 1)[-1] in {"title", "desc", "defs", "style"}:
            original.remove(item)
    original.attrib.clear()
    original.set("x", str(x))
    original.set("y", str(y))
    original.set("width", str(size))
    original.set("height", str(size))
    original.set("viewBox", "0 0 128 128")
    return ElementTree.tostring(deepcopy(original), encoding="unicode")


def terminal(x: int, y: int, color: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="44" height="34" rx="7" fill="white" '
        f'stroke="{color}" stroke-width="2"/>'
        f'<path d="M{x + 11} {y + 11}l6 6-6 6m12 0h9" fill="none" '
        f'stroke="{color}" stroke-width="2.5" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
    )


def draw(chinese: bool, mobile: bool) -> str:
    width, height = (480, 750) if mobile else (1120, 300)
    title = "换个助手，项目接着做" if chinese else "Save. Switch. Continue."
    description = (
        "Codex 保存项目笔记，Claude Code 取回并追加更新，Codex 再读取最新笔记。"
        "两边在同一台电脑打开同一个 TOMC 记忆本，并显式调用存取工具。"
        if chinese
        else "Codex saves project notes; Claude Code recalls and updates them; "
        "Codex reads the latest notes. Both servers open one TOMC notebook on "
        "the same computer, using explicit save and recall calls."
    )
    steps = [
        ("Codex", "保存项目笔记", "决策、约束与下一步")
        if chinese
        else ("Codex", "Save project notes", "Decisions and next steps"),
        ("Claude Code", "取回并追加更新", "继续同一项任务")
        if chinese
        else ("Claude Code", "Recall and update notes", "Continue the same task"),
        ("Codex", "读取最新笔记", "接着上次的进度继续")
        if chinese
        else ("Codex", "Read the latest notes", "Pick up from the update"),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" '
        'refY="4" orient="auto"><path d="M0 0L7 4L0 8" fill="none" '
        f'stroke="{PINE}" stroke-width="1.5"/></marker></defs>',
        "<style>text{font-family:Arial,'Microsoft YaHei','Noto Sans CJK SC',sans-serif}</style>",
        '<rect width="100%" height="100%" rx="18" fill="white"/>',
        text(24, 44, title, 34 if mobile else 36, 700),
    ]
    for index, (client, action, detail) in enumerate(steps):
        x, y, card_width, card_height = (
            (24, 80 + index * 178, 432, 144) if mobile else (24 + index * 370, 76, 332, 136)
        )
        color = "#97651b" if index == 1 else PINE
        fill = "#fff8e9" if index == 1 else "#eef6f0"
        out.extend(
            [
                f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" '
                f'rx="14" fill="{fill}" stroke="{LINE}" stroke-width="1.5"/>',
                f'<circle cx="{x + 28}" cy="{y + 32}" r="15" fill="{color}"/>',
                f'<text x="{x + 28}" y="{y + 39}" text-anchor="middle" font-size="20" '
                f'font-weight="700" fill="white">{index + 1}</text>',
                text(x + 54, y + 41, client, 28, 700),
                terminal(x + card_width - 67, y + 16, color),
                text(x + 24, y + 84, action, 26 if mobile else 24, 600),
                text(x + 24, y + 117, detail, 22, 500),
            ]
        )
        if index < 2:
            if mobile:
                path = f"M240 {y + 155}V{y + 168}"
            else:
                path = f"M{x + card_width + 9} {y + 68}H{x + card_width + 27}"
            out.append(
                f'<path d="{path}" fill="none" stroke="{PINE}" stroke-width="2.5" '
                'marker-end="url(#arrow)"/>'
            )
    footer = 602 if mobile else 234
    out.append(mark(24, footer, 48))
    out.append(
        text(84, footer + 33, "同一个 TOMC 记忆本" if chinese else "One TOMC notebook", 26, 700)
    )
    condition = (
        "同一台电脑 · 共用记忆库 · 显式保存和取回"
        if chinese
        else "Same computer · Shared store · Explicit save / recall"
    )
    if mobile:
        lines = (
            ("同一台电脑 · 共用记忆库", "显式保存和取回")
            if chinese
            else ("Same computer · Shared store", "Explicit save / recall")
        )
        out.extend(text(24, 687 + index * 31, line, 22) for index, line in enumerate(lines))
    else:
        out.append(text(460, 267, condition, 20))
    out.append("</svg>\n")
    return "\n".join(out)


if __name__ == "__main__":
    for chinese in (False, True):
        for mobile in (False, True):
            suffix = ("_zh" if chinese else "") + ("_mobile" if mobile else "")
            destination = ROOT / "assets" / f"shared_notebook_handoff{suffix}.svg"
            destination.write_text(draw(chinese, mobile), encoding="utf-8", newline="\n")
            ElementTree.parse(destination)
    print("Built four native SVG handoff diagrams.")
