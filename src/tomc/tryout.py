"""A first run on a bundled synthetic sample: real numbers, nothing saved.

`tomc try`, the MCP tool `try_tomc` and the MCP prompt `quickstart` all use this. The
sample is prepared in memory only: no notebook, context snapshot or usage statistic is
written, so trying TOMC Memory leaves no trace on the computer.
"""

from __future__ import annotations

import json
import os
import re
import time
from importlib.resources import files

from .easy import prepare_context

LANGUAGES = ("en", "zh")
_STATE = re.compile(r"^\[STATE(\??)\] (\S+) = (.+?)\s+<src:([^>]+)>$")
# A doubtful record ends its value with "(later: u140)": the line that may have changed it.
_LATER = re.compile(r"\s*\(later: (u\d+)\)$")

_TEXT = {
    "en": {
        "heading": "TOMC Memory trial · {title}",
        "numbers": "Original {before:,} tokens → prepared {after:,} tokens   {change}   {time}, CPU only",
        "estimate": " (token counts are estimates{budget})",
        "budget": "; budget {budget:,}",
        "seconds": "{seconds:.2f} s",
        "under": "under 0.01 s",
        "question": "Q: {question}",
        "found": "Found: ",
        "indent": "       ",
        "line": "line {lines}",
        "lines": "lines {lines}",
        "join": ", ",
        "copied": " (value when copied)",
        "later": " (line {line:,} may have changed it; that line is included)",
        "nothing": "Found: no typed records; the prepared memory keeps the matching source lines.",
        "next": (
            'Next: ① paste your own long log and say "prepare this with TOMC Memory"  '
            '② say "remember this project with TOMC Memory"; in a new chat say '
            '"continue where we left off"'
        ),
        "saved": "Nothing was saved: the sample was prepared in memory only.",
        "summary": "TOMC Memory trial: {before:,} → {after:,} estimated tokens ({change}) on a built-in sample; nothing saved.",
    },
    "zh": {
        "heading": "TOMC Memory 试跑 · {title}",
        "numbers": "原始 {before:,} token → 准备后 {after:,} token   {change}   {time}，仅 CPU",
        "estimate": "（token 数为估算{budget}）",
        "budget": "，预算 {budget:,}",
        "seconds": "{seconds:.2f} 秒",
        "under": "不到 0.01 秒",
        "question": "问：{question}",
        "found": "找到：",
        "indent": "      ",
        "line": "第 {lines} 行",
        "lines": "第 {lines} 行",
        "join": "、",
        "copied": "（复制时的值）",
        "later": "（第 {line:,} 行可能改过，已附上原句）",
        "nothing": "找到：没有结构化记录；准备后的内容保留了相关原文行。",
        "next": (
            '下一步：①贴你自己的长日志，说"用 TOMC Memory 准备"  '
            '②说"用 TOMC Memory 记住这个项目"，新聊天说"接着上次"'
        ),
        "saved": "本次没有保存任何内容：样例只在内存里处理。",
        "summary": "TOMC Memory 试跑：内置样例 {before:,} → {after:,} token（估算，{change}），未保存任何内容。",
    },
}


def normalize_language(language: str | None) -> str:
    """'zh', 'zh-CN', '中文' and similar mean Chinese; anything else English."""
    value = (language or "").strip().lower()
    return "zh" if value.startswith(("zh", "cn", "chinese", "中")) else "en"


