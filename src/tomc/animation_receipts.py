"""Append-only receipts tying each pet animation to the request ID that caused it.

One JSON line per event: queued (the UI read a prepared event), started, completed,
skipped (with a reason code) or interrupted. Lines hold IDs, stage, counts and
timestamps only, never prompts, memory text or paths. Compilation, dispatch,
model success and billing stay in the request tables; a receipt proves only what
this UI process did with an event. Writing never raises into the UI.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

EVENTS = {"queued", "started", "completed", "skipped", "interrupted"}
TERMINAL = {"completed", "skipped", "interrupted"}
FILENAME = "animation_receipts.jsonl"
_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_CODE = re.compile(r"[a-z0-9_]{1,40}\Z")


def _stamp():
    return datetime.now(timezone.utc).isoformat()


def _count(value):
    return value if type(value) is int and 0 <= value <= 10**12 else None


class AnimationReceipts:
    """Bounded per-machine receipt log; rotates once to ``.1`` at ``max_bytes``."""

    def __init__(self, directory: str | Path, *, demo: bool = False, max_bytes: int = 512 * 1024):
        self.path = Path(directory) / FILENAME
        self.demo = bool(demo)
        self.max_bytes = max_bytes
        self.instance = f"{os.getpid()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"

    def record(self, event, request_id, *, stage=None, context_input_tokens=None, reason=None):
        if event not in EVENTS or not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            return False
        line = {"utc": _stamp(), "event": event, "request_id": request_id, "ui": self.instance}
        if type(stage) is int and 1 <= stage <= 4:
            line["stage"] = stage
        if _count(context_input_tokens) is not None:
            line["context_input_tokens"] = context_input_tokens
        if isinstance(reason, str) and _CODE.fullmatch(reason):
            line["reason"] = reason
        if self.demo:
            line["demo"] = True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size >= self.max_bytes:
                os.replace(self.path, self.path.with_name(FILENAME + ".1"))
            with self.path.open("a+b") as handle:
                if handle.seek(0, os.SEEK_END):
                    handle.seek(-1, os.SEEK_END)
                    if handle.read(1) != b"\n":
                        handle.write(b"\n")  # End a line a crash cut short; never merge into it.
                handle.write(json.dumps(line, separators=(",", ":")).encode("utf-8") + b"\n")
            return True
        except OSError:
            return False

    def read(self, request_ids=None):
        """Oldest first across the rotated and current files; unreadable lines are skipped."""
        wanted = set(request_ids) if request_ids is not None else None
        rows = []
        for path in (self.path.with_name(FILENAME + ".1"), self.path):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for text in lines:
                try:
                    row = json.loads(text)
                except ValueError:
                    continue  # A line can be cut short by a crash mid-write.
                if (
                    isinstance(row, dict)
                    and row.get("event") in EVENTS
                    and (wanted is None or row.get("request_id") in wanted)
                ):
                    rows.append(row)
        return rows

    def recover_interrupted(self):
        """Close animations an earlier UI process started but never finished.

        Crash-exactly-once is not promised: the earlier process may have drawn
        part of the animation. It is reported as interrupted, never replayed.
        """
        open_starts = {}
        for row in self.read():
            if row["event"] == "started" and row.get("ui") != self.instance:
                open_starts[row["request_id"]] = row
            elif row["event"] in TERMINAL:
                open_starts.pop(row["request_id"], None)
        for request_id, row in open_starts.items():
            self.record(
                "interrupted",
                request_id,
                stage=row.get("stage"),
                context_input_tokens=row.get("context_input_tokens"),
                reason="ui_exited_before_completion",
            )
        return len(open_starts)
