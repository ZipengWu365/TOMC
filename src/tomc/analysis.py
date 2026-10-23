"""A local savings analysis, and the anonymous feedback report a user may submit.

The analysis names conversations for the user's own screen. The feedback report
keeps only work categories, counts and coarse distributions: no conversation
names, folders, tasks, content, session or request IDs. It is built locally and
leaves the computer only when the user submits it on GitHub.
"""

from __future__ import annotations

import json
import platform
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from . import __version__
from .categories import CODES, classify
from .conversation_names import resolve
from .pet_growth import STAGES
from .savings import PERIODS, request_savings, savings_report

REPOSITORY = "ZipengWu365/TOMC"
FEEDBACK_FOLDER = "feedback/reports"
# GitHub's new-file page reads the report from the URL; longer links are refused.
MAX_URL = 7500
MAX_COMMENT = 1000
MAX_CONVERSATIONS = 20
REDUCTION_EDGES = (0.01, 0.05, 0.10, 0.25, 0.50)
REDUCTION_LABELS = ("<1%", "1-5%", "5-10%", "10-25%", "25-50%", ">=50%")
# Why a request reached the model unchanged, grouped for people rather than code.
COVERAGE = {
    "compressed": {"old_history_compiled_cache_may_change", "replayed_prefix"},
    "host_managed": {
        "native_compaction_state",
        "native_compaction",
        "native_compaction_reset",
        "native_compaction_active",
        "native_compaction_completed",
        "native_compaction_cooldown",
        "host_compaction_request",
        "native_context_management",
        "server_side_or_incremental_history",
        "native_or_unknown_request",
        "previous_response_id",
    },
    "short": {
        "insufficient_old_history",
        "history_below_threshold",
        "history_fits_memory_budget",
        "no_readable_old_history",
        "no_eligible_old_history",
        "no_request_size_reduction",
        "nonshrinking",
        "no_complete_memory_fits",
    },
    "auxiliary": {"auxiliary_request", "non_main_request", "subagent_request"},
    "switched_off": {
        "session_disabled",
        "global_disabled",
        "disabled",
        "disabled_compatible_replay",
    },
}
COVERAGE_ORDER = (
    "compressed",
    "host_managed",
    "short",
    "unsupported",
    "auxiliary",
    "switched_off",
    "failed",
)


def coverage_group(state, reason):
    if state == "failed" or reason in {"client_disconnected", "transport_failed"}:
        return "failed"
    for group, reasons in COVERAGE.items():
        if reason in reasons:
            return group
    return "compressed" if state in {"prepared", "forwarded"} else "unsupported"


def _period_start(period, today):
    span = PERIODS[period]
    return None if span is None else str(today - timedelta(days=span))


