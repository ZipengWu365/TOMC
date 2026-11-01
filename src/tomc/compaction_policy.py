"""Cost-aware compaction decisions for the request gateway adapters.

Rewriting history pays only when the tokens it removes would have been billed
often enough to cover what the rewrite bills again. With provider prompt
caching, removed history would otherwise be read at the cached rate on every
later request, while everything after the first changed message is written
again at the cache-write rate (Anthropic 1.25x input for 5-minute and 2x for
1-hour entries; OpenAI-style caches bill a miss at the input rate). A cold
cache (expired, first request, provider without caching) bills the whole
request anyway, so shrinking it is an immediate gain.

``decide`` compares one candidate rewrite with sending the request unchanged:

    immediate = cost(candidate now) - cost(unchanged now)
    future    = cached_rate * removed * (1 - risk) * expected_remaining_requests
    refetch   = risk * removed * write_rate
    apply when future - immediate - refetch > margin * (max(immediate, 0) + refetch)

Requests close to the model window are compacted regardless, which is cheaper
than a host's model-written summary. Amounts are in input-price token units.
The decision itself is a pure function of numbers. ``SessionStats`` rows hold
counters and short call hashes only, never request content.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Relative (input, cached read, cache write) rates when the catalog has no row.
_DEFAULT_RATES = {
    "anthropic": (1.0, 0.1, 1.25),
    "anthropic_1h": (1.0, 0.1, 2.0),
    "openai": (1.0, 0.1, 1.0),
}
_KEY_LIMIT = 2000
_ID_LIMIT = 64


@dataclass(frozen=True)
class Prices:
    """Per-token rates in any common unit; only their ratios matter."""

    input: float
    cache_read: float
    cache_write: float
    source: str


def prices_for(provider: str, model: str | None, *, long_ttl: bool = False) -> Prices:
    """Bundled/synced catalog rates for ``model``, else conservative defaults."""
    name = model.split("[", 1)[0] if isinstance(model, str) else None
    try:
        from .pricing_catalog import all_rates

        rows = [
            r
            for r in all_rates()
            if r.get("provider") == provider
            and r.get("model") == name
            and r.get("variant") in ("standard", "standard-short")
        ]
    except Exception:  # A broken local catalog must not block a request.
        rows = []
    if rows and isinstance(rows[0].get("input"), (int, float)) and rows[0]["input"] > 0:
        row = rows[0]
        rate = float(row["input"])
        cached = row.get("cached")
        if not isinstance(cached, (int, float)):
            # No cached rate: every request is billed in full.
            return Prices(rate, rate, rate, "catalog:" + str(row.get("key")))
        write = row.get("cache_write_1h") if long_ttl else None
        write = write if isinstance(write, (int, float)) else row.get("cache_write")
        write = float(write) if isinstance(write, (int, float)) else rate
        return Prices(rate, float(cached), write, "catalog:" + str(row.get("key")))
    key = "anthropic_1h" if provider == "anthropic" and long_ttl else provider
    rates = _DEFAULT_RATES.get(key, _DEFAULT_RATES["anthropic"])
    return Prices(*rates, "default:" + key)


@dataclass
class SessionStats:
    """Per-session counters persisted by an adapter; numbers and hashes only."""

    requests: int = 0
    last_seen: float | None = None
    ttl: int = 300
    last_sent_tokens: int | None = None
    last_provider_input: int | None = None
    last_provider_cached: int | None = None
    token_ratio: float | None = None
    compactions: int = 0
    compiled_calls: int = 0
    refetches: int = 0
    compiled_keys: list[str] = field(default_factory=list)
    counted_ids: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, value: Any) -> SessionStats:
        if not isinstance(value, dict):
            return cls()
        known = {k: v for k, v in value.items() if k in cls.__dataclass_fields__}
        try:
            return cls(**known)
        except TypeError:
            return cls()

    def remember_compiled(self, keys: Sequence[str]) -> None:
        self.compiled_calls += len(keys)
        self.compiled_keys = [*self.compiled_keys, *keys][-_KEY_LIMIT:]

    def observe_calls(self, calls: Sequence[tuple[str, str]]) -> None:
        """Count new calls (id, key) that repeat a call TOMC compiled away."""
        known = set(self.compiled_keys)
        counted = set(self.counted_ids)
        for call_id, key in calls:
            if call_id in counted:
                continue
            counted.add(call_id)
            self.counted_ids = [*self.counted_ids, call_id][-_ID_LIMIT:]
            if key in known:
                self.refetches += 1

    def observe_usage(
        self, sent_tokens: int | None, provider_input: int | None, provider_cached: int | None
    ) -> None:
        if provider_input is not None:
            self.last_provider_input = provider_input
            self.last_provider_cached = provider_cached
            if sent_tokens:
                ratio = provider_input / sent_tokens
                if 0.2 <= ratio <= 5:
                    self.token_ratio = (
                        ratio if self.token_ratio is None else 0.5 * self.token_ratio + 0.5 * ratio
                    )

    @property
    def risk(self) -> float:
        """Share of compiled calls the agent repeated, with a 1-in-10 prior."""
        return min(0.9, (self.refetches + 1) / (self.compiled_calls + 10))


def cache_warm(stats: SessionStats, now: float) -> bool:
    """The previous request is recent and its large prompt was actually cached."""
    if stats.last_seen is None or now - stats.last_seen >= 0.9 * stats.ttl:
        return False
    return not (
        stats.last_provider_input is not None
        and stats.last_provider_input > 4096
        and not stats.last_provider_cached
    )


def expected_remaining(
    requests: int, history: Sequence[int], *, prior: float = 0.5, min_sessions: int = 8
) -> float:
    """Median further requests of earlier sessions that reached this length.

    Without enough history, a conservative fraction of the requests so far:
    a session that has run longer is more likely to keep running.
    """
    reached = [length - requests for length in history if length >= requests]
    if len(reached) >= min_sessions:
        return float(statistics.median(reached))
    return prior * requests


@dataclass(frozen=True)
class Decision:
    apply: bool
    reason: str
    gain: float
    cost: float
    remaining: float
    warm: bool

    def detail(self) -> dict[str, Any]:
        return {
            "policy": self.reason,
            "policy_gain": max(0, round(self.gain)),
            "policy_cost": max(0, round(self.cost)),
            "policy_remaining": max(0, round(self.remaining)),
            "policy_warm": self.warm,
        }


def decide(
    *,
    before: int,
    after: int,
    kept: int,
    previous: int | None,
    prices: Prices,
    warm: bool,
    remaining: float,
    ratio: float | None = None,
    risk: float = 0.1,
    margin: float = 0.5,
    window: int | None = None,
    pressure: float = 0.8,
) -> Decision:
    """Weigh one rewrite against the unchanged request; see the module docstring.

    ``before``/``after``/``kept``/``previous`` are lexical estimates of the
    unchanged request, the rewritten request, the rewritten request's unchanged
    leading part, and the previous request as sent. ``ratio`` converts them to
    provider tokens.
    """
    k = ratio or 1.0
    removed = max(0, before - after) * k
    if removed <= 0:
        return Decision(False, "no_reduction", 0.0, 0.0, remaining, warm)
    u = prices.input or 1.0
    r, w = prices.cache_read / u, prices.cache_write / u
    if window and before * k >= pressure * window:
        return Decision(True, "window_pressure", removed, 0.0, remaining, warm)
    if warm:
        cached = min(previous or 0, before)
        hit = min(kept, after)
        unchanged_now = r * cached + w * (before - cached)
        rewritten_now = r * hit + w * (after - hit)
    else:
        unchanged_now, rewritten_now = w * before, w * after
    immediate = (rewritten_now - unchanged_now) * k
    future = r * removed * (1 - risk) * max(0.0, remaining)
    refetch = risk * removed * w
    gain = future - min(immediate, 0.0)
    cost = max(immediate, 0.0) + refetch
    if gain - cost > margin * cost:
        return Decision(True, "profitable" if warm else "cold_cache", gain, cost, remaining, warm)
    return Decision(False, "unprofitable", gain, cost, remaining, warm)


_TABLE = (
    "CREATE TABLE IF NOT EXISTS tomc_compaction_sessions ("
    "host TEXT NOT NULL, session_id TEXT NOT NULL, requests INTEGER NOT NULL, "
    "stats TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(host,session_id))"
)


def load_stats(db: sqlite3.Connection, host: str, session_id: str) -> SessionStats:
    db.execute(_TABLE)
    row = db.execute(
        "SELECT stats FROM tomc_compaction_sessions WHERE host=? AND session_id=?",
        (host, session_id),
    ).fetchone()
    try:
        return SessionStats.from_json(json.loads(row[0])) if row else SessionStats()
    except ValueError:
        return SessionStats()


def save_stats(
    db: sqlite3.Connection, host: str, session_id: str, stats: SessionStats, now: float
) -> None:
    db.execute(_TABLE)
    db.execute(
        "INSERT INTO tomc_compaction_sessions VALUES (?,?,?,?,?) ON CONFLICT(host,session_id) "
        "DO UPDATE SET requests=excluded.requests,stats=excluded.stats,updated=excluded.updated",
        (host, session_id, stats.requests, json.dumps(stats.to_json()), now),
    )


def session_lengths(db: sqlite3.Connection, host: str, exclude: str, limit: int = 500) -> list[int]:
    """Main-request counts of this host's most recent other sessions."""
    db.execute(_TABLE)
    return [
        row[0]
        for row in db.execute(
            "SELECT requests FROM tomc_compaction_sessions WHERE host=? AND session_id<>? "
            "ORDER BY updated DESC LIMIT ?",
            (host, exclude, limit),
        )
    ]


def observe_usage(
    path: Path | str,
    host: str,
    session_id: str,
    *,
    sent_tokens: int | None,
    provider_input: int | None,
    provider_cached: int | None,
) -> None:
    """Record the provider's reported usage of the request a session just sent."""
    db = sqlite3.connect(path, timeout=30)
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(_TABLE)
            row = db.execute(
                "SELECT stats,updated FROM tomc_compaction_sessions WHERE host=? AND session_id=?",
                (host, session_id),
            ).fetchone()
            if row is None:
                return
            stats = SessionStats.from_json(json.loads(row[0]))
            stats.observe_usage(sent_tokens, provider_input, provider_cached)
            save_stats(db, host, session_id, stats, row[1])
    finally:
        db.close()