def system_language() -> str:
    """Chinese when the terminal locale is Chinese; English otherwise."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name)
        if value:
            return normalize_language(value)
    return "en"


def load_sample(language: str = "en") -> dict:
    """The bundled synthetic sample, installed with the package as data."""
    language = normalize_language(language)
    source = files("tomc").joinpath(f"data/try_sample_{language}.json")
    return json.loads(source.read_text(encoding="utf-8"))


def _line_number(source: str, lines: list[str]) -> int | None:
    """The 1-based sample line of a source id such as ``u24``."""
    source = source.strip()
    if source.startswith("u") and source[1:].isdigit() and int(source[1:]) < len(lines):
        return int(source[1:]) + 1
    return None


def _found(
    memory: str, lines: list[str], question: str
) -> list[tuple[str, str, list[int], bool, int | None]]:
    """Typed state records in the prepared memory, with 1-based line numbers in the sample.

    A doubtful record (``STATE?``) is kept with the line that may have changed it.
    """
    found = []
    for row in memory.splitlines():
        match = _STATE.match(row.strip())
        if not match:
            continue
        doubtful, key, value, sources = match.groups()
        later = _LATER.search(value) if doubtful else None
        if later:
            value = value[: later.start()]
        numbers = [n for n in (_line_number(s, lines) for s in sources.split(",")) if n]
        copied = any(
            re.match(rf"^\s*{re.escape(key)}\s+(?:copies|copy|takes)\s", lines[n - 1])
            for n in numbers
        )
        found.append(
            (key, value, numbers, copied, _line_number(later[1], lines) if later else None)
        )
    # Follow the order of the question, then anything it did not name.
    position = {key: question.find(key) for key, *_ in found}
    found.sort(key=lambda item: (position[item[0]] < 0, position[item[0]], item[0]))
    return found


def run_sample(language: str | None = "en") -> dict:
    """Prepare the bundled sample and describe the result in a short card."""
    language = normalize_language(language)
    text = _TEXT[language]
    sample = load_sample(language)
    lines = sample["lines"]
    history = "\n".join(lines)
    started = time.perf_counter()
    prepared = prepare_context(history, sample["question"], sample.get("budget"))
    seconds = time.perf_counter() - started
    stats = prepared.compilation.stats
    before, after = stats.input_tokens, stats.output_tokens
    percent = round(100 * (before - after) / before) if before else 0
    change = f"↓{percent}%" if percent >= 0 else f"↑{-percent}%"
    elapsed = text["under"] if seconds < 0.01 else text["seconds"].format(seconds=seconds)
    budget = sample.get("budget")
    found = _found(prepared.compilation.compiled_memory, lines, sample["question"])

    card = [
        text["heading"].format(title=sample["title"]),
        text["numbers"].format(before=before, after=after, change=change, time=elapsed)
        + text["estimate"].format(budget=text["budget"].format(budget=budget) if budget else ""),
        text["question"].format(question=sample["question"]),
    ]
    if not found:
        card.append(text["nothing"])
    for index, (key, value, numbers, copied, later) in enumerate(found):
        where = text["line" if len(numbers) == 1 else "lines"].format(
            lines=text["join"].join(f"{n:,}" for n in numbers)
        )
        prefix = text["found"] if index == 0 else text["indent"]
        note = (text["copied"] if copied else "") + (
            text["later"].format(line=later) if later else ""
        )
        card.append(
            f"{prefix}{key} = {value} ← {where}{note}"
            if numbers
            else f"{prefix}{key} = {value}{note}"
        )
    card += [text["next"], text["saved"]]
    return {
        "summary": text["summary"].format(before=before, after=after, change=change),
        "card": "\n".join(card),
        "show_to_user": "Show the card to the user as it is, then offer the two next steps.",
        "saved": False,
        "details": {
            "language": language,
            "sample": sample["title"],
            "sample_lines": len(lines),
            "question": sample["question"],
            "budget": budget,
            "input_estimated_tokens": before,
            "memory_estimated_tokens": after,
            "reduction_percent": percent,
            "seconds": round(seconds, 4),
            "counter": stats.tokenizer,
            "found": [
                {
                    "key": key,
                    "value": value,
                    "lines": numbers,
                    "copied": copied,
                    "may_have_changed_at_line": later,
                }
                for key, value, numbers, copied, later in found
            ],
            "memory": prepared.compilation.compiled_memory,
            "note": "Synthetic sample prepared in memory; no notebook, context or statistic "
            "was written. Token counts are lexical estimates, not billed tokens.",
        },
    }