def _activity(path, start):
    coverage, stages = dict.fromkeys(COVERAGE_ORDER, 0), [0] * len(STAGES)
    if not Path(path).exists():
        return coverage, stages
    with closing(
        sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    ) as db:
        tables = {
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "tomc_request_activity" in tables:
            for state, reason, count in db.execute(
                "SELECT state,reason,COUNT(*) FROM tomc_request_activity "
                "WHERE state!='preparing' AND (? IS NULL OR substr(started_utc,1,10)>=?) "
                "GROUP BY state,reason",
                (start, start),
            ):
                coverage[coverage_group(state, reason)] += count
        if "tomc_context_prepared_events" in tables:
            for (tokens,) in db.execute(
                "SELECT context_input_tokens FROM tomc_context_prepared_events "
                "WHERE ? IS NULL OR substr(prepared_utc,1,10)>=?",
                (start, start),
            ):
                stages[max(i for i, stage in enumerate(STAGES) if tokens >= stage[0])] += 1
    return coverage, stages


def analysis_report(
    path,
    period="all",
    *,
    now=None,
    days=30,
    records=None,
    names=None,
    catalog=None,
    reference=None,
    detected=None,
):
    """Savings by conversation and work category, with coverage and size distributions."""
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    start = _period_start(period, today)
    totals = savings_report(
        path, period, days=days, now=now, catalog=catalog, reference=reference, detected=detected
    )
    requests = [
        row
        for row in request_savings(
            path, catalog=catalog, reference=reference, detected=detected
        ).values()
        if start is None or (row["day"] or "") >= start
    ]
    if records is None:
        from .context_library import ContextLibrary

        records = ContextLibrary(path).list(limit=10000)
    sessions = {}
    for row in requests:
        if row["session_id"]:
            entry = sessions.setdefault(
                (row["host"], row["session_id"]),
                {"tokens_saved": 0, "money": None, "compressions": 0, "titles": [], "contexts": 0},
            )
            entry["tokens_saved"] += row["tokens_saved"]
            entry["compressions"] += 1
            if row["money"] is not None:
                entry["money"] = (entry["money"] or 0.0) + row["money"]
    for record in records:  # newest first
        key = (record.get("host"), record.get("session_id"))
        if not key[1]:
            continue
        entry = sessions.setdefault(
            key, {"tokens_saved": 0, "money": None, "compressions": 0, "titles": [], "contexts": 0}
        )
        entry["titles"].append(record.get("title") or "")
        if start is None or (record.get("created_utc") or "")[:10] >= start:
            entry["contexts"] += 1
    names = resolve(sessions) if names is None else names
    conversations = []
    for (host, session), entry in sessions.items():
        if not entry["compressions"] and not entry["contexts"]:
            continue  # no activity inside this period
        name = names.get((host, session)) or {}
        first = entry["titles"][-1] if entry["titles"] else None
        conversations.append(
            {
                "key": (host, session),
                "host": host,
                "title": name.get("title") or first,
                "folder": name.get("folder"),
                "agent": name.get("agent"),
                "category": classify(
                    name.get("title") or first, name.get("folder"), *entry["titles"][:10]
                ),
                "tokens_saved": entry["tokens_saved"],
                "money": entry["money"],
                "compressions": entry["compressions"],
                "contexts": entry["contexts"],
            }
        )
    conversations.sort(key=lambda row: (-row["tokens_saved"], -row["compressions"]))
    attributed = sum(row["tokens_saved"] for row in conversations)
    categories = {}
    for row in conversations:
        group = categories.setdefault(
            row["category"],
            {
                "category": row["category"],
                "tokens_saved": 0,
                "money": None,
                "conversations": 0,
                "compressions": 0,
            },
        )
        group["tokens_saved"] += row["tokens_saved"]
        group["conversations"] += 1
        group["compressions"] += row["compressions"]
        if row["money"] is not None:
            group["money"] = (group["money"] or 0.0) + row["money"]
    hosts = {}
    for row in requests:
        group = hosts.setdefault(
            row["host"] or "other",
            {"host": row["host"] or "other", "tokens_saved": 0, "compressions": 0},
        )
        group["tokens_saved"] += row["tokens_saved"]
        group["compressions"] += 1
    reductions = [0] * len(REDUCTION_LABELS)
    for row in requests:
        share = row["tokens_saved"] / row["input_tokens"] if row["input_tokens"] else 0
        reductions[sum(share >= edge for edge in REDUCTION_EDGES)] += 1
    coverage, stages = _activity(path, start)
    observed = sum(coverage.values())
    return {
        "period": period,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "tokens_saved": totals["tokens_saved"],
            "money": totals["money"],
            "compressions": totals["preparations"],
            "conversations": len(conversations),
            "requests": observed,
            "compressed_share": coverage["compressed"] / observed if observed else None,
            "unattributed_tokens": totals["tokens_saved"] - attributed,
        },
        "conversations": conversations,
        "categories": sorted(categories.values(), key=lambda row: -row["tokens_saved"]),
        "hosts": sorted(hosts.values(), key=lambda row: -row["tokens_saved"]),
        "models": totals["models"],
        "daily": totals["daily"],
        "mode": totals["mode"],
        "reductions": [
            {"bucket": label, "requests": count}
            for label, count in zip(REDUCTION_LABELS, reductions)
        ],
        "stages": [
            {"stage": index + 1, "compilations": count} for index, count in enumerate(stages)
        ],
        "coverage": [{"group": group, "requests": coverage[group]} for group in COVERAGE_ORDER],
    }


def _system():
    name = platform.system()
    return {"Darwin": "macOS"}.get(name, name or "unknown")


