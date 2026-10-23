"""Independent numeric preparation receipts; imports never create usage."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class PreparationLog:
    """Append numeric receipts. A snapshot_id is historical and may have been deleted."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def record(self, preparation_id: str, *, status: str, host=None, session_id=None,
               snapshot_id=None, input_tokens=None, output_tokens=None, counter=None):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS preparation_receipts ("
                "id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, status TEXT NOT NULL, "
                "host TEXT, session_id TEXT, snapshot_id TEXT, input_tokens INTEGER, "
                "output_tokens INTEGER, counter TEXT)"
            )
            db.execute(
                "INSERT OR IGNORE INTO preparation_receipts VALUES (?,?,?,?,?,?,?,?,?)",
                (preparation_id, datetime.now(timezone.utc).isoformat(), status,
                 host, session_id, snapshot_id, input_tokens, output_tokens, counter),
            )
