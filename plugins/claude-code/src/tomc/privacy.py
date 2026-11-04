"""Local privacy helpers: owner-only database files, secret redaction and erasure.

Nothing here contacts a network. Redaction is a fast pattern pass over text that
TOMC Memory is about to save; it lowers the chance that a pasted key ends up on
disk, but it cannot recognise every secret.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

REDACTED = "[REDACTED]"
DEFAULT_RETENTION_DAYS = 30

# Shown once, the first time the desktop companion or the gateway installer runs.
PRIVACY_NOTICE = {
    "zh": (
        "TOMC Memory 只在本机运行，不上传数据。开启网关后，Codex 和 Claude Code 的请求会经过"
        "本机的 TOMC Memory；登录凭证不保存。打开“保存上下文记录”时，压缩后的旧对话和你最新的一句话"
        "会先去掉常见密钥，再保存在本机 30 天。你可以随时关闭记录或一键清空；TOMC Memory "
        "没在运行时，可以一键恢复直连。"
    ),
    "en": (
        "TOMC Memory runs only on this computer and uploads nothing. With the gateway on, "
        "Codex and Claude Code requests pass through TOMC Memory on this computer; sign-in "
        "credentials are never saved. While \u201cSave context records\u201d is on, compressed old "
        "conversation and your latest message are kept here for 30 days, with common keys "
        "removed first. You can turn recording off or erase everything at any time. If TOMC "
        "Memory is not running, one command restores the direct connection."
    ),
}
NOTICE_MARKER = "privacy-notice-v1"


def take_privacy_notice(directory: Path | str, language: str = "en") -> str | None:
    """The first-run notice text, exactly once per data folder; None afterwards."""
    marker = Path(directory) / NOTICE_MARKER
    try:
        marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with marker.open("x", encoding="utf-8") as stream:
            stream.write("shown\n")
    except FileExistsError:
        return None
    except OSError:
        return None  # Unwritable folder: never nag on every launch.
    return PRIVACY_NOTICE["zh" if language == "zh" else "en"]


_SECRET_WORDS = (
    r"api[_-]?key|apikey|secret|token(?!s)|passw(?:or)?d|passphrase|pwd|"
    r"private[_-]?key|access[_-]?key|credentials?|auth[_-]?key|authorization"
)
_PATTERNS = (
    # PEM private key blocks, also when the END line was cut off.
    (
        re.compile(
            r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?"
            r"(?:-----END[A-Z0-9 ]*PRIVATE KEY-----|(?=\n[ \t]*\n)|\Z)"
        ),
        REDACTED,
    ),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 " + REDACTED),
    # Well-known provider token shapes.
    (
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{16,}|(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{8,}"
            r"|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{25,}"
            r"|glpat-[A-Za-z0-9_-]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
            r"|AIza[0-9A-Za-z_-]{35}"
            r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
        ),
        REDACTED,
    ),
    # Credentials inside URLs: scheme://user:password@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s/@]+@"), r"\1" + REDACTED + "@"),
    # KEY=value, KEY: value, "api_key": "value", including .env lines and escaped JSON.
    (
        re.compile(
            r"(?i)((?:\b|_)[A-Za-z0-9_.-]*(?:" + _SECRET_WORDS + r")[A-Za-z0-9_.-]*"
            r"(?:\\?[\"'])?\s*[:=]\s*(?:\\?[\"'])?)"
            r"(?!\[REDACTED\]|true\b|false\b|null\b|none\b|\$\{|<)"
            # A value cut short by a call or index, like os.environ["X"], is code.
            r"([^\s\"'\\,;#()\[\]{}<>]{6,})(?=[\s\"'\\,;#)\]}]|$)"
        ),
        r"\1" + REDACTED,
    ),
)


def redact(text: str) -> str:
    """Replace common credential patterns with a marker; other text is unchanged."""
    if not isinstance(text, str) or not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: Any) -> Any:
    """Redact every string inside JSON-like data, keeping its structure."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    return value


def ensure_private_file(path: Path | str) -> Path:
    """Create the database file with owner-only permissions before SQLite opens it.

    SQLite gives its journal files the same permissions as the database file.
    An existing file keeps its permissions; ``tighten_permissions`` fixes those.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        except FileExistsError:
            pass
    return path


def tighten_permissions(path: Path | str) -> None:
    """Make an existing database owner-only on POSIX systems (best effort)."""
    if os.name != "posix":
        return
    path = Path(path)
    for candidate in (path, path.with_name(path.name + "-journal")):
        try:
            if candidate.is_file() and candidate.stat().st_mode & 0o077:
                os.chmod(candidate, 0o600)
        except OSError:
            pass


def connect(path: Path | str, timeout: float = 30, **kwargs) -> sqlite3.Connection:
    """A write connection to a private database file that overwrites deleted content."""
    db = sqlite3.connect(ensure_private_file(path), timeout=timeout, **kwargs)
    db.execute("PRAGMA secure_delete=ON")
    return db


def vacuum(path: Path | str) -> bool:
    """Rebuild the file so deleted pages are gone. Skipped while another writer is busy."""
    path = Path(path)
    if not path.exists():
        return False
    try:
        db = sqlite3.connect(path, timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("VACUUM")
        finally:
            db.close()
    except sqlite3.Error:
        return False
    return True


# Tables whose rows hold conversation text or conversation metadata. Numeric usage
# totals and the on/off switches stay, so the companion's statistics survive an erase.
_ERASE_TABLES = (
    "entries",
    "tomc_context_snapshots",
    "tomc_snapshot_conversations",
    "tomc_anthropic_prefixes",
    "tomc_anthropic_prefix_times",
    "tomc_request_activity",
    "tomc_active_session",
    "preparation_receipts",
)


def erase_all(path: Path | str) -> dict:
    """Delete all saved conversation data in one database, then VACUUM the file.

    Paused sessions keep their off switch, with their title and project removed.
    """
    path = Path(path)
    counts: dict[str, int] = {}
    if path.exists():
        db = connect(path)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                tables = {
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                for table in _ERASE_TABLES:
                    if table in tables:
                        counts[table] = db.execute(f"DELETE FROM {table}").rowcount
                if "tomc_sessions" in tables:
                    counts["tomc_sessions"] = db.execute(
                        "DELETE FROM tomc_sessions WHERE enabled<>0"
                    ).rowcount
                    db.execute("UPDATE tomc_sessions SET title=NULL, project=NULL")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS tomc_preferences ("
                    "name TEXT PRIMARY KEY, value INTEGER NOT NULL)"
                )
                db.execute(
                    "INSERT INTO tomc_preferences VALUES ('erase_generation',1) "
                    "ON CONFLICT(name) DO UPDATE SET value=value+1"
                )
        finally:
            db.close()
        vacuum(path)
    return {
        "erased": True,
        "deleted": counts,
        "kept": "On/off switches and numeric usage totals (no conversation text).",
    }
