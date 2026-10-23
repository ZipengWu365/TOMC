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
            "memory_tokens INTEGER NOT NULL, usable INTEGER NOT NULL, request_id TEXT, "
            "context_input_tokens INTEGER)"
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(context_usage_events)")}
        if "request_id" not in columns:
            db.execute("ALTER TABLE context_usage_events ADD COLUMN request_id TEXT")
        if "context_input_tokens" not in columns:
            db.execute("ALTER TABLE context_usage_events ADD COLUMN context_input_tokens INTEGER")
        db.execute("CREATE TABLE IF NOT EXISTS context_usage_request_ids (request_id TEXT PRIMARY KEY)")

    def record(self, report: dict) -> None:
        """Atomically count one completed preparation, including zero/negative reduction."""
        usable = report["usable"]
        request_id = report.get("request_id")
        context_input_tokens = report.get("context_input_tokens")
        if context_input_tokens is not None and (
            isinstance(context_input_tokens, bool) or not isinstance(context_input_tokens, int)
            or context_input_tokens < 0
        ):
            raise ValueError("context_input_tokens must be a nonnegative integer or None.")
        if request_id is not None and (
            not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 256
            or any(ord(char) < 32 for char in request_id)
        ):
            raise ValueError("request_id must be a nonempty single-line identifier.")
        values = (
            datetime.now(timezone.utc).date().isoformat(), report["counter"], 1,
            int(usable), int(usable and report["reduced_tokens"] < 0),
            report["input_tokens"] if usable else 0,
            report["memory_tokens"] if usable else 0,
        )
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._schema(db)
            if request_id is not None:
                inserted = db.execute("INSERT OR IGNORE INTO context_usage_request_ids VALUES (?)",
                                      (request_id,)).rowcount
                if not inserted:
                    return
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
                "(recorded_at,counter,input_tokens,memory_tokens,usable,request_id,context_input_tokens) "
                "VALUES (?,?,?,?,?,?,?)",
                (recorded_at, report["counter"], report["input_tokens"],
                 report["memory_tokens"], int(usable), request_id, context_input_tokens),
            )
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

    def event_cursor(self) -> int:
        """Read the current position without loading or replaying historical events."""
        if not self.path.exists():
            return 0
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=0.2)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='context_usage_events'").fetchone():
                return 0
            return db.execute("SELECT COALESCE(MAX(seq),0) FROM context_usage_events").fetchone()[0]

    def recent_events(self, after: int = 0, *, limit: int | None = None) -> list[dict]:
        """Numeric-only event stream; callers can page without losing burst events."""
        if isinstance(after, bool) or not isinstance(after, int) or after < 0:
            raise ValueError("after must be a nonnegative integer.")
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise ValueError("limit must be a positive integer or None.")
        if not self.path.exists():
            return []
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True,
                                     timeout=0.2)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='context_usage_events'").fetchone():
                return []
            columns = {row[1] for row in db.execute("PRAGMA table_info(context_usage_events)")}
            request_column = "request_id" if "request_id" in columns else "NULL"
            context_column = "context_input_tokens" if "context_input_tokens" in columns else "NULL"
            rows = db.execute("SELECT seq,recorded_at,counter,input_tokens,memory_tokens,usable,"
                              + request_column + "," + context_column + " "
                              "FROM context_usage_events WHERE seq>? ORDER BY seq LIMIT ?",
                              (after, limit if limit is not None else -1)).fetchall()
        return [{"seq": seq, "recorded_at": at, "counter": counter,
                 "input_tokens": before, "memory_tokens": after_tokens, "usable": bool(usable),
                 "reduced_tokens": before-after_tokens if usable else None, "request_id": request_id,
                 "context_input_tokens": context_input_tokens}
                for seq, at, counter, before, after_tokens, usable, request_id, context_input_tokens in rows]

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
            # Keep the legacy latest table shape: already-running MCP writers
            # use INSERT ... VALUES without naming columns. Match its snapshot
            # to the event, never borrow context length from an older request.
            latest_context_input_tokens = None
            event_columns = {row[1] for row in db.execute("PRAGMA table_info(context_usage_events)")}
            if latest and "context_input_tokens" in event_columns:
                event = db.execute(
                    "SELECT recorded_at,counter,input_tokens,memory_tokens,usable,context_input_tokens "
                    "FROM context_usage_events ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                if event and event[:5] == latest:
                    latest_context_input_tokens = event[5]
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
                "context_input_tokens": latest_context_input_tokens,
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
