"""User-wide controls and explicitly attributed sessions, without chat contents."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .privacy import DEFAULT_RETENTION_DAYS, connect

# Preferences live in their own name/value table so older TOMC Memory processes that
# share this database keep writing their two-column switch row unchanged.
PREFERENCES = {
    # MCP prepare_context/recall_memory results are saved only after the user opts in.
    "save_mcp_results": False,
    # Days that automatically saved snapshots and Claude replay data are kept.
    "retention_days": DEFAULT_RETENTION_DAYS,
}
MAX_RETENTION_DAYS = 3650


def _text(value: str, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(char) < 32 for char in value)
    ):
        raise ValueError(f"{label} must be nonempty text of at most {maximum} characters.")
    return value.strip()


def _identity(host: str, session_id: str) -> tuple[str, str]:
    host = _text(host, "host", 64)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", host):
        raise ValueError("Use a stable host name such as codex or claude_code.")
    return host, _text(session_id, "session_id", 256)


def _boolean(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean.")
    return value


def _retention(value: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_RETENTION_DAYS
    ):
        raise ValueError(f"retention_days must be an integer from 1 to {MAX_RETENTION_DAYS}.")
    return value


def preference(db, name: str):
    """One stored preference, or its default when unset or unreadable."""
    default = PREFERENCES[name]
    try:
        row = db.execute("SELECT value FROM tomc_preferences WHERE name=?", (name,)).fetchone()
    except sqlite3.Error:
        row = None
    if row is None:
        return default
    if isinstance(default, bool):
        return bool(row[0])
    try:
        return _retention(row[0])
    except ValueError:
        return default


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000:
        raise ValueError("limit must be an integer from 1 to 10000.")
    return value


class SessionStore:
    """Share switches across processes; never infer identity from the active row."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    @staticmethod
    def _schema(db):
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_settings ("
            "id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL, "
            "save_contexts INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_sessions ("
            "host TEXT NOT NULL, session_id TEXT NOT NULL, title TEXT, project TEXT, "
            "enabled INTEGER NOT NULL DEFAULT 1, first_seen TEXT NOT NULL, "
            "last_seen TEXT NOT NULL, event TEXT NOT NULL, PRIMARY KEY(host,session_id))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_active_session ("
            "id INTEGER PRIMARY KEY CHECK(id=1), host TEXT NOT NULL, "
            "session_id TEXT NOT NULL, event_seq INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS tomc_preferences ("
            "name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
        )

    @contextmanager
    def _write(self):
        db = connect(self.path, timeout=30)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                self._schema(db)
                yield db
        finally:
            db.close()

    @contextmanager
    def _read(self):
        if not self.path.exists():
            yield None
            return
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            db.execute("BEGIN")
            yield db
        finally:
            db.close()

    @staticmethod
    def _has(db, table):
        return (
            db is not None
            and db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            is not None
        )

    @classmethod
    def _settings(cls, db):
        row = (
            db.execute("SELECT enabled,save_contexts FROM tomc_settings WHERE id=1").fetchone()
            if cls._has(db, "tomc_settings")
            else None
        )
        stored = cls._has(db, "tomc_preferences")
        return {
            "enabled": bool(row[0]) if row else True,
            "save_contexts": bool(row[1]) if row else True,
            **{
                name: preference(db, name) if stored else default
                for name, default in PREFERENCES.items()
            },
        }

    def settings(self) -> dict:
        """Read the authorized defaults without creating a database."""
        with self._read() as db:
            return self._settings(db)

    def erase_generation(self) -> int:
        """Changes after each erase-all, so other processes drop what they hold in memory."""
        with self._read() as db:
            if not self._has(db, "tomc_preferences"):
                return 0
            row = db.execute(
                "SELECT value FROM tomc_preferences WHERE name='erase_generation'"
            ).fetchone()
            return int(row[0]) if row else 0

    def update_settings(
        self, enabled=None, save_contexts=None, save_mcp_results=None, retention_days=None
    ) -> dict:
        for value, label in (
            (enabled, "enabled"),
            (save_contexts, "save_contexts"),
            (save_mcp_results, "save_mcp_results"),
        ):
            if value is not None:
                _boolean(value, label)
        if retention_days is not None:
            _retention(retention_days)
        if all(
            value is None for value in (enabled, save_contexts, save_mcp_results, retention_days)
        ):
            return self.settings()
        with self._write() as db:
            settings = self._settings(db)
            if enabled is not None or save_contexts is not None:
                if enabled is not None:
                    settings["enabled"] = enabled
                if save_contexts is not None:
                    settings["save_contexts"] = save_contexts
                db.execute(
                    "INSERT INTO tomc_settings VALUES (1,?,?) ON CONFLICT(id) "
                    "DO UPDATE SET enabled=excluded.enabled,save_contexts=excluded.save_contexts",
                    (int(settings["enabled"]), int(settings["save_contexts"])),
                )
            for name, value in (
                ("save_mcp_results", save_mcp_results),
                ("retention_days", retention_days),
            ):
                if value is not None:
                    settings[name] = value
                    db.execute(
                        "INSERT INTO tomc_preferences VALUES (?,?) ON CONFLICT(name) "
                        "DO UPDATE SET value=excluded.value",
                        (name, int(value)),
                    )
            return settings

    @staticmethod
    def _record(row, settings):
        host, session_id, title, project, enabled, first_seen, last_seen, event = row
        return {
            "host": host,
            "session_id": session_id,
            "title": title,
            "project": project,
            "enabled": bool(enabled),
            "effective_enabled": settings["enabled"] and bool(enabled),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "event": event,
        }

    @staticmethod
    def _row(db, host, session_id):
        return db.execute(
            "SELECT host,session_id,title,project,enabled,first_seen,last_seen,event "
            "FROM tomc_sessions WHERE host=? AND session_id=?",
            (host, session_id),
        ).fetchone()

    def register(
        self, host, session_id, *, title=None, project=None, event="activity", activate=True
    ) -> dict:
        """Register explicit host metadata; preserve a session's disabled choice."""
        host, session_id = _identity(host, session_id)
        title = _text(title, "title", 500) if title is not None else None
        project = _text(project, "project", 4096) if project is not None else None
        event = _text(event, "event", 80)
        _boolean(activate, "activate")
        now = datetime.now(timezone.utc).isoformat()
        with self._write() as db:
            db.execute(
                "INSERT INTO tomc_sessions VALUES (?,?,?,?,1,?,?,?) "
                "ON CONFLICT(host,session_id) DO UPDATE SET "
                "title=COALESCE(excluded.title,title),project=COALESCE(excluded.project,project),"
                "last_seen=excluded.last_seen,event=excluded.event",
                (host, session_id, title, project, now, now, event),
            )
            if activate:
                previous = db.execute(
                    "SELECT host,session_id,event_seq FROM tomc_active_session WHERE id=1"
                ).fetchone()
                if previous is None or previous[:2] != (host, session_id):
                    sequence = previous[2] + 1 if previous else 1
                    db.execute(
                        "INSERT INTO tomc_active_session VALUES (1,?,?,?) ON CONFLICT(id) "
                        "DO UPDATE SET host=excluded.host,session_id=excluded.session_id,"
                        "event_seq=excluded.event_seq",
                        (host, session_id, sequence),
                    )
            return self._record(self._row(db, host, session_id), self._settings(db))

    def list(self, limit=100) -> list[dict]:
        limit = _limit(limit)
        with self._read() as db:
            if not self._has(db, "tomc_sessions"):
                return []
            settings = self._settings(db)
            rows = db.execute(
                "SELECT host,session_id,title,project,enabled,first_seen,last_seen,event "
                "FROM tomc_sessions ORDER BY last_seen DESC,host,session_id LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._record(row, settings) for row in rows]

    def get(self, host, session_id) -> dict | None:
        """Look up one explicit identity without list limits or database creation."""
        host, session_id = _identity(host, session_id)
        with self._read() as db:
            if not self._has(db, "tomc_sessions"):
                return None
            row = self._row(db, host, session_id)
            return self._record(row, self._settings(db)) if row is not None else None

    def requires_identity(self) -> bool:
        """Unattributed preparation must not bypass an existing per-session pause."""
        with self._read() as db:
            if not self._has(db, "tomc_sessions"):
                return False
            return bool(
                db.execute("SELECT EXISTS(SELECT 1 FROM tomc_sessions WHERE enabled=0)").fetchone()[
                    0
                ]
            )

    def set_enabled(self, host, session_id, enabled) -> dict:
        host, session_id = _identity(host, session_id)
        _boolean(enabled, "enabled")
        now = datetime.now(timezone.utc).isoformat()
        with self._write() as db:
            db.execute(
                "INSERT INTO tomc_sessions VALUES (?,?,NULL,NULL,?,?,?,'setting') "
                "ON CONFLICT(host,session_id) DO UPDATE SET enabled=excluded.enabled",
                (host, session_id, int(enabled), now, now),
            )
            return self._record(self._row(db, host, session_id), self._settings(db))

    def effective_enabled(self, host=None, session_id=None) -> bool:
        """Unknown attribution uses only the global switch, never the active UI row."""
        identity = (
            _identity(host, session_id) if host is not None and session_id is not None else None
        )
        with self._read() as db:
            if not self._settings(db)["enabled"]:
                return False
            if identity is None or not self._has(db, "tomc_sessions"):
                return True
            row = self._row(db, *identity)
            return bool(row[4]) if row else True

    def active(self) -> dict | None:
        """Last explicitly activated session; the sequence changes only on a switch."""
        with self._read() as db:
            if not self._has(db, "tomc_active_session") or not self._has(db, "tomc_sessions"):
                return None
            active = db.execute(
                "SELECT host,session_id,event_seq FROM tomc_active_session WHERE id=1"
            ).fetchone()
            if active is None:
                return None
            row = self._row(db, active[0], active[1])
            if row is None:
                return None
            return {**self._record(row, self._settings(db)), "event_seq": active[2]}
