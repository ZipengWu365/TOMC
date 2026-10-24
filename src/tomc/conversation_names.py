"""Original conversation names from each host's own local records, read-only.

Codex keeps thread names in ``$CODEX_HOME/state_*.sqlite`` (``threads.name``, else
the first-message ``title`` it shows for unnamed threads) and ``session_index.jsonl``.
A sub-agent thread is shown under its parent's name. Claude Code appends
``ai-title`` lines (``custom-title`` after a rename) to each session transcript.
Only names, working folders and agent nicknames are read; nothing is written.
"""

from __future__ import annotations

import json
import mmap
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path, PureWindowsPath

_SPACE = re.compile(r"\s+")
_UUID = re.compile(r"[0-9a-fA-F-]{8,64}\Z")
# Newest first: a rename wins over generated titles; older builds wrote summaries.
# Claude Code writes compact JSON; the spaced form is accepted as well.
_CLAUDE_TITLES = tuple(
    (marker, key)
    for kind, key in (
        ("custom-title", "customTitle"),
        ("ai-title", "aiTitle"),
        ("summary", "summary"),
    )
    for marker in (f'"type":"{kind}"'.encode(), f'"type": "{kind}"'.encode())
)


def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def clean(value, limit=80):
    """One readable line, shortened with an ellipsis."""
    if not isinstance(value, str):
        return None
    text = _SPACE.sub(" ", value).strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def folder(path):
    """The last folder name of a working directory, never the full path."""
    if not isinstance(path, str) or not path.strip():
        return None
    name = PureWindowsPath(path.strip().rstrip("\\/")).name or Path(path.strip()).name
    return clean(name, 48)


def _state_db(home):
    numbered = []
    for path in home.glob("state_*.sqlite"):
        suffix = path.stem.removeprefix("state_")
        if suffix.isdigit():
            numbered.append((int(suffix), path))
    return max(numbered)[1] if numbered else None


def codex_names(thread_ids, home=None):
    """{thread ID: {"title", "folder", "agent"}} for the threads Codex knows."""
    home = Path(home) if home else codex_home()
    wanted = {value for value in thread_ids if isinstance(value, str) and value}
    if not wanted:
        return {}
    index = {}
    try:
        with (home / "session_index.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("id") in wanted and row.get("thread_name"):
                    index[row["id"]] = row["thread_name"]  # later lines are renames
    except OSError:
        pass
    threads, parents = {}, {}
    database = _state_db(home)
    if database is not None:
        try:
            with closing(
                sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5)
            ) as db:
                tables = {
                    name
                    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "thread_spawn_edges" in tables:
                    for start in range(0, len(wanted), 400):
                        batch = sorted(wanted)[start : start + 400]
                        marks = ",".join("?" * len(batch))
                        parents.update(
                            db.execute(
                                "SELECT child_thread_id,parent_thread_id FROM thread_spawn_edges "
                                f"WHERE child_thread_id IN ({marks})",
                                batch,
                            ).fetchall()
                        )
                if "threads" in tables:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(threads)")}
                    fields = [
                        name
                        for name in ("name", "title", "cwd", "agent_nickname", "source")
                        if name in columns
                    ]
                    lookup = sorted(wanted | set(parents.values()))
                    for start in range(0, len(lookup), 400):
                        batch = lookup[start : start + 400]
                        marks = ",".join("?" * len(batch))
                        for row in db.execute(
                            f"SELECT id,{','.join(fields)} FROM threads WHERE id IN ({marks})",
                            batch,
                        ):
                            threads[row[0]] = dict(zip(fields, row[1:]))
        except sqlite3.Error:
            pass

    def own_name(thread):
        row = threads.get(thread, {})
        return clean(row.get("name")) or clean(index.get(thread))

    result = {}
    for thread in wanted:
        row = threads.get(thread, {})
        parent = parents.get(thread)
        subagent = parent is not None or row.get("source") == "subagent"
        title = own_name(thread)
        if not title and parent:
            title = own_name(parent) or clean(threads.get(parent, {}).get("title"))
        title = title or clean(row.get("title"))
        if title or row:
            result[thread] = {
                "title": title,
                "folder": folder(row.get("cwd") or threads.get(parent, {}).get("cwd")),
                "agent": clean(row.get("agent_nickname"), 40) if subagent else None,
                "subagent": subagent,
            }
    return result


# (size, mtime) → (title, cwd) per transcript; only a changed transcript is read again.
_CLAUDE_CACHE: dict = {}


def _claude_title(path):
    try:
        stat = path.stat()
    except OSError:
        return None, None
    stamp = (stat.st_size, stat.st_mtime_ns)
    cached = _CLAUDE_CACHE.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    found = _read_claude_title(path)
    _CLAUDE_CACHE[path] = (stamp, found)
    return found


def _read_claude_title(path):
    try:
        with path.open("rb") as stream:
            if os.fstat(stream.fileno()).st_size == 0:
                return None, None
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:

                def record(position):
                    start = data.rfind(b"\n", 0, position) + 1
                    end = data.find(b"\n", position)
                    try:
                        value = json.loads(data[start : len(data) if end < 0 else end])
                    except ValueError:
                        return {}
                    return value if isinstance(value, dict) else {}

                title = None
                for marker, key in _CLAUDE_TITLES:
                    position = data.rfind(marker)
                    if position >= 0:
                        title = clean(record(position).get(key))
                        if title:
                            break
                position = data.rfind(b'"cwd":')
                cwd = record(position).get("cwd") if position >= 0 else None
                return title, cwd
    except (OSError, ValueError):
        return None, None


def claude_names(session_ids, home=None):
    """{session ID: {"title", "folder"}} from Claude Code session transcripts."""
    projects = (Path(home) if home else claude_home()) / "projects"
    wanted = {value for value in session_ids if isinstance(value, str) and _UUID.fullmatch(value)}
    if not wanted:
        return {}
    # One directory pass; identifiers are matched against file names, never used as patterns.
    transcripts = {path.stem: path for path in projects.glob("*/*.jsonl") if path.stem in wanted}
    result = {}
    for session, transcript in transcripts.items():
        title, cwd = _claude_title(transcript)
        if title or cwd:
            result[session] = {"title": title, "folder": folder(cwd), "agent": None}
    return result


def resolve(conversations, *, codex=None, claude=None):
    """Names for ``(host, session_id)`` pairs; unknown hosts and sessions are omitted."""
    pairs = {(host, session) for host, session in conversations if session}
    names = {}
    found = codex_names([s for h, s in pairs if h == "codex"], codex)
    names.update({("codex", session): value for session, value in found.items()})
    found = claude_names([s for h, s in pairs if h == "claude"], claude)
    names.update({("claude", session): value for session, value in found.items()})
    return names
