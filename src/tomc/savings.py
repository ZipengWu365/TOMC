"""Savings dashboard data: tokens saved, their value at each request's own model rate.

Reads the local statistics database only. A compiled request recorded by the
gateway carries its model ID; older or tool-path preparations fall back to the
host's detected default model, then to the reference model chosen in Pricing.
Saved tokens are valued at that model's listed input rate, except the share the
provider served from its prompt cache for that request, which is valued at the
cached-read rate: removing a token the provider would have read from cache saves
only the cached price. Choosing the cached-read mode in Pricing values all at it.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .cost_estimate import SETTINGS
from .pricing_catalog import all_rates

PERIODS = {"today": 0, "7d": 6, "all": None}
# Above these request sizes the provider lists a higher long-context rate.
_BANDS = {
    "openai": ("standard-short", "standard-long", 272_000),
    "anthropic": ("standard", "standard-long", 100_000),
}
_VARIANTS = {"deepseek": ("off-peak", "peak"), "cursor": ("listed",)}
_DATED = re.compile(r"-(?:\d{8}|latest)\Z")


def normalize_model(value):
    """``claude-opus-5-5[1m]`` and ``openai/gpt-6-astra`` name catalog models."""
    if not isinstance(value, str):
        return None
    model = value.strip().lower().split("[", 1)[0].rsplit("/", 1)[-1]
    return model or None


def model_rate(model, *, request_tokens=None, mode="input", rates=()):
    """The listed rate for one request's model, or None when it is not in the catalog."""
    name = normalize_model(model)
    if name is None:
        return None
    rows = [row for row in rates if row.get("model") == name]
    if not rows and _DATED.search(name):
        name = _DATED.sub("", name)
        rows = [row for row in rates if row.get("model") == name]
    if not rows:
        return None
    # Cursor resells other providers' models; prefer the model's own provider.
    rows.sort(key=lambda row: row.get("provider") == "cursor")
    provider = rows[0].get("provider")
    variants = {row.get("variant"): row for row in rows if row.get("provider") == provider}
    row = None
    if provider in _BANDS:
        short, long, threshold = _BANDS[provider]
        if isinstance(request_tokens, int) and request_tokens > threshold:
            row = variants.get(long)
        row = row or variants.get(short)
    else:
        row = next((variants[v] for v in _VARIANTS.get(provider, ()) if v in variants), None)
    row = row or next(iter(variants.values()))
    rate = row.get(mode)
    if (
        isinstance(rate, bool)
        or not isinstance(rate, (int, float))
        or not math.isfinite(rate)
        or rate < 0
    ):
        return None
    return {
        "model": row["model"],
        "label": row.get("label") or row["model"],
        "provider": provider,
        "variant": row.get("variant"),
        "rate": rate,
    }


