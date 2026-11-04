"""The "this week" share card: numbers and wording only, no Qt.

Everything comes from the local statistics database and stays on this computer.
The card shows work types, never conversation names, folders, prompts or IDs.

Honesty rules the wording follows (and the tests check):

- every token, money and percentage figure carries "≈" or "估算 / estimate";
- the footer always says the figures are context estimates, not a bill or a quota
  saving, and names the token counting method; when money is shown, it also names
  the price it was worked out from;
- money that cannot be priced is hidden, never shown as $0;
- figures from different counting methods (TOMC tool calls, the Windows gateway
  beta) are listed separately and never added up;
- a week with no saving says so; fewer than ``MIN_SAMPLES`` usable records gives
  no percentage;
- demo or test data always gets a watermark;
- savings are never converted into water, electricity or trees.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .categories import label as category_label

MIN_SAMPLES = 5
DAYS = 7
REPOSITORY = "github.com/ZipengWu365/TOMC"
GATEWAY_MARKERS = ("request-json", "entire-payload")
DEMO_MARKERS = ("demo", "test", "fixture", "sample", "synthetic", "fake")
_UNSET = object()

TEXT = {
    "zh": {
        "title": "TOMC Memory 本周战报",
        "lead_saved": "本周少发了 ≈",
        "unit": "tokens",
        "estimate": "估算",
        "share": "约占原本要发送内容的 {share}（估算）",
        "few": "样本太少：本周只有 {n} 次可用记录，先不算比例",
        "none_head": "本周没省到",
        "none_sub": "短对话本来就不需要压缩",
        "grew_sub": "上下文增加 ≈ {tokens} tokens（估算）",
        "empty_head": "本周还没有记录",
        "empty_sub": "让助手用上 TOMC Memory，过几天再来看",
        "money": "按标价估算 ≈ {money}",
        "money_note": "按{kind}标价折算 · 不是账单 · 有缓存或订阅时实际更少",
        "kind_input": "未缓存输入",
        "kind_cached": "缓存读取",
        "unpriced": "另有 ≈ {tokens} tokens 找不到标价，没算进金额",
        "chart": "近 7 天每天少发的 tokens（估算）",
        "today": "今天",
        "chart_empty": "这 7 天还没有少发的记录",
        "cell_runs": "整理次数",
        "runs": "{n} 次",
        "cell_cover": "压缩覆盖",
        "cover_requests": "{total} 个请求里压缩了 {done} 个",
        "cover_runs": "{total} 次整理里 {done} 次变短",
        "cell_top": "最省的工作类型",
        "cell_average": "平均每次少发",
        "average": "≈ {tokens} tokens",
        "top_share": "{label} ≈ {share}",
        "none": "暂无",
        "source_mcp": "只统计 TOMC 工具调用",
        "source_gateway": "数据来自 Windows 网关测试版",
        "source_also": "另：{label} ≈ {tokens} tokens，口径不同，不相加",
        "label_mcp": "TOMC 工具调用",
        "label_gateway": "Windows 网关测试版",
        "fixed": "上下文估算，不等于账单或额度节省",
        "basis": "按 {model} 标价估算",
        "basis_many": "按各请求所用模型标价估算（{model} 等 {n} 个）",
        "counter": "token 数为本机文本估算（{counter}）",
        "footer": "TOMC Memory v{version} · 开源 MIT · 本机 CPU 估算，未上传任何内容",
        "made": "生成于 {date}",
        "watermark": "演示数据 · DEMO DATA",
        "summary_saved": "TOMC Memory 本周战报 {range}：少发了 ≈ {tokens} tokens（估算）",
        "summary_share": "，约占 {share}",
        "summary_money": "，按标价估算 ≈ {money}",
        "summary_none": "TOMC Memory 本周战报 {range}：{head}",
        "summary_demo": "（演示数据）",
        "filename": "TOMC-本周战报-{date}.png",
    },
    "en": {
        "title": "TOMC Memory · this week",
        "lead_saved": "Sent fewer tokens this week ≈",
        "unit": "tokens",
        "estimate": "estimate",
        "share": "≈ {share} of what would have been sent (estimate)",
        "few": "Too few samples: {n} usable this week, so no percentage",
        "none_head": "Nothing saved this week",
        "none_sub": "Short chats don't need compressing",
        "grew_sub": "Context grew by ≈ {tokens} tokens (estimate)",
        "empty_head": "No records this week",
        "empty_sub": "Use TOMC Memory with your assistant, then check back",
        "money": "≈ {money} at list price (estimate)",
        "money_note": "At {kind} list price · not a bill · less with caching or a subscription",
        "kind_input": "uncached input",
        "kind_cached": "cache-read",
        "unpriced": "≈ {tokens} more tokens have no listed price and are left out",
        "chart": "Fewer tokens sent per day, last 7 days (estimate)",
        "today": "Today",
        "chart_empty": "No days with fewer tokens sent yet",
        "cell_runs": "Preparations",
        "runs": "{n}",
        "cell_cover": "Coverage",
        "cover_requests": "{done} of {total} requests compressed",
        "cover_runs": "{done} of {total} got shorter",
        "cell_top": "Top work type",
        "cell_average": "Average per preparation",
        "average": "≈ {tokens} fewer tokens",
        "top_share": "{label} ≈ {share}",
        "none": "Not enough data",
        "source_mcp": "Counts TOMC tool calls only",
        "source_gateway": "From the Windows gateway (beta)",
        "source_also": "Also: {label} ≈ {tokens} tokens, counted differently, not added",
        "label_mcp": "TOMC tool calls",
        "label_gateway": "Windows gateway (beta)",
        "fixed": "Context estimate, not a bill or quota saving",
        "basis": "Priced at {model} list price",
        "basis_many": "Priced at each request's model ({model} and {n} more)",
        "counter": "Tokens are a local text estimate ({counter})",
        "footer": "TOMC Memory v{version} · MIT · estimated on this CPU, nothing uploaded",
        "made": "Made {date}",
        "watermark": "演示数据 · DEMO DATA",
        "summary_saved": "TOMC Memory, week of {range}: ≈ {tokens} fewer tokens sent (estimate)",
        "summary_share": ", ≈ {share}",
        "summary_money": ", ≈ {money} at list price",
        "summary_none": "TOMC Memory, week of {range}: {head}",
        "summary_demo": " (demo data)",
        "filename": "TOMC-weekly-report-{date}.png",
    },
}


def _language(language):
    return "en" if getattr(language, "code", language) == "en" else "zh"


def tokens_text(value):
    """1234 -> 1.2K, 1234567 -> 1.23M; always a magnitude, the sign is in the words."""
    value = abs(int(value))
    if value < 1000:
        return f"{value}"
    if value < 100_000:
        return f"{value / 1000:.1f}K".replace(".0K", "K")
    if value < 1_000_000:
        return f"{value / 1000:.0f}K"
    if value < 1_000_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value / 1_000_000_000:.2f}B"


def percent_text(share):
    percent = 100 * share
    return "<1%" if 0 < percent < 1 else f"{percent:.0f}%"


def money_text(value):
    if value < 0.01:
        return "<$0.01"
    return f"${value:,.2f}"


def source_of(counter):
    """The gateway counts the whole request JSON; TOMC tools count the context text."""
    lowered = str(counter or "").lower()
    return "gateway" if any(marker in lowered for marker in GATEWAY_MARKERS) else "mcp"


def _counter_name(counter):
    return str(counter or "").replace(" (estimate)", "").strip() or "regex-v1"


def _tables(db):
    return {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _new_source(name, days):
    return {
        "source": name,
        "calls": 0,
        "usable": 0,
        "increased": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tokens_saved": 0,
        "counters": set(),
        "events": 0,
        "shorter": 0,
        "daily": dict.fromkeys(days, 0),
        "groups": {},
    }


def _week(path, days, catalog, reference, detected):
    """Per-source numbers for these days; sources are never pooled."""
    from .savings import _pricer

    sources = {}
    path = Path(path)
    if not path.exists():
        return sources
    start, end = days[0], days[-1]
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    ) as db:
        db.execute("BEGIN")
        tables = _tables(db)
        daily = (
            db.execute(
                "SELECT day,counter,calls,usable_calls,increased_calls,input_tokens,memory_tokens "
                "FROM context_usage_daily WHERE day>=? AND day<=?",
                (start, end),
            ).fetchall()
            if "context_usage_daily" in tables
            else []
        )
        events = []
        if "context_usage_events" in tables:
            joined = "tomc_request_activity" in tables
            activity_columns = (
                {row[1] for row in db.execute("PRAGMA table_info(tomc_request_activity)")}
                if joined
                else set()
            )
            host = "a.host" if joined else "NULL"
            model = "a.model" if "model" in activity_columns else "NULL"
            join = (
                " LEFT JOIN tomc_request_activity a ON a.request_id=e.request_id" if joined else ""
            )
            events = db.execute(
                f"SELECT substr(e.recorded_at,1,10),e.counter,e.input_tokens,e.memory_tokens,"
                f"{host},{model} FROM context_usage_events e{join} WHERE e.usable=1 "
                "AND substr(e.recorded_at,1,10)>=? AND substr(e.recorded_at,1,10)<=?",
                (start, end),
            ).fetchall()
    mode = (reference or {}).get("mode")
    reference_price, price = _pricer(
        catalog, reference, detected, mode if mode in ("input", "cached") else "input"
    )

    def add(source, tokens, priced):
        key = priced["model"] if priced else None
        group = source["groups"].setdefault(
            key, {"label": priced["label"] if priced else None, "tokens": 0, "money": 0.0}
        )
        group["tokens"] += tokens
        if priced:
            group["money"] += tokens * priced["rate"] / 1_000_000

    for day, counter, calls, usable, increased, before, after in daily:
        source = sources.setdefault(source_of(counter), _new_source(source_of(counter), days))
        source["calls"] += calls
        source["usable"] += usable
        source["increased"] += increased
        source["input_tokens"] += before
        source["output_tokens"] += after
        source["counters"].add(_counter_name(counter))
        if day in source["daily"]:
            source["daily"][day] += before - after
    seen = {}
    for day, counter, before, after, host, model in events:
        name = source_of(counter)
        source = sources.setdefault(name, _new_source(name, days))
        saved = before - after
        source["events"] += 1
        source["shorter"] += saved > 0
        seen[(name, day)] = seen.get((name, day), 0) + saved
        add(source, saved, price(model, host, before)[0])
    # Daily totals written before per-request events existed are valued at the reference.
    for name, source in sources.items():
        for day, saved in source["daily"].items():
            missing = saved - seen.get((name, day), 0)
            if missing > 0:
                add(source, missing, reference_price)
        source["tokens_saved"] = source["input_tokens"] - source["output_tokens"]
    return sources


def _money(source, mode):
    """Money for one source; None when nothing in it has a listed price."""
    positive = {key: group for key, group in source["groups"].items() if group["tokens"] > 0}
    priced = {key: group for key, group in positive.items() if key is not None}
    if not priced:
        return None
    labels = [group["label"] for group in sorted(priced.values(), key=lambda g: -g["tokens"])]
    return {
        "value": sum(group["money"] for group in priced.values()),
        "models": labels,
        "mode": mode,
        "unpriced_tokens": positive.get(None, {}).get("tokens", 0),
    }


def _analysis(path, now, catalog, reference, detected):
    """Coverage and the top work type; conversation names never leave this function."""
    from .analysis import analysis_report

    try:
        report = analysis_report(
            path, "7d", now=now, catalog=catalog, reference=reference, detected=detected
        )
    except (OSError, sqlite3.Error, ValueError):
        return None, None
    totals = report["totals"]
    coverage = None
    if totals["requests"]:
        coverage = {
            "kind": "requests",
            "total": totals["requests"],
            "done": round((totals["compressed_share"] or 0) * totals["requests"]),
        }
    positive = [row for row in report["categories"] if row["tokens_saved"] > 0]
    top = None
    if positive:
        total = sum(row["tokens_saved"] for row in positive)
        top = {"code": positive[0]["category"], "share": positive[0]["tokens_saved"] / total}
    return coverage, top


def card_data(
    path=None,
    language="zh",
    *,
    now=None,
    demo=None,
    catalog=None,
    reference=_UNSET,
    detected=None,
):
    """This week's numbers for the share card, from the local database only.

    ``demo`` forces the demo watermark on (True) or leaves it to detection (None):
    a database named like a demo, or counters named demo/test/fixture, count as
    demo data. ``reference`` defaults to the reference model chosen in Pricing.
    """
    from .pet_growth import growth_state
    from .store import default_store_path
    from .usage import UsageStore

    code = _language(language)
    words = TEXT[code]
    path = Path(path).expanduser() if path else default_store_path()
    if reference is _UNSET:
        from .cost_estimate import load_pricing

        reference = load_pricing()
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    today = moment.date()
    days = [str(today - timedelta(days=offset)) for offset in range(DAYS - 1, -1, -1)]
    sources = _week(path, days, catalog, reference, detected)
    mode = (reference or {}).get("mode")
    mode = mode if mode in ("input", "cached") else "input"
    ranked = sorted(
        sources.values(), key=lambda s: (-s["usable"], -s["calls"], s["source"] != "mcp")
    )
    main = ranked[0] if ranked else _new_source("mcp", days)
    others = ranked[1:]
    usable = main["usable"]
    saved = main["tokens_saved"]
    if usable == 0:
        state = "empty"
    elif saved > 0:
        state = "saved" if usable >= MIN_SAMPLES else "few"
    elif saved == 0:
        state = "none_saved"
    else:
        state = "increased"
    share = saved / main["input_tokens"] if state == "saved" and main["input_tokens"] else None
    money = _money(main, mode) if state in ("saved", "few") else None
    coverage, top = (None, None)
    # Request coverage and work types come from the gateway's request records only.
    if main["source"] == "gateway" and path.exists():
        coverage, top = _analysis(path, moment, catalog, reference, detected)
    if coverage is None and main["calls"]:
        coverage = {
            "kind": "preparations",
            "total": main["calls"],
            # Per-request events tell "shorter" from "unchanged"; daily totals cannot.
            "done": main["shorter"]
            if main["events"] == main["usable"]
            else max(0, main["usable"] - main["increased"]),
        }
    if top is not None:
        top = {**top, "label": category_label(top["code"], code)}
        if state != "saved":
            top["share"] = None
    counters = sorted(set().union(*(s["counters"] for s in sources.values())) if sources else ())
    detected_demo = "demo" in path.name.lower() or any(
        marker in counter.lower() for counter in counters for marker in DEMO_MARKERS
    )
    # The card shows the cat as it is on the desktop: grown by total saving.
    try:
        stage = growth_state(UsageStore(path).summary())["level"]
    except (OSError, sqlite3.Error):
        stage = 1
    data = {
        "language": code,
        "version": __version__,
        "generated": str(today),
        "start": days[0],
        "end": days[-1],
        "range": _range(days[0], days[-1]),
        "state": state,
        "source": main["source"],
        "source_label": words["label_" + main["source"]],
        "tokens_saved": saved,
        "input_tokens": main["input_tokens"],
        "output_tokens": main["output_tokens"],
        "share": share,
        "preparations": main["calls"],
        "usable": usable,
        "increased": main["increased"],
        "coverage": coverage,
        "top_category": top,
        "daily": [
            {"day": day, "tokens_saved": main["daily"].get(day, 0), "today": day == days[-1]}
            for day in days
        ],
        "money": money["value"] if money else None,
        "money_models": money["models"] if money else [],
        "money_mode": mode,
        "unpriced_tokens": money["unpriced_tokens"] if money else 0,
        "stage": stage,
        "demo": bool(demo) or detected_demo,
        "counters": sorted(main["counters"]) or ["regex-v1"],
        "other_sources": [
            {
                "source": other["source"],
                "label": words["label_" + other["source"]],
                "tokens_saved": other["tokens_saved"],
                "usable": other["usable"],
            }
            for other in others
        ],
    }
    data["text"] = card_text(data)
    return data


def _range(start, end):
    def short(day):
        month, date = day[5:7], day[8:10]
        return f"{int(month)}/{int(date)}"

    return f"{short(start)}–{short(end)}"


def card_text(data, *, hide_money=False):
    """Every string the card draws, by slot. The renderer draws only these."""
    words = TEXT[data["language"]]
    state = data["state"]
    text = {"title": words["title"], "range": data["range"]}
    if state in ("saved", "few"):
        text["lead"] = words["lead_saved"]
        text["number"] = tokens_text(data["tokens_saved"])
        text["unit"] = words["unit"]
        text["badge"] = words["estimate"]
        text["sub"] = (
            words["share"].format(share=percent_text(data["share"]))
            if data["share"] is not None
            else words["few"].format(n=data["usable"])
        )
    elif state in ("none_saved", "increased"):
        text["head"] = words["none_head"]
        text["sub"] = (
            words["grew_sub"].format(tokens=tokens_text(data["tokens_saved"]))
            if state == "increased"
            else words["none_sub"]
        )
    else:
        text["head"] = words["empty_head"]
        text["sub"] = words["empty_sub"]
    show_money = data["money"] is not None and not hide_money
    if show_money:
        kind = words["kind_cached"] if data["money_mode"] == "cached" else words["kind_input"]
        text["money"] = words["money"].format(money=money_text(data["money"]))
        text["money_note"] = words["money_note"].format(kind=kind)
        if data["unpriced_tokens"] > 0:
            text["money_unpriced"] = words["unpriced"].format(
                tokens=tokens_text(data["unpriced_tokens"])
            )
    days = data["daily"]
    text["chart"] = words["chart"]
    text["days"] = [
        words["today"] if row["today"] else f"{int(row['day'][5:7])}/{int(row['day'][8:10])}"
        for row in days
    ]
    peak = max(days, key=lambda row: row["tokens_saved"])
    text["peak"] = "≈ " + tokens_text(peak["tokens_saved"]) if peak["tokens_saved"] > 0 else ""
    text["chart_empty"] = words["chart_empty"] if peak["tokens_saved"] <= 0 else None
    text["cells"] = [
        (words["cell_runs"], words["runs"].format(n=f"{data['preparations']:,}")),
        (words["cell_cover"], _coverage_text(data["coverage"], words)),
        _third_cell(data, words),
    ]
    source_lines = [words["source_" + data["source"]]]
    source_lines += [
        words["source_also"].format(label=other["label"], tokens=tokens_text(other["tokens_saved"]))
        for other in data["other_sources"]
    ]
    text["sources"] = source_lines
    fixed = [words["fixed"]]
    if show_money:
        models = data["money_models"]
        fixed.append(
            words["basis"].format(model=models[0])
            if len(models) == 1
            else words["basis_many"].format(model=models[0], n=len(models) - 1)
        )
    fixed.append(words["counter"].format(counter=", ".join(data["counters"])))
    text["fixed"] = fixed
    text["footer"] = words["footer"].format(version=data["version"])
    text["repo"] = REPOSITORY
    text["made"] = words["made"].format(date=data["generated"])
    text["watermark"] = words["watermark"] if data["demo"] else None
    return text


def _coverage_text(coverage, words):
    if not coverage:
        return words["none"]
    key = "cover_requests" if coverage["kind"] == "requests" else "cover_runs"
    return words[key].format(total=f"{coverage['total']:,}", done=f"{coverage['done']:,}")


def _third_cell(data, words):
    """The top work type; without one, the average saving per preparation (≈)."""
    if data["top_category"] or data["state"] not in ("saved", "few"):
        return (words["cell_top"], _top_text(data["top_category"], words))
    average = data["tokens_saved"] / data["usable"]
    return (words["cell_average"], words["average"].format(tokens=tokens_text(round(average))))


def _top_text(top, words):
    if not top:
        return words["none"]
    if top.get("share") is None:
        return top["label"]
    return words["top_share"].format(label=top["label"], share=percent_text(top["share"]))


def card_strings(data, *, hide_money=False):
    """The flat list of strings on the card, in drawing order (for checks and alt text)."""
    text = card_text(data, hide_money=hide_money)
    out = []
    for key, value in text.items():
        if value is None:
            continue
        if key == "cells":
            out += [part for cell in value for part in cell]
        elif isinstance(value, list):
            out += value
        else:
            out.append(value)
    return out


def summary_line(data, *, hide_money=False):
    """One line of plain text describing the card, for the terminal."""
    words = TEXT[data["language"]]
    text = card_text(data, hide_money=hide_money)
    if data["state"] in ("saved", "few"):
        line = words["summary_saved"].format(
            range=data["range"], tokens=tokens_text(data["tokens_saved"])
        )
        if data["share"] is not None:
            line += words["summary_share"].format(share=percent_text(data["share"]))
        if "money" in text:
            line += words["summary_money"].format(money=money_text(data["money"]))
    else:
        line = words["summary_none"].format(range=data["range"], head=text["head"])
    if data["demo"]:
        line += words["summary_demo"]
    return line


def default_filename(data):
    return TEXT[data["language"]]["filename"].format(date=data["generated"].replace("-", ""))
