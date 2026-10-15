"""Local named notebooks for explicit MCP saves; no automatic transcript collection."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .easy import PreparedContext, prepare_context
from .input import MAX_INPUT_CHARS, parse_history
from .schemas import Message


def default_store_path() -> Path:
    """Resolve the configurable user-local database outside the repository."""
    return (
        Path(os.environ.get("TOMC_MEMORY_PATH", str(Path.home() / ".tomc/memory.sqlite3")))
        .expanduser()
        .absolute()
    )


class MemoryStore:
    """Append exact submitted text, isolate notebooks by name, and replay on recall."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path is not None else default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        with self._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"
            )
            db.execute("CREATE INDEX IF NOT EXISTS entries_name ON entries(name, id)")

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _name(name: str) -> str:
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name) > 120
            or any(ord(c) < 32 for c in name)
        ):
            raise ValueError("Choose a notebook name of 1–120 characters.")
        return name.strip()

    @staticmethod
    def _messages(rows) -> list[Message]:
        return [Message(**m) for row in rows for m in json.loads(row[0])]

    def remember(self, name: str, content: str) -> dict:
        """Append one submitted history, deduplicating an immediate exact retry."""
        name = self._name(name)
        parsed = parse_history(content)
        messages = [Message(parsed)] if isinstance(parsed, str) else parsed
        if not messages or not any(m.content.strip() for m in messages):
            raise ValueError("There is no text to remember.")
        payload = json.dumps([asdict(m) for m in messages], ensure_ascii=False)
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT payload FROM entries WHERE name=? ORDER BY id", (name,)
            ).fetchall()
            duplicate = bool(rows and rows[-1][0] == payload)
            if not duplicate:
                all_messages = self._messages(rows) + messages
                if sum(len(m.content) + len(m.role) + 16 for m in all_messages) > MAX_INPUT_CHARS:
                    raise ValueError(
                        "Notebook is full (200,000 characters). Start a new named notebook; nothing was deleted."
                    )
                db.execute("INSERT INTO entries(name,payload) VALUES (?,?)", (name, payload))
            return {"name": name, "saved": not duplicate, "entries": len(rows) + (not duplicate)}

    def recall(self, name: str, task: str, budget: int | None = None) -> PreparedContext:
        """Read only the chosen notebook and compile for the supplied next task.

        Without a budget, about 80% of the notebook's estimated tokens are kept."""
        with self._connection() as db:
            rows = db.execute(
                "SELECT payload FROM entries WHERE name=? ORDER BY id", (self._name(name),)
            ).fetchall()
        if not rows:
            raise ValueError("Notebook not found. List notebooks or save some memory first.")
        return prepare_context(self._messages(rows), task, budget)

    def list(self) -> list[dict]:
        """Return notebook names and counts, without returning their contents."""
        with self._connection() as db:
            rows = db.execute(
                "SELECT name, count(*), max(created) FROM entries GROUP BY name ORDER BY max(id) DESC"
            ).fetchall()
        return [{"name": n, "entries": count, "updated": updated} for n, count, updated in rows]

    def forget(self, name: str) -> dict:
        """Delete only the explicitly named notebook; no wildcard deletion."""
        name = self._name(name)
        with self._connection() as db:
            deleted = db.execute("DELETE FROM entries WHERE name=?", (name,)).rowcount
        return {"name": name, "deleted_entries": deleted}
