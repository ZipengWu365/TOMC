"""Numeric-only request lifecycle observations, separate from preparation estimates."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATES = {"preparing", "prepared", "forwarded", "passthrough", "failed"}
SCOPE = (
    "Observed local-proxy request stages. Before/after are lexical estimates; provider usage "
    "is observed usage only, not a counterfactual saving or a billing difference. "
    "Context input is the estimated history submitted to a new compilation, when known. "
    "Protocol detail holds structural host facts only, never request content."
)
# Structural facts a host declares about a request: kind, compaction trigger/phase,
# compaction generation and opaque-item counts. Never message text or identifiers.
DETAIL_KEYS = {
    "request_kind",
    "request_class",
    "compaction_trigger",
    "compaction_phase",
    "compaction_reason",
    "window",
    "history_initialization",
    "compaction_items",
    "compaction_trigger_item",
    "agent",
    "endpoint",
}
_DETAIL_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,40}\Z")
# A request's declared model ID, e.g. gpt-6-astra or claude-opus-5-5[1m]; it prices savings.
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@\[\]+-]{0,127}\Z")


def model_id(value):
    """A short model identifier, or None for anything else (never stored)."""
    return value if isinstance(value, str) and _MODEL.fullmatch(value) else None


def protocol_detail(value):
    """Keep allowlisted keys with short codes, booleans or small counts; drop the rest.

    Dropping instead of raising keeps the request's state record even when a host
    sends an unexpected value; nothing outside the allowlist is ever stored.
    """
    if not isinstance(value, dict):
        return None
    clean = {}
    for key in sorted(DETAIL_KEYS & set(value)):
        item = value[key]
        if (
            type(item) is bool
            or (type(item) is int and 0 <= item <= 1_000_000_000)
            or (isinstance(item, str) and _DETAIL_CODE.fullmatch(item))
        ):
            clean[key] = item
    return clean or None


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _text(value, label, *, optional=False):
    if value is None and optional:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{label} must be nonempty single-line text of at most 256 characters.")
    return value


def _number(value, label):
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"{label} must be a nonnegative integer or None.")
    return value


class RequestActivity:
    """Record preparation separately from dispatch and eventual provider usage.

    ``start`` begins CPU eligibility/preparation. ``finish(state='prepared')`` ends
    that CPU phase before transport. ``sent`` records observed upstream dispatch,
    after which ``usage`` can add response metadata without making the pet busy.
    ``finish(state='forwarded')`` is allowed only when the caller already verified
    dispatch. The store cannot independently verify a caller's transport evidence.
    IDs should be unique per outbound attempt; retries must not reuse a completed ID.
    No request bodies, headers, prompts, API keys or provider outputs are stored.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @staticmethod
    def _schema(db):
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_request_activity ("
            "request_id TEXT PRIMARY KEY, host TEXT NOT NULL, session_id TEXT, "
            "state TEXT NOT NULL, reason TEXT, started_utc TEXT NOT NULL, "
            "updated_utc TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0, "
            "before_tokens INTEGER, after_tokens INTEGER, "
            "provider_input_tokens INTEGER, provider_cached_tokens INTEGER, context_input_tokens INTEGER)"
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(tomc_request_activity)")}
        if "context_input_tokens" not in columns:
            db.execute("ALTER TABLE tomc_request_activity ADD COLUMN context_input_tokens INTEGER")
        if "protocol_detail" not in columns:
            db.execute("ALTER TABLE tomc_request_activity ADD COLUMN protocol_detail TEXT")
        if "model" not in columns:
            db.execute("ALTER TABLE tomc_request_activity ADD COLUMN model TEXT")
        db.execute(
            "CREATE INDEX IF NOT EXISTS tomc_request_activity_updated "
            "ON tomc_request_activity(updated_utc)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_context_prepared_events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE, "
            "context_input_tokens INTEGER NOT NULL, prepared_utc TEXT NOT NULL)"
        )

    @contextmanager
    def _read(self):
        if not self.path.exists():
            yield None
            return
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN")
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                self._schema(db)
                yield db
        finally:
            db.close()

    @staticmethod
    def _has(db):
        return (
            db is not None
            and db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tomc_request_activity'"
            ).fetchone()
            is not None
        )

    @staticmethod
    def _record(row):
        if row is None:
            return None
        result = dict(row)
        result.setdefault("context_input_tokens", None)
        result.setdefault("model", None)
        try:
            result["protocol_detail"] = protocol_detail(
                json.loads(result.get("protocol_detail") or "null")
            )
        except (TypeError, ValueError):
            result["protocol_detail"] = None
        result["sent"] = bool(result["sent"])
        before, after = result["before_tokens"], result["after_tokens"]
        result["estimated_reduced_tokens"] = (
            before - after if before is not None and after is not None else None
        )
        result["scope"] = SCOPE
        return result

    @staticmethod
    def _row(db, request_id):
        row = db.execute(
            "SELECT * FROM tomc_request_activity WHERE request_id=?", (request_id,)
        ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return row

    def start(self, request_id, host, session_id=None):
        request_id = _text(request_id, "request_id")
        host = _text(host, "host")
        session_id = _text(session_id, "session_id", optional=True)
        stamp = _stamp()
        with self._write() as db:
            # An idempotent repeated start must not restart completed work or move identity.
            existing = db.execute(
                "SELECT * FROM tomc_request_activity WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing is not None:
                if existing["host"] != host or existing["session_id"] != session_id:
                    raise ValueError("A request ID cannot be reused for a different identity.")
                return self._record(existing)
            db.execute(
                "INSERT INTO tomc_request_activity "
                "(request_id,host,session_id,state,started_utc,updated_utc) VALUES (?,?,?,'preparing',?,?)",
                (request_id, host, session_id, stamp, stamp),
            )
            return self._record(self._row(db, request_id))

    def finish(
        self,
        request_id,
        *,
        state,
        reason=None,
        before_tokens=None,
        after_tokens=None,
        provider_input_tokens=None,
        provider_cached_tokens=None,
        context_input_tokens=None,
        detail=None,
        model=None,
    ):
        if state not in STATES - {"preparing"}:
            raise ValueError("Use prepared, forwarded, passthrough or failed.")
        request_id = _text(request_id, "request_id")
        if reason is not None and (
            not isinstance(reason, str) or not re.fullmatch(r"[\w.:-]{1,120}", reason)
        ):
            raise ValueError("reason must be a short code, not request content or exception text.")
        values = [
            _number(value, name)
            for name, value in (
                ("before_tokens", before_tokens),
                ("after_tokens", after_tokens),
                ("provider_input_tokens", provider_input_tokens),
                ("provider_cached_tokens", provider_cached_tokens),
                ("context_input_tokens", context_input_tokens),
            )
        ]
        detail = protocol_detail(detail)
        encoded = json.dumps(detail, sort_keys=True, separators=(",", ":")) if detail else None
        with self._write() as db:
            old = self._row(db, request_id)
            if old["state"] != "preparing" and state == "prepared":
                if old["state"] == "prepared":
                    return self._record(old)
                raise ValueError("A finished request cannot return to the prepared stage.")
            db.execute(
                "UPDATE tomc_request_activity SET state=?,reason=?,updated_utc=?, "
                "sent=CASE WHEN ?='forwarded' THEN 1 ELSE sent END, "
                "before_tokens=COALESCE(?,before_tokens),after_tokens=COALESCE(?,after_tokens), "
                "provider_input_tokens=COALESCE(?,provider_input_tokens), "
                "provider_cached_tokens=COALESCE(?,provider_cached_tokens), "
                "context_input_tokens=COALESCE(?,context_input_tokens), "
                "protocol_detail=COALESCE(?,protocol_detail),model=COALESCE(?,model) "
                "WHERE request_id=?",
                (state, reason, _stamp(), state, *values, encoded, model_id(model), request_id),
            )
            if state in {"prepared", "forwarded"} and context_input_tokens is not None:
                # A durable ordered event, independent of later requests and
                # provider completion. Repeated finish calls cannot replay it.
                db.execute(
                    "INSERT OR IGNORE INTO tomc_context_prepared_events "
                    "(request_id,context_input_tokens,prepared_utc) VALUES (?,?,?)",
                    (request_id, context_input_tokens, _stamp()),
                )
            return self._record(self._row(db, request_id))

    def prepared_cursor(self):
        """Current stream position; a reader never backfills historical activity."""
        with self._read() as db:
            if (
                db is None
                or not db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tomc_context_prepared_events'"
                ).fetchone()
            ):
                return 0
            return db.execute(
                "SELECT COALESCE(MAX(seq),0) FROM tomc_context_prepared_events"
            ).fetchone()[0]

    def prepared_events(self, after_seq=0, limit=500):
        """Read every new compilation in durable order, including concurrent ones."""
        if isinstance(after_seq, bool) or not isinstance(after_seq, int) or after_seq < 0:
            raise ValueError("after_seq must be a nonnegative integer.")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer.")
        with self._read() as db:
            if (
                db is None
                or not db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tomc_context_prepared_events'"
                ).fetchone()
            ):
                return []
            return [
                dict(row)
                for row in db.execute(
                    "SELECT seq,request_id,context_input_tokens,prepared_utc "
                    "FROM tomc_context_prepared_events WHERE seq>? ORDER BY seq LIMIT ?",
                    (after_seq, limit),
                )
            ]

    def sent(self, request_id):
        """Caller observed dispatch; passthrough remains visibly unmodified."""
        request_id = _text(request_id, "request_id")
        with self._write() as db:
            row = self._row(db, request_id)
            if row["state"] not in {"prepared", "forwarded", "passthrough"}:
                raise ValueError("Finish preparation before recording dispatch.")
            db.execute(
                "UPDATE tomc_request_activity SET state=?,sent=1,updated_utc=? WHERE request_id=?",
                ("forwarded" if row["state"] == "prepared" else row["state"], _stamp(), request_id),
            )
            return self._record(self._row(db, request_id))

    def usage(self, request_id, *, provider_input_tokens=None, provider_cached_tokens=None):
        """Attach final provider counts once available; missing values stay unknown."""
        request_id = _text(request_id, "request_id")
        before = _number(provider_input_tokens, "provider_input_tokens")
        cached = _number(provider_cached_tokens, "provider_cached_tokens")
        with self._write() as db:
            row = self._row(db, request_id)
            if not row["sent"]:
                raise ValueError("Provider usage requires observed upstream dispatch.")
            db.execute(
                "UPDATE tomc_request_activity SET provider_input_tokens=COALESCE(?,provider_input_tokens), "
                "provider_cached_tokens=COALESCE(?,provider_cached_tokens),updated_utc=? WHERE request_id=?",
                (before, cached, _stamp(), request_id),
            )
            return self._record(self._row(db, request_id))

    def active(self, stale_after_seconds=120):
        """Latest CPU preparation, never the whole model-generation/stream lifetime.

        Old interrupted starts expire from the busy indicator without inventing a
        successful finish. They remain inspectable in ``last`` and the summary.
        """
        if (
            isinstance(stale_after_seconds, bool)
            or not isinstance(stale_after_seconds, int)
            or stale_after_seconds < 1
        ):
            raise ValueError("stale_after_seconds must be a positive integer.")
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)).isoformat()
        with self._read() as db:
            if not self._has(db):
                return None
            row = db.execute(
                "SELECT * FROM tomc_request_activity WHERE state='preparing' AND updated_utc>=? "
                "ORDER BY started_utc DESC,request_id DESC LIMIT 1",
                (cutoff,),
            ).fetchone()
            record = self._record(row)
            if record:
                record["active_count"] = db.execute(
                    "SELECT COUNT(*) FROM tomc_request_activity "
                    "WHERE state='preparing' AND updated_utc>=?",
                    (cutoff,),
                ).fetchone()[0]
            return record

    def last(self):
        with self._read() as db:
            if not self._has(db):
                return None
            return self._record(
                db.execute(
                    "SELECT * FROM tomc_request_activity "
                    "ORDER BY started_utc DESC,request_id DESC LIMIT 1"
                ).fetchone()
            )

    def summary(self):
        result = {
            "scope": SCOPE,
            "total_requests": 0,
            "sent_requests": 0,
            "counts": {state: 0 for state in sorted(STATES)},
            "provider_usage_requests": 0,
            "provider_input_tokens": None,
            "provider_cached_tokens": None,
            "by_host": [],
        }
        with self._read() as db:
            if not self._has(db):
                return result
            for state, count in db.execute(
                "SELECT state,COUNT(*) FROM tomc_request_activity GROUP BY state"
            ):
                result["counts"][state] = count
                result["total_requests"] += count
            row = db.execute(
                "SELECT SUM(sent),COUNT(provider_input_tokens),SUM(provider_input_tokens), "
                "SUM(provider_cached_tokens) FROM tomc_request_activity"
            ).fetchone()
            result.update(
                sent_requests=row[0] or 0,
                provider_usage_requests=row[1],
                provider_input_tokens=row[2],
                provider_cached_tokens=row[3],
            )
            for row in db.execute(
                "SELECT host,COUNT(*),SUM(sent),COUNT(provider_input_tokens), "
                "SUM(provider_input_tokens),SUM(provider_cached_tokens) "
                "FROM tomc_request_activity GROUP BY host ORDER BY host"
            ):
                result["by_host"].append(
                    dict(
                        zip(
                            (
                                "host",
                                "requests",
                                "sent_requests",
                                "provider_usage_requests",
                                "provider_input_tokens",
                                "provider_cached_tokens",
                            ),
                            row,
                        )
                    )
                )
        return result
