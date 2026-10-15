"""Render README result figures from the existing tables (Python standard library only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import escape
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "results"
PAPER = '<a id="paper-explained"></a>'
COLORS = {"full": "#8893a4", "40": "#277cba", "60": "#83b4d8", "80": "#b5cadb"}


def blob_sha(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def table_for(text: str, prefix: str) -> str:
    front = text.split(PAPER, 1)[0]
    matches = re.findall(r"^" + re.escape(prefix) + r"[^\n]*(?:\n\|[^\n]*)+", front, re.M)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one result table starting with {prefix!r}; found {len(matches)}"
        )
    return matches[0]


def rows(table: str) -> list[list[str]]:
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in table.splitlines()[2:]
    ]


def numbers(codex: str, claude: str) -> dict:
    a, b = rows(codex), rows(claude)
    if len(a) != 4 or any(len(row) != 4 for row in a):
        raise ValueError("Codex must have four rows and four columns")
    if len(b) != 3 or any(len(row) != 4 for row in b):
        raise ValueError("Claude must have three rows and four columns")
    if any(row[3] != "45/45" for row in a):
        raise ValueError("Unexpected Codex answer counts")
    codex_values = [int(row[1].replace(",", "")) for row in a]
    codex_changes = [None] + [float(row[2].rstrip("%")) for row in a[1:]]
    costs, changes = [], []
    for row in b:
        if any("5/5" not in cell for cell in row[1:]):
            raise ValueError("Unexpected Claude answer counts")
        costs.append([float(re.search(r"US\$(\d+\.\d+)", cell)[1]) for cell in row[1:]])
        changes.append([None] + [int(re.search(r"[−-](\d+)%", cell)[1]) for cell in row[2:]])
    expected = (
        [42191, 28713, 33344, 38035],
        [None, 29.7, 19.5, 9.2],
        [[0.169, 0.075, 0.103], [0.334, 0.141, 0.195], [0.628, 0.255, 0.369]],
        [[None, 56, 39], [None, 58, 42], [None, 59, 41]],
    )
    if (codex_values, codex_changes, costs, changes) != expected:
        raise ValueError("Recorded values changed; review the figure scope before updating")
    return {
        "codex_mean_input": codex_values,
        "codex_mean_paired_reduction": codex_changes,
        "claude_cost_usd": costs,
        "claude_reported_cost_reduction": changes,
    }


def start(height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title description">',
        f'<title id="title">{escape(title)}</title><desc id="description">{escape(description)}</desc>',
        '<style>text{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC",Arial,sans-serif;fill:#17212f} .muted{fill:#4d5c6f} .small{font-size:18px}</style>',
        f'<rect x="1" y="1" width="998" height="{height - 2}" rx="16" fill="#ffffff" stroke="#d7dfe8"/>',
    ]


def text(
    parts: list[str],
    x: float,
    y: float,
    value: str,
    size: int = 22,
    weight: int = 400,
    anchor: str = "start",
    cls: str = "",
) -> None:
    parts.append(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" class="{cls}">{escape(value)}</text>'
    )


def rect(parts: list[str], x: float, y: float, width: float, height: float, color: str) -> None:
    parts.append(
        f'<rect x="{x}" y="{y}" width="{width:.3f}" height="{height}" rx="3" fill="{color}"/>'
    )


def codex_svg(data: dict, lang: str) -> str:
    zh = lang == "zh"
    title = "Windows Codex · gpt-6.1-sol"
    p = start(
        540,
        title,
        "Four context budgets; mean total request input 42191, 28713, 33344, 38035. All 45/45 correct. Paired reductions 29.7%, 19.5%, 9.2%.",
    )
    text(p, 38, 46, title, 28, 700)
    text(
        p,
        38,
        78,
        "合成历史中的最新状态问答" if zh else "Latest-state questions on synthetic histories",
        20,
        cls="muted",
    )
    text(p, 962, 46, "45/45", 30, 700, "end")
    text(
        p,
        962,
        77,
        "每种预算均答对" if zh else "correct at every budget",
        18,
        anchor="end",
        cls="muted",
    )
    labels = (
        ["完整历史", "TOMC · 40% 预算", "TOMC · 60% 预算", "TOMC · 默认 80%"]
        if zh
        else ["Full history", "TOMC · 40% budget", "TOMC · 60% budget", "TOMC · default 80%"]
    )
    text(
        p,
        300,
        123,
        "平均请求输入（token）" if zh else "Mean request input (tokens)",
        19,
        cls="muted",
    )
    text(p, 957, 123, "配对减少" if zh else "Paired reduction", 19, anchor="end", cls="muted")
    scale = 450 / 45000
    for i, (label, value, key) in enumerate(
        zip(labels, data["codex_mean_input"], ["full", "40", "60", "80"])
    ):
        y = 172 + i * 64
        text(p, 38, y + 7, label, 20)
        rect(p, 300, y - 17, value * scale, 30, COLORS[key])
        text(p, 810, y + 6, f"{value:,}", 22, 600, "end")
        change = data["codex_mean_paired_reduction"][i]
        text(
            p,
            957,
            y + 6,
            ("参照" if zh else "Reference") if change is None else f"−{change:.1f}%",
            22,
            600,
            "end",
        )
    for value in [0, 10000, 20000, 30000, 40000]:
        x = 300 + value * scale
        text(
            p, x, 414, str(value // 1000) + "K" if value else "0", 17, anchor="middle", cls="muted"
        )
    text(
        p,
        38,
        458,
        "9 份历史（3 个 seed × 10K / 20K / 40K）；每种条件各回答一轮。"
        if zh
        else "9 histories (3 seeds × 10K / 20K / 40K); one answering turn per condition.",
        18,
        cls="muted",
    )
    text(
        p,
        38,
        488,
        "减少比例为各份历史配对比例的均值，与条形长度的比值不同。"
        if zh
        else "Reductions average paired history-level ratios; bars show mean request input.",
        18,
        cls="muted",
    )
    text(
        p,
        38,
        518,
        "输入包含缓存、宿主指令与工具定义；未测试完整编程工作流。"
        if zh
        else "Input includes cache, host instructions and tools. Full coding workflows untested.",
        18,
        cls="muted",
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def claude_svg(data: dict, lang: str) -> str:
    zh = lang == "zh"
    title = "Claude Code · Claude Opus 5.5"
    p = start(
        690,
        title,
        "Answering-request USD costs for 10K, 20K and 40K histories, with full history or 40%/60% retention. Each shown condition answered 5/5 latest-state questions.",
    )
    text(p, 38, 46, title, 28, 700)
    text(
        p,
        38,
        78,
        "合成历史 · 单次回答请求费用（美元）"
        if zh
        else "Synthetic histories · cost per answering request (USD)",
        20,
        cls="muted",
    )
    text(p, 960, 46, "5/5", 30, 700, "end")
    text(
        p,
        960,
        77,
        "每组条件均答对" if zh else "correct in every condition",
        18,
        anchor="end",
        cls="muted",
    )
    text(p, 797, 124, "美元" if zh else "USD", 19, anchor="end", cls="muted")
    text(p, 956, 124, "费用减少" if zh else "Cost reduction", 19, anchor="end", cls="muted")
    labels = (
        ["完整历史", "保留 40%", "保留 60%"] if zh else ["Full history", "Keep 40%", "Keep 60%"]
    )
    scale = 405 / 0.65
    for group, history in enumerate(["10K", "20K", "40K"]):
        y0 = 168 + group * 142
        text(p, 38, y0 + 39, ("约 " if zh else "~") + history, 23, 600)
        text(p, 38, y0 + 66, "token", 18, cls="muted")
        for j, (label, key) in enumerate(zip(labels, ["full", "40", "60"])):
            y = y0 + j * 37
            value = data["claude_cost_usd"][group][j]
            text(p, 155, y + 7, label, 19)
            rect(p, 300, y - 15, value * scale, 26, COLORS[key])
            text(p, 797, y + 6, f"${value:.3f}", 22, 600, "end")
            change = data["claude_reported_cost_reduction"][group][j]
            text(
                p,
                956,
                y + 6,
                ("参照" if zh else "Reference") if change is None else f"−{change}%",
                21,
                600,
                "end",
            )
    for value in [0, 0.2, 0.4, 0.6]:
        text(p, 300 + value * scale, 564, f"${value:.1f}", 17, anchor="middle", cls="muted")
    text(
        p,
        38,
        610,
        "每份历史包含 5 个最新状态问题；所有展示条件均为 5/5。"
        if zh
        else "Five latest-state questions per history; all shown conditions answered 5/5.",
        18,
        cls="muted",
    )
    text(
        p,
        38,
        640,
        "百分比沿用原实验报告的舍入值；这组测试与 Codex 的请求协议不同。"
        if zh
        else "Percentages retain the report's rounding. This protocol differs from the Codex trial.",
        18,
        cls="muted",
    )
    text(
        p,
        38,
        670,
        "仅展示回答请求费用，不代表完整 Agent 会话的账单节省。"
        if zh
        else "Answering-request costs only; no claim of end-to-end agent-session savings.",
        18,
        cls="muted",
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


def rewrite(original: str, lang: str, codex: str, claude: str) -> str:
    front, paper = original.split(PAPER, 1)
    zh = lang == "zh"
    for name, table, target, alt in [
        (
            "codex",
            codex,
            "docs/codex_retention_20261005_zh.md" if zh else "docs/codex_retention_20261005.md",
            "Windows Codex：4 种预算下均为 45/45；平均请求输入及配对减少比例。"
            if zh
            else "Windows Codex: all four budgets score 45/45. Mean request input and paired reductions.",
        ),
        (
            "claude",
            claude,
            "docs/validation.md#claude-code-windows-validation",
            "Claude Code：10K、20K、40K 历史的请求费用；各展示条件均为 5/5。"
            if zh
            else "Claude Code: costs at 10K, 20K and 40K histories; all shown conditions score 5/5.",
        ),
    ]:
        image = f"assets/results/{name}_savings_{lang}.svg"
        if image not in front:
            caption = "查看可复制的原始数值" if zh else "Exact values (copyable text)"
            replacement = f"[![{alt}]({image})]({target})\n\n<details>\n<summary>{caption}</summary>\n\n{table}\n\n</details>"
            if front.count(table) != 1:
                raise ValueError("Result table is ambiguous")
            front = front.replace(table, replacement, 1)
    # Edit the new onboarding prose; leave code, numerical tables and paper text alone.
    if zh:
        front = re.sub(
            r"^\*\*视频演示的流程：\*\*.*$",
            "API 接入方在请求前调用 TOMC，发送准备好的上下文。Codex 和 Claude Code 通过工具保存或召回任务笔记。视频中的模型名单包含有记录的测试和作者报告的试用，未做统一的多模型评测，也没有模型提供商背书。",
            front,
            flags=re.M,
        )
        front = re.sub(
            r"^\*\*可核验的实验数字：\*\*.*$",
            "[实测结果](#实测节省)保留了 Codex、Claude Code 各自的实验条件和原始记录。",
            front,
            flags=re.M,
        )
        front = front.replace("**立即试用：** ", "")
        front = front.replace("#### 首次试用：按你的使用场景选择入口", "#### 首次试用")
        front = front.replace(
            "这里验证的是**显式保存与召回**，不会自动记录当前聊天的全部历史。",
            "笔记需要主动保存和召回，插件不会自动记录全部聊天。",
        )
        front = front.replace("**答案一样，请求更小。** 我们用", "我们用")
        front = front.replace(
            "答案与完整历史完全一致，请求费用降低一半以上：",
            "这 5 个问题的答案与完整历史一致。费用如下：",
        )
        front = front.replace(
            "这里的 `history`、`task`、`client` 和 `model` 来自你已有的应用。",
            "`history`、`task`、`client` 和 `model` 来自你已有的应用。",
        )
    else:
        front = re.sub(
            r"^\*\*What the demo illustrates:\*\*.*$",
            "API integrations call TOMC before the next request and send the prepared context. Codex and Claude Code use tools to save or recall task notes. The video includes recorded tests and author-reported trials; it has no uniform multi-model benchmark or provider endorsement.",
            front,
            flags=re.M,
        )
        front = re.sub(
            r"^\*\*Results you can audit:\*\*.*$",
            "The [measured results](#measured-savings) give the Codex and Claude Code protocols and their source records.",
            front,
            flags=re.M,
        )
        front = front.replace("**Try it:** ", "")
        front = front.replace(
            "#### First run — choose the path that fits your workflow", "#### First run"
        )
        front = front.replace(
            "This tests **explicit** save/recall, not automatic recording of active chats.",
            "Save and recall are explicit tool calls. The plugin does not record the whole chat automatically.",
        )
        front = front.replace("**Same answers, smaller requests.** On synthetic", "On synthetic")
        front = front.replace(
            "every answer matched the full history and the request cost fell by more than half:",
            "all five answers matched the full-history condition. The answering-request costs were:",
        )
    updated = front + PAPER + paper
    if original.split("</div>", 1)[0] != updated.split("</div>", 1)[0]:
        raise ValueError("Star header changed")
    if updated.split(PAPER, 1)[1] != paper:
        raise ValueError("Paper section changed")
    if re.findall(r"```.*?```", original, re.S) != re.findall(r"```.*?```", updated, re.S):
        raise ValueError("Code block changed")
    for table in (codex, claude):
        if updated.count(table) != 1:
            raise ValueError("Copyable data was lost or duplicated")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="check generated files without writing"
    )
    parser.add_argument(
        "--update-readmes", action="store_true", help="embed figures and edit onboarding prose"
    )
    args = parser.parse_args()
    source, tables, data = {}, {}, {}
    for lang, filename, a, b in [
        ("en", "README.md", "| Context sent |", "| History |"),
        ("zh", "README_zh.md", "| 发送的上下文 |", "| 历史长度 |"),
    ]:
        value = (ROOT / filename).read_text(encoding="utf-8")
        if value.count(PAPER) != 1:
            raise ValueError(f"Paper marker missing or duplicated: {filename}")
        source[lang] = (filename, value)
        tables[lang] = (table_for(value, a), table_for(value, b))
        data[lang] = numbers(*tables[lang])
    if data["en"] != data["zh"]:
        raise ValueError("English and Chinese figures disagree")
    outputs = {}
    for lang in ("en", "zh"):
        outputs[OUT / f"codex_savings_{lang}.svg"] = codex_svg(data[lang], lang)
        outputs[OUT / f"claude_savings_{lang}.svg"] = claude_svg(data[lang], lang)
    for value in outputs.values():
        ElementTree.fromstring(value)
        if "<script" in value or "<foreignObject" in value:
            raise ValueError("Unsafe SVG")
    outputs[OUT / "data.json"] = (
        json.dumps(
            {
                "source": "README measured-savings tables; original protocols linked in each README",
                **data["en"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    report = {}
    for lang, (filename, original) in source.items():
        modified = rewrite(original, lang, *tables[lang])
        if args.update_readmes:
            outputs[ROOT / filename] = modified
        report[filename] = {
            "source_blob": blob_sha(original),
            "result_blob": blob_sha(modified),
            "star_header_unchanged": True,
            "paper_section_unchanged": True,
            "code_blocks_unchanged": True,
            "copyable_tables_preserved": True,
        }
    for path, value in outputs.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != value:
                raise ValueError(f"Stale generated file: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
    print(json.dumps({"files": len(outputs), "checks": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
