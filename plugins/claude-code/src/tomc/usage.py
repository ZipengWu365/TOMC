"""Local preparation accounting, never provider usage or billed savings."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .easy import PreparedContext

SCOPE = (
    "Estimated context-text reduction per preparation, not API usage or billed savings. "
    "Excludes task, tool/request overhead and caching. Repeated preparations count separately; "
    "empty outputs are excluded from token totals."
)


def reduction_report(prepared: PreparedContext) -> dict:
    """Keep signed differences; an empty output is not a usable saving."""
    stats = prepared.compilation.stats
    before, after = stats.input_tokens, stats.output_tokens
    usable = bool(prepared.compilation.compiled_memory.strip()) and before > 0
    delta = before - after if usable else None
    percent = round(100 * delta / before, 2) if usable else None
    if not usable:
        summary = "TOMC: no usable context; excluded from estimated reduction totals."
    else:
        summary = (
            f"TOMC estimated context tokens: {before:,} -> {after:,}; "
            f"reduction {delta:+,} ({percent:+.2f}%). Not API/billing savings."
        )
    return {
        "input_tokens": before,
        "memory_tokens": after,
        "reduced_tokens": delta,
        "reduction_percent": percent,
        "counter": stats.tokenizer,
        "usable": usable,
        "summary": summary,
    }


class UsageStore:
    """Daily numeric aggregates in the notebook DB, without content or notebook names."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _schema(self, db):
        db.execute(
            "CREATE TABLE IF NOT EXISTS context_usage_daily ("
            "day TEXT NOT NULL, counter TEXT NOT NULL, calls INTEGER NOT NULL, "
            "usable_calls INTEGER NOT NULL, increased_calls INTEGER NOT NULL, "
            "input_tokens INTEGER NOT NULL, memory_tokens INTEGER NOT NULL, "
            "PRIMARY KEY(day,counter))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS context_usage_latest ("
            "id INTEGER PRIMARY KEY CHECK(id=1), recorded_at TEXT NOT NULL, "
            "counter TEXT NOT NULL, input_tokens INTEGER NOT NULL, "
            "memory_tokens INTEGER NOT NULL, usable INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS context_usage_growth ("
            "counter TEXT PRIMARY KEY, peak_net_tokens INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS context_usage_events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL, "
            "counter TEXT NOT NULL, input_tokens INTEGER NOT NULL, "
            "memory_tokens INTEGER NOT NULL, usable INTEGER NOT NULL)"
        )

    def record(self, report: dict) -> None:
        """Atomically count one completed preparation, including zero/negative reduction."""
        usable = report["usable"]
        values = (
            datetime.now(timezone.utc).date().isoformat(), report["counter"], 1,
            int(usable), int(usable and report["reduced_tokens"] < 0),
            report["input_tokens"] if usable else 0,
            report["memory_tokens"] if usable else 0,
        )
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            self._schema(db)
            db.execute(
                "INSERT INTO context_usage_daily VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(day,counter) DO UPDATE SET "
                "calls=calls+excluded.calls, usable_calls=usable_calls+excluded.usable_calls, "
                "increased_calls=increased_calls+excluded.increased_calls, "
                "input_tokens=input_tokens+excluded.input_tokens, "
                "memory_tokens=memory_tokens+excluded.memory_tokens", values,
            )
            recorded_at = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT OR REPLACE INTO context_usage_latest VALUES (1,?,?,?,?,?)",
                (recorded_at, report["counter"],
                 report["input_tokens"], report["memory_tokens"], int(usable)),
            )
            db.execute(
                "INSERT INTO context_usage_events "
                "(recorded_at,counter,input_tokens,memory_tokens,usable) VALUES (?,?,?,?,?)",
                (recorded_at, report["counter"], report["input_tokens"],
                 report["memory_tokens"], int(usable)),
            )
            db.execute("DELETE FROM context_usage_events WHERE seq <= "
                       "(SELECT MAX(seq)-64 FROM context_usage_events)")
            # Keep earned forms even when a later preparation increases context.
            # Growth uses the signed cumulative net, never a sum of positive calls.
            net = db.execute(
                "SELECT COALESCE(SUM(input_tokens-memory_tokens),0) "
                "FROM context_usage_daily WHERE counter=?", (report["counter"],),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO context_usage_growth VALUES (?,?) "
                "ON CONFLICT(counter) DO UPDATE SET "
                "peak_net_tokens=MAX(peak_net_tokens,excluded.peak_net_tokens)",
                (report["counter"], max(0, net)),
            )

    def recent_events(self, after: int = 0) -> list[dict]:
        """Bounded numeric-only animation queue, not notebook/conversation content."""
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=0.2)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='context_usage_events'").fetchone():
                return []
            rows = db.execute("SELECT seq,recorded_at,counter,input_tokens,memory_tokens,usable "
                              "FROM context_usage_events WHERE seq>? ORDER BY seq", (after,)).fetchall()
        return [{"seq": seq, "recorded_at": at, "counter": counter,
                 "input_tokens": before, "memory_tokens": after_tokens, "usable": bool(usable),
                 "reduced_tokens": before-after_tokens if usable else None}
                for seq, at, counter, before, after_tokens, usable in rows]

    def summary(self, period: str = "all") -> dict:
        """Read all time, today UTC, or the rolling seven UTC calendar days."""
        if period not in {"all", "today", "7d"}:
            raise ValueError("period must be all, today, or 7d (UTC).")
        today = datetime.now(timezone.utc).date()
        start = None if period == "all" else today - timedelta(days=6 if period == "7d" else 0)
        # Readers (including the floating display) never create or change a DB.
        if not self.path.exists():
            return self._empty(period, start, today)
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=0.2)) as db:
            db.execute("BEGIN")
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='context_usage_daily'"
            ).fetchone()
            rows = [] if not exists else db.execute(
                "SELECT counter, SUM(calls), SUM(usable_calls), SUM(increased_calls), "
                "SUM(input_tokens), SUM(memory_tokens) FROM context_usage_daily "
                "WHERE (? IS NULL OR day>=?) AND day<=? GROUP BY counter ORDER BY counter",
                (str(start) if start else None, str(start) if start else None, str(today)),
            ).fetchall()
            has_latest = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='context_usage_latest'"
            ).fetchone()
            latest = None if not has_latest else db.execute(
                "SELECT recorded_at,counter,input_tokens,memory_tokens,usable "
                "FROM context_usage_latest WHERE id=1"
            ).fetchone()
            has_growth = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='context_usage_growth'"
            ).fetchone()
            peaks = dict(db.execute("SELECT counter,peak_net_tokens FROM context_usage_growth")) \
                if has_growth else {}
            growth_rows = [] if not exists else db.execute(
                "SELECT counter,SUM(input_tokens-memory_tokens) FROM context_usage_daily "
                "WHERE day<=? GROUP BY counter ORDER BY counter", (str(today),),
            ).fetchall()
        groups = []
        for counter, calls, usable, increased, before, after in rows:
            groups.append({
                "counter": counter, "preparations": calls, "usable_preparations": usable,
                "excluded_empty_preparations": calls - usable, "increased_preparations": increased,
                "input_tokens": before, "memory_tokens": after,
                "reduced_tokens": before - after,
                "reduction_percent": round(100 * (before - after) / before, 2) if before else None,
            })
        result = self._empty(period, start, today)
        result.update({"preparations": sum(group["preparations"] for group in groups),
                       "by_counter": groups,
                       "growth": [{"counter": counter, "net_tokens": net,
                                   "peak_net_tokens": max(0, net, peaks.get(counter, 0))}
                                  for counter, net in growth_rows]})
        if latest:
            at, counter, before, after, usable = latest
            result["last_preparation"] = {
                "recorded_at": at, "counter": counter, "input_tokens": before,
                "memory_tokens": after, "usable": bool(usable),
                "reduced_tokens": before - after if usable else None,
                "reduction_percent": round(100 * (before - after) / before, 2)
                if usable and before else None,
            }
        return result

    @staticmethod
    def _empty(period, start, today):
        return {
            "period": period, "timezone": "UTC", "start_date": str(start) if start else None,
            "end_date": str(today), "scope": SCOPE,
            "preparations": 0, "by_counter": [], "last_preparation": None, "growth": [],
        }
