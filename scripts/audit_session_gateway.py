"""Read gateway evidence for explicit chat IDs; never send a prompt or change settings.

Examples:
  python scripts/audit_session_gateway.py --session-id THREAD_ID
  python scripts/audit_session_gateway.py --sessions-json selected_sessions.json

JSON selections are a list of IDs (using --host), a list of {host, session_id}
objects, or {"sessions": [...]} containing either form. Output is JSON on stdout.
Registration or an enabled switch is not evidence that a model request arrived.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

HOSTS = {"codex", "claude"}
STATES = {"preparing", "prepared", "forwarded", "passthrough", "failed"}
SCOPE = (
    "Only explicitly selected IDs are queried. observed means a gateway request record exists, "
    "not merely configuration or session registration. Prepared events record compilation, "
    "not dispatch, model success, visible animation, foreground focus or billed savings. "
    "Missing legacy event tables mean preparation evidence is unavailable, not zero compilations. "
    "Animation receipts show what one pet UI process did with each prepared event "
    "(queued/started/completed/skipped/interrupted), not that the user saw it."
)
DETAIL_KEYS = {"request_kind", "request_class", "compaction_trigger", "compaction_phase",
               "compaction_reason", "window", "history_initialization", "compaction_items",
               "compaction_trigger_item", "agent", "endpoint"}
RECEIPT_EVENTS = {"queued", "started", "completed", "skipped", "interrupted"}


def _identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", value) else None


def selections(ids, manifest=None, host="codex"):
    rows = list(ids)
    if manifest is not None:
        if manifest.stat().st_size > 1_000_000:
            raise ValueError("invalid_selection")
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        data = data.get("sessions") if isinstance(data, dict) else data
        if not isinstance(data, list):
            raise ValueError("invalid_selection")
        rows.extend(data)
    if not rows or len(rows) > 1000:
        raise ValueError("invalid_selection")
    result = []
    for row in rows:
        selected_host = row.get("host", host) if isinstance(row, dict) else host
        session_id = row.get("session_id") if isinstance(row, dict) else row
        if selected_host not in HOSTS or _identifier(session_id) is None:
            raise ValueError("invalid_selection")
        identity = (selected_host, session_id)
        if identity not in result:
            result.append(identity)
    return result


def _empty(host, session_id, *, unknown=False):
    return {
        "host": host, "session_id": session_id,
        "observed": None if unknown else False,
        "registered": None if unknown else False,
        "switch": {
            "global_enabled": None if unknown else True,
            "global_source": "unknown" if unknown else "default",
            "session_enabled": None if unknown else True,
            "session_source": "unknown" if unknown else "default",
            "effective_enabled": None if unknown else True,
        },
        "request_count": None if unknown else 0,
        "sent_request_count": None if unknown else 0,
        "provider_usage_request_count": None if unknown else 0,
        "reason_counts": None if unknown else {},
        "last_request": None,
        "prepared_event_stream_available": None if unknown else False,
        "prepared_event_count": None, "prepared_events": [],
        "prepared_events_truncated": False,
    }


def _number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9T:Z.+-]{10,40}", value):
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        return None


def _reason(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", value) else None


def _detail(value):
    """Structural host facts only; anything outside the allowlist is dropped."""
    try:
        data = json.loads(value) if isinstance(value, str) else None
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    clean = {key: item for key, item in sorted(data.items()) if key in DETAIL_KEYS and (
        type(item) is bool or (type(item) is int and item >= 0) or (
            isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,40}", item)))}
    return clean or None


def _request(row):
    if row is None:
        return None
    record = {"request_id": _identifier(row["request_id"]),
              "state": row["state"] if row["state"] in STATES else "unknown",
              "reason": _reason(row["reason"]),
              "sent": bool(row["sent"])}
    for name in ("started_utc", "updated_utc"):
        record[name] = _timestamp(row[name])
    for name in ("before_tokens", "after_tokens", "context_input_tokens",
                 "provider_input_tokens", "provider_cached_tokens"):
        record[name] = _number(row[name])
    record["protocol_detail"] = _detail(row["protocol_detail"])
    return record


def receipts(path, request_ids):
    """Animation receipts for the given request IDs, oldest first; missing file means none."""
    wanted, found = set(request_ids), {}
    for part in (path.with_name(path.name + ".1"), path):
        try:
            lines = part.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for text in lines:
            try:
                row = json.loads(text)
            except ValueError:
                continue
            if not isinstance(row, dict) or row.get("request_id") not in wanted \
                    or row.get("event") not in RECEIPT_EVENTS:
                continue
            entry = {"event": row["event"], "utc": _timestamp(row.get("utc")),
                     "ui": _identifier(row.get("ui"))}
            if type(row.get("stage")) is int and 1 <= row["stage"] <= 4:
                entry["stage"] = row["stage"]
            if _number(row.get("context_input_tokens")) is not None:
                entry["context_input_tokens"] = row["context_input_tokens"]
            if isinstance(row.get("reason"), str) and re.fullmatch(r"[a-z0-9_]{1,40}", row["reason"]):
                entry["reason"] = row["reason"]
            if row.get("demo") is True:
                entry["demo"] = True
            found.setdefault(row["request_id"], []).append(entry)
    return found


def _session(db, tables, identity, event_limit):
    host, session_id = identity
    result = _empty(host, session_id)
    setting = db.execute("SELECT enabled FROM tomc_settings WHERE id=1").fetchone() \
        if "tomc_settings" in tables else None
    session = db.execute("SELECT enabled FROM tomc_sessions WHERE host=? AND session_id=?",
                         identity).fetchone() if "tomc_sessions" in tables else None
    result["registered"] = session is not None
    result["switch"] = {
        "global_enabled": bool(setting[0]) if setting else True,
        "global_source": "stored" if setting else "default",
        "session_enabled": bool(session[0]) if session else True,
        "session_source": "registered" if session else "default",
        "effective_enabled": (bool(setting[0]) if setting else True) and
                             (bool(session[0]) if session else True),
    }
    if "tomc_request_activity" not in tables:
        return result
    count = db.execute(
        "SELECT COUNT(*),COALESCE(SUM(sent),0),COUNT(provider_input_tokens) "
        "FROM tomc_request_activity WHERE host=? AND session_id=?", identity).fetchone()
    result.update(observed=count[0] > 0, request_count=count[0],
                  sent_request_count=count[1], provider_usage_request_count=count[2])
    columns = {row[1] for row in db.execute("PRAGMA table_info(tomc_request_activity)")}
    context = "context_input_tokens" if "context_input_tokens" in columns else "NULL AS context_input_tokens"
    detail = "protocol_detail" if "protocol_detail" in columns else "NULL AS protocol_detail"
    row = db.execute(
        "SELECT request_id,state,reason,sent,started_utc,updated_utc,before_tokens,after_tokens,"
        "provider_input_tokens,provider_cached_tokens," + context + "," + detail + " "
        "FROM tomc_request_activity WHERE host=? AND session_id=? "
        "ORDER BY started_utc DESC,request_id DESC LIMIT 1", identity).fetchone()
    result["last_request"] = _request(row)
    result["reason_counts"] = {
        (_reason(reason) or "unknown"): count for reason, count in db.execute(
            "SELECT reason,COUNT(*) FROM tomc_request_activity WHERE host=? AND session_id=? "
            "GROUP BY reason ORDER BY COUNT(*) DESC,reason", identity)}
    if "tomc_context_prepared_events" in tables:
        result["prepared_event_stream_available"] = True
        join = (" FROM tomc_context_prepared_events p JOIN tomc_request_activity a "
                "ON a.request_id=p.request_id WHERE a.host=? AND a.session_id=? ")
        count = db.execute("SELECT COUNT(*)" + join, identity).fetchone()[0]
        result["prepared_event_count"] = count
        result["prepared_events_truncated"] = count > event_limit
        rows = db.execute("SELECT p.seq,p.request_id,p.context_input_tokens,p.prepared_utc" + join +
                          "ORDER BY p.seq DESC LIMIT ?", (*identity, event_limit)).fetchall()
        result["prepared_events"] = [
            {"seq": _number(row["seq"]), "request_id": _identifier(row["request_id"]),
             "context_input_tokens": _number(row["context_input_tokens"]),
             "prepared_utc": _timestamp(row["prepared_utc"])} for row in reversed(rows)]
    return result


def audit(store, identities, event_limit=20, receipts_path=None):
    """One consistent read transaction; no schema creation or content queries."""
    if not isinstance(event_limit, int) or isinstance(event_limit, bool) or not 1 <= event_limit <= 500:
        raise ValueError("invalid_event_limit")
    identities = selections([{"host": host, "session_id": session_id} for host, session_id in identities])
    report = {"schema_version": 2, "read_only": True,
              "checked_utc": datetime.now(timezone.utc).isoformat(), "scope": SCOPE,
              "store_status": "missing", "error_code": None, "prepared_event_limit": event_limit,
              "sessions": [_empty(*identity) for identity in identities]}
    try:
        store = Path(store)
        if not store.exists():
            return report
        with closing(sqlite3.connect(store.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            report["sessions"] = [_session(db, tables, identity, event_limit) for identity in identities]
            report["store_status"] = "available"
    except (OSError, sqlite3.Error):
        # Error messages can contain paths or malformed input; emit a fixed code.
        report.update(store_status="unavailable", error_code="store_unreadable",
                      sessions=[_empty(*identity, unknown=True) for identity in identities])
        return report
    path = Path(receipts_path) if receipts_path else store.with_name("animation_receipts.jsonl")
    ids = [event["request_id"] for session in report["sessions"] for event in session["prepared_events"]]
    found = receipts(path, ids) if ids else {}
    for session in report["sessions"]:
        for event in session["prepared_events"]:
            event["animation_receipts"] = found.get(event["request_id"], [])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc/memory.sqlite3")
    parser.add_argument("--host", choices=sorted(HOSTS), default="codex")
    parser.add_argument("--session-id", action="append", default=[])
    parser.add_argument("--sessions-json", type=Path)
    parser.add_argument("--event-limit", type=int, default=20)
    parser.add_argument("--receipts", type=Path, help="Animation receipt log (default: next to --store)")
    args = parser.parse_args(argv)
    try:
        identities = selections(args.session_id, args.sessions_json, args.host)
        report = audit(args.store, identities, args.event_limit, args.receipts)
    except (OSError, ValueError, TypeError):
        print(json.dumps({"read_only": True, "error_code": "invalid_selection_or_limit"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["store_status"] == "unavailable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
