"""Local named notebooks for explicit MCP saves; no automatic transcript collection."""

from __future__ import annotations

import json
import os
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .easy import PreparedContext, prepare_context
from .input import parse_history
from .privacy import connect, ensure_private_file, erase_all, tighten_permissions, vacuum
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
        ensure_private_file(self.path)
        tighten_permissions(self.path)
        with self._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"
            )
            db.execute("CREATE INDEX IF NOT EXISTS entries_name ON entries(name, id)")

    @contextmanager
    def _connection(self):
        db = connect(self.path, timeout=10)
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
        # One spelling per name: a composed and a decomposed "café" are the same notebook.
        return unicodedata.normalize("NFC", name.strip())

    @staticmethod
    def _resolve(db, name: str) -> str:
        """The stored notebook this name refers to; names match ignoring case.

        "Proj" finds an existing "proj", like a case-insensitive file system that keeps
        the first spelling. An exact match wins over a case-only one, and among several
        case-only matches (saved before names were matched this way) the oldest wins.
        """
        same_case = None
        for (stored,) in db.execute("SELECT name FROM entries GROUP BY name ORDER BY min(id)"):
            normal = unicodedata.normalize("NFC", stored)
            if normal == name:
                return stored
            if same_case is None and normal.casefold() == name.casefold():
                same_case = stored
        return same_case or name

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
            name = self._resolve(db, name)
            rows = db.execute(
                "SELECT payload FROM entries WHERE name=? ORDER BY id", (name,)
            ).fetchall()
            duplicate = bool(rows and rows[-1][0] == payload)
            if not duplicate:
                db.execute("INSERT INTO entries(name,payload) VALUES (?,?)", (name, payload))
            return {"name": name, "saved": not duplicate, "entries": len(rows) + (not duplicate)}

    def recall(
        self, name: str, task: str, budget: int | None = None, *, max_chars: int | None = None
    ) -> PreparedContext:
        """Read only the chosen notebook and compile for the supplied next task.

        Without a budget, 60-80% of the notebook's estimated tokens are kept
        (more compression for longer notebooks). ``max_chars`` fits the result to
        a client's tool-output limit, as in ``prepare_context``."""
        with self._connection() as db:
            name = self._resolve(db, self._name(name))
            rows = db.execute(
                "SELECT payload FROM entries WHERE name=? ORDER BY id", (name,)
            ).fetchall()
        if not rows:
            raise ValueError("Notebook not found. List notebooks or save some memory first.")
        return prepare_context(
            self._messages(rows), task, budget, adaptive=False, max_chars=max_chars
        )

    def list(self) -> list[dict]:
        """Return notebook names and counts, without returning their contents."""
        with self._connection() as db:
            rows = db.execute(
                "SELECT name, count(*), max(created) FROM entries GROUP BY name ORDER BY max(id) DESC"
            ).fetchall()
        return [{"name": n, "entries": count, "updated": updated} for n, count, updated in rows]

    def forget(self, name: str) -> dict:
        """Delete only the explicitly named notebook and the snapshots prepared from it."""
        from .context_library import ContextLibrary

        name = self._name(name)
        with self._connection() as db:
            name = self._resolve(db, name)
            deleted = db.execute("DELETE FROM entries WHERE name=?", (name,)).rowcount
        snapshots = ContextLibrary(self.path).delete_notebook(name)
        if deleted or snapshots:
            vacuum(self.path)
        return {"name": name, "deleted_entries": deleted, "deleted_snapshots": snapshots}

    def erase_all(self) -> dict:
        """Delete every notebook, saved snapshot and conversation record in this database."""
        return erase_all(self.path)
