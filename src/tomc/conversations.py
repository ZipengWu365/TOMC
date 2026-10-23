"""Group saved context snapshots under the conversations they came from."""

from __future__ import annotations

from .conversation_names import folder


def conversation_key(record):
    """("session", host, id) for a local chat, ("imported", ...) or ("unlinked", ...)."""
    host, session = record.get("host"), record.get("session_id")
    if session:
        return ("session", host, session)
    if not host and (record.get("origin_host") or record.get("origin_session_id")):
        return ("imported", record.get("origin_host"), record.get("origin_session_id"))
    return ("unlinked", host, None)


def group_conversations(records, *, names=None, savings=None, sessions=None, imported=None):
    """Conversations, most recently active first.

    ``records`` come newest first from ``ContextLibrary.list``. ``names`` maps
    ``(host, session_id)`` to host-provided names, ``savings`` maps request IDs to
    ``request_savings`` rows, ``sessions`` maps ``(host, session_id)`` to registered
    TOMC sessions and ``imported`` maps snapshot IDs to names carried in bundles.
    A local conversation's savings cover every compiled request of that chat; other
    groups fall back to their snapshots' own context estimates.
    """
    names, savings = names or {}, savings or {}
    sessions, imported = sessions or {}, imported or {}
    by_session = {}
    for row in savings.values():
        by_session.setdefault((row.get("host"), row.get("session_id")), []).append(row)
    groups = {}
    for record in records:
        key = conversation_key(record)
        kind, host, session = key
        group = groups.get(key)
        if group is None:
            name = names.get((host, session), {}) if kind == "session" else {}
            registered = sessions.get((host, session)) if kind == "session" else None
            group = groups[key] = {
                "key": key,
                "kind": kind,
                "host": host,
                "session_id": session,
                "title": name.get("title"),
                "folder": name.get("folder") or folder((registered or {}).get("project")),
                "agent": name.get("agent"),
                "records": [],
                "latest_utc": record.get("created_utc"),
                "enabled": None if registered is None else bool(registered.get("enabled", True)),
            }
        if kind == "imported" and not group["title"]:
            group["title"] = imported.get(record.get("id"))
        group["records"].append({**record, "request": savings.get(record.get("preparation_id"))})
    result = []
    for group in groups.values():
        # The first task of a chat names it when the host has no name for it.
        group["first_title"] = group["records"][-1].get("title")
        rows = (
            by_session.get((group["host"], group["session_id"]))
            if group["kind"] == "session"
            else None
        )
        if rows:
            group["tokens_saved"] = sum(row["tokens_saved"] for row in rows)
            priced = [row["money"] for row in rows if row["money"] is not None]
            group["money"] = sum(priced) if priced else None
            group["requests"] = len(rows)
        else:
            group["tokens_saved"] = sum(record["reduced_tokens"] for record in group["records"])
            group["money"] = None
            group["requests"] = 0
        result.append(group)
    return sorted(result, key=lambda group: group["latest_utc"] or "", reverse=True)