def feedback_payload(report, *, categories=None, comment="", system=None):
    """The anonymous report: categories and counts, never names, folders, tasks or IDs.

    ``categories`` maps a conversation key to the user's corrected category.
    """
    categories = categories or {}
    numbered, conversations = {}, []
    for row in report["conversations"][:MAX_CONVERSATIONS]:
        category = categories.get(row["key"], row["category"])
        category = category if category in CODES else "other"
        numbered[category] = numbered.get(category, 0) + 1
        conversations.append(
            {
                "label": f"{category} #{numbered[category]}",
                "category": category,
                "host": row["host"] if row["host"] in ("codex", "claude") else "other",
                "compressions": row["compressions"],
                "contexts": row["contexts"],
                "tokens_saved": row["tokens_saved"],
            }
        )
    by_category = {}
    for row in report["conversations"]:
        category = categories.get(row["key"], row["category"])
        category = category if category in CODES else "other"
        group = by_category.setdefault(
            category,
            {"category": category, "conversations": 0, "compressions": 0, "tokens_saved": 0},
        )
        group["conversations"] += 1
        group["compressions"] += row["compressions"]
        group["tokens_saved"] += row["tokens_saved"]
    totals = report["totals"]
    return {
        "format": "tomc-feedback-v1",
        "tomc_version": __version__,
        "system": system or _system(),
        "period": report["period"],
        "date": report["generated_utc"][:10],
        "totals": {
            "tokens_saved": totals["tokens_saved"],
            "money_usd": round(totals["money"], 4) if totals["money"] is not None else None,
            "valued_at": report["mode"],
            "compressions": totals["compressions"],
            "conversations": totals["conversations"],
            "requests": totals["requests"],
            "compressed_share": round(totals["compressed_share"], 4)
            if totals["compressed_share"] is not None
            else None,
        },
        "categories": sorted(by_category.values(), key=lambda row: -row["tokens_saved"]),
        "conversations": conversations,
        "hosts": [
            {**row, "host": row["host"] if row["host"] in ("codex", "claude") else "other"}
            for row in report["hosts"]
        ],
        "models": [
            {"model": row["model"] or "unpriced", "tokens_saved": row["tokens_saved"]}
            for row in report["models"]
        ],
        "coverage": report["coverage"],
        "reductions": report["reductions"],
        "stages": report["stages"],
        "daily": [[row["day"], row["tokens_saved"]] for row in report["daily"]],
        "comment": (comment or "").strip()[:MAX_COMMENT],
    }


def feedback_markdown(payload):
    totals = payload["totals"]
    lines = [
        "# TOMC feedback report",
        "",
        f"TOMC {payload['tomc_version']} · {payload['system']} · period: {payload['period']} · "
        f"{payload['date']}",
        "",
        "Contains work categories and counts only: no conversation names, folders, tasks, "
        "content or IDs.",
        "",
        f"- Tokens saved: {totals['tokens_saved']:,}",
        f"- Compressions: {totals['compressions']:,} across {totals['conversations']} conversations",
    ]
    if totals["compressed_share"] is not None:
        lines.append(
            f"- Requests compressed: {totals['compressed_share']:.1%} of {totals['requests']:,}"
        )
    if payload["categories"]:
        lines.append(
            "- Top categories: "
            + ", ".join(
                f"{row['category']} {row['tokens_saved']:,}" for row in payload["categories"][:3]
            )
        )
    if payload["comment"]:
        lines += ["", "## Comment", "", payload["comment"]]
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    lines += ["", "## Data", "", "```json", data, "```", ""]
    return "\n".join(lines)


def feedback_filename(date):
    return f"{FEEDBACK_FOLDER}/{date}-{uuid.uuid4().hex[:8]}.md"


def feedback_url(markdown, filename, *, repository=REPOSITORY, branch="main"):
    """GitHub's new-file page with the report filled in; None when the link is too long.

    Submitting the page proposes the file; for anyone without write access GitHub
    forks the repository and opens a pull request.
    """
    base = f"https://github.com/{repository}/new/{quote(branch)}"
    url = f"{base}?{urlencode({'filename': filename, 'value': markdown}, quote_via=quote)}"
    return url if len(url) <= MAX_URL else None


def feedback_page(filename, *, repository=REPOSITORY, branch="main"):
    """The same page without content, for pasting a report that does not fit in a link."""
    base = f"https://github.com/{repository}/new/{quote(branch)}"
    return f"{base}?{urlencode({'filename': filename}, quote_via=quote)}"