def load_detected(path=None):
    """Default model per host, recorded when TOMC was installed."""
    try:
        data = json.loads(Path(path or SETTINGS.parent / "detected_models.json").read_text("utf-8"))
        return {
            host: row["model"]
            for host, row in data["hosts"].items()
            if isinstance(row, dict) and isinstance(row.get("model"), str)
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _pricer(catalog, reference, detected, mode):
    """Price a request by its own model, its host's detected default, then the reference."""
    rates = list(all_rates(catalog))
    detected = load_detected() if detected is None else detected
    fallback = None
    rate = (reference or {}).get(mode)
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        rate = (reference or {}).get("rate")
    if isinstance(rate, (int, float)) and not isinstance(rate, bool) and math.isfinite(rate):
        fallback = {
            "model": reference.get("model") or "reference",
            "label": reference.get("label") or reference.get("model") or "reference",
            "provider": reference.get("provider"),
            "rate": rate,
        }

    def price(model, host, request_tokens):
        if model:
            priced = model_rate(model, request_tokens=request_tokens, mode=mode, rates=rates)
            if priced:
                return priced, "request"
        if host in detected:
            priced = model_rate(
                detected[host], request_tokens=request_tokens, mode=mode, rates=rates
            )
            if priced:
                return priced, "detected"
        return (fallback, "reference") if fallback else (None, None)

    return fallback, price


def _blend(priced, cached, provider_input, provider_cached):
    """Value saved tokens at the request's own mix of cached and uncached input."""
    if (
        not priced
        or not cached
        or isinstance(provider_input, bool)
        or not isinstance(provider_input, int)
        or provider_input <= 0
        or isinstance(provider_cached, bool)
        or not isinstance(provider_cached, int)
    ):
        return priced
    share = min(1.0, max(0.0, provider_cached / provider_input))
    return {**priced, "rate": share * cached["rate"] + (1 - share) * priced["rate"]}


def request_savings(path, *, catalog=None, reference=None, detected=None):
    """Tokens and money each compiled request saved, keyed by request ID, with its session."""
    path = Path(path)
    if not path.exists():
        return {}
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    ) as db:
        tables = {
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not {"context_usage_events", "tomc_request_activity"} <= tables:
            return {}
        columns = {row[1] for row in db.execute("PRAGMA table_info(tomc_request_activity)")}
        model = "a.model" if "model" in columns else "NULL"
        usage = (
            "a.provider_input_tokens,a.provider_cached_tokens"
            if "provider_cached_tokens" in columns
            else "NULL,NULL"
        )
        rows = db.execute(
            f"SELECT e.request_id,e.input_tokens,e.memory_tokens,a.host,a.session_id,{model},"
            f"substr(e.recorded_at,1,10),{usage} FROM context_usage_events e "
            "JOIN tomc_request_activity a ON a.request_id=e.request_id WHERE e.usable=1"
        ).fetchall()
    mode = (reference or {}).get("mode")
    mode = mode if mode in ("input", "cached") else "input"
    _, price = _pricer(catalog, reference, detected, mode)
    _, cached_price = _pricer(catalog, reference, detected, "cached")
    result = {}
    for request_id, before, after, host, session_id, requested, day, used, cached in rows:
        priced, _basis = price(requested, host, before)
        if mode == "input":
            priced = _blend(priced, cached_price(requested, host, before)[0], used, cached)
        saved = before - after
        result[request_id] = {
            "host": host,
            "session_id": session_id,
            "day": day,
            "input_tokens": before,
            "tokens_saved": saved,
            "money": saved * priced["rate"] / 1_000_000 if priced else None,
            "model": priced["label"] if priced else None,
        }
    return result


def _empty(period, days, today):
    return {
        "period": period,
        "tokens_saved": 0,
        "preparations": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reduction_percent": None,
        "money": None,
        "unpriced_tokens": 0,
        "mode": "input",
        "models": [],
        "daily": [
            {"day": str(today - timedelta(days=offset)), "tokens_saved": 0}
            for offset in range(days - 1, -1, -1)
        ],
    }


def savings_report(
    path, period="all", *, days=14, now=None, catalog=None, reference=None, detected=None
):
    """Totals for today, the last seven UTC days or all time, plus a daily trend.

    ``reference`` is the Pricing selection (``load_pricing()``); its mode, input or
    cached read, applies to every model. Daily aggregates are authoritative for
    token totals; events written before per-request records existed are valued
    at the reference model.
    """
    if period not in PERIODS:
        raise ValueError("period must be all, today, or 7d (UTC).")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 366:
        raise ValueError("days must be an integer from 1 to 366.")
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    report = _empty(period, days, today)
    mode = (reference or {}).get("mode")
    mode = report["mode"] = mode if mode in ("input", "cached") else "input"
    path = Path(path)
    if not path.exists():
        return report
    span = PERIODS[period]
    start = None if span is None else str(today - timedelta(days=span))
    # Read the selected period and the trend window in one pass.
    lower = None if start is None else min(start, str(today - timedelta(days=days - 1)))
    with closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
    ) as db:
        db.execute("BEGIN")
        tables = {
            name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "context_usage_daily" not in tables:
            return report
        daily = db.execute(
            "SELECT day,SUM(usable_calls),SUM(input_tokens),SUM(memory_tokens) "
            "FROM context_usage_daily WHERE day<=? AND (? IS NULL OR day>=?) GROUP BY day",
            (str(today), lower, lower),
        ).fetchall()
        events = []
        if "context_usage_events" in tables:
            joined = "tomc_request_activity" in tables
            columns = (
                {row[1] for row in db.execute("PRAGMA table_info(tomc_request_activity)")}
                if joined
                else set()
            )
            host = "a.host" if joined else "NULL"
            model = "a.model" if "model" in columns else "NULL"
            usage = (
                "a.provider_input_tokens,a.provider_cached_tokens"
                if "provider_cached_tokens" in columns
                else "NULL,NULL"
            )
            join = (
                " LEFT JOIN tomc_request_activity a ON a.request_id=e.request_id" if joined else ""
            )
            events = db.execute(
                f"SELECT substr(e.recorded_at,1,10),e.input_tokens,e.memory_tokens,{host},{model},"
                f"{usage} "
                f"FROM context_usage_events e{join} WHERE e.usable=1 "
                "AND substr(e.recorded_at,1,10)<=? AND (? IS NULL OR substr(e.recorded_at,1,10)>=?)",
                (str(today), start, start),
            ).fetchall()
    trend = {row["day"]: row for row in report["daily"]}
    in_period = {}
    for day, calls, before, after in daily:
        if day in trend:
            trend[day]["tokens_saved"] = before - after
        if start is None or day >= start:
            in_period[day] = (calls, before, after)
            report["preparations"] += calls
            report["input_tokens"] += before
            report["output_tokens"] += after
    reference_price, price = _pricer(catalog, reference, detected, mode)
    _, cached_price = _pricer(catalog, reference, detected, "cached")
    groups = {}

    def add(tokens, priced, basis, host):
        key = priced["model"] if priced else None
        group = groups.setdefault(
            key,
            {
                "model": key,
                "label": priced["label"] if priced else None,
                "provider": priced.get("provider") if priced else None,
                "bases": set(),
                "hosts": set(),
                "rates": set(),
                "tokens_saved": 0,
                "money": 0.0 if priced else None,
                "preparations": 0,
            },
        )
        group["tokens_saved"] += tokens
        if host:
            group["hosts"].add(host)
        if priced:
            group["bases"].add(basis)
            group["rates"].add(priced["rate"])
            group["money"] += tokens * priced["rate"] / 1_000_000
        return group

    seen = {}
    for day, before, after, host, model, used, cached in events:
        saved = before - after
        seen[day] = seen.get(day, 0) + saved
        priced, basis = price(model, host, before)
        if mode == "input":
            priced = _blend(priced, cached_price(model, host, before)[0], used, cached)
        add(saved, priced, basis, host)["preparations"] += 1
    # Aggregates written before per-request events existed (or by an older writer).
    for day, (_calls, before, after) in in_period.items():
        missing = (before - after) - seen.get(day, 0)
        if missing > 0:
            add(missing, reference_price, "reference", None)
    report["tokens_saved"] = sum(group["tokens_saved"] for group in groups.values())
    if not groups:
        report["tokens_saved"] = report["input_tokens"] - report["output_tokens"]
    priced = [group for group in groups.values() if group["money"] is not None]
    report["money"] = sum(group["money"] for group in priced) if priced else None
    report["unpriced_tokens"] = sum(
        group["tokens_saved"] for group in groups.values() if group["money"] is None
    )
    if report["input_tokens"]:
        report["reduction_percent"] = round(
            100 * (report["input_tokens"] - report["output_tokens"]) / report["input_tokens"], 2
        )
    report["models"] = sorted(
        (
            {
                **group,
                "bases": sorted(group["bases"]),
                "hosts": sorted(group["hosts"]),
                "rates": sorted(group["rates"]),
            }
            for group in groups.values()
            if group["tokens_saved"] or group["preparations"]
        ),
        key=lambda group: (group["model"] is None, -group["tokens_saved"]),
    )
    return report
