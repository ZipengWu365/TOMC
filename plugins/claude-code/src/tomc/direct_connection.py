"""Restore the direct connection for Codex and Claude Code, with TOMC Memory stopped.

Only the settings TOMC Memory's gateway activation wrote are removed: Codex's
top-level ``openai_base_url`` and Claude Code's ``env.ANTHROPIC_BASE_URL`` (with
its ``CLAUDE_CODE_GATEWAY_HINT_HEADERS`` switch), and only while they still point
at the local gateway. Everything else in those files stays as it is, including
edits the host made after installation. Running it again changes nothing.

Standard library only, so it also works when the gateway's own environment is
broken: ``python -m tomc restore-direct`` or ``python direct_connection.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
from pathlib import Path

CODEX_CONFIG = ".codex/config.toml"
CLAUDE_SETTINGS = ".claude/settings.json"
HOST_SETTINGS = (CODEX_CONFIG, CLAUDE_SETTINGS)
HINT = "CLAUDE_CODE_GATEWAY_HINT_HEADERS"
_GATEWAY = r"http://(?:127\.0\.0\.1|localhost):\d{1,5}/{host}/?"
_CODEX_LINE = re.compile(r"\s*openai_base_url\s*=\s*([\"'])(?P<url>[^\"']*)\1\s*(?:#.*)?")


def is_gateway_url(value, host: str) -> bool:
    return (
        isinstance(value, str) and re.fullmatch(_GATEWAY.replace("{host}", host), value) is not None
    )


def _top_level_gateway_lines(text: str) -> list[int]:
    lines = []
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("["):
            break  # The first table header ends the top-level keys.
        match = _CODEX_LINE.fullmatch(line)
        if match and is_gateway_url(match.group("url"), "codex"):
            lines.append(index)
    return lines


def codex_without_gateway(data: bytes, original: bytes | None = None) -> bytes | None:
    """Codex config without TOMC Memory's endpoint, or None when there is nothing to remove."""
    text = data.decode("utf-8")
    bom = "﻿" if text.startswith("﻿") else ""
    text = text.removeprefix(bom)
    if original is not None and _top_level_gateway_lines(original.decode("utf-8-sig")):
        return None  # The endpoint was already there before this installation.
    remove = set(_top_level_gateway_lines(text))
    if not remove:
        return None
    kept = [line for i, line in enumerate(text.splitlines(keepends=True)) if i not in remove]
    return (bom + "".join(kept)).encode("utf-8")


def claude_without_gateway(data: bytes, original: bytes | None = None) -> bytes | None:
    """Claude settings without TOMC Memory's env entries; b"" means delete the file."""
    document = json.loads(data.decode("utf-8-sig"))
    env = document.get("env") if isinstance(document, dict) else None
    if not isinstance(env, dict) or not is_gateway_url(env.get("ANTHROPIC_BASE_URL"), "claude"):
        return None
    before = {}
    if original is not None:
        try:
            before = json.loads(original.decode("utf-8-sig"))
        except (ValueError, UnicodeError):
            before = {}
        before = before if isinstance(before, dict) else {}
    before_env = before.get("env") if isinstance(before.get("env"), dict) else {}
    if is_gateway_url(before_env.get("ANTHROPIC_BASE_URL"), "claude"):
        return None  # The endpoint was already there before this installation.
    del env["ANTHROPIC_BASE_URL"]
    if env.get(HINT) == "1" and HINT not in before_env:
        del env[HINT]
    if not env and "env" not in before:
        del document["env"]
    if not document and original is None:
        return b""
    contents = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return b"\xef\xbb\xbf" + contents if data.startswith(b"\xef\xbb\xbf") else contents


def write_preserving_mode(path: Path, contents: bytes) -> None:
    """Atomically replace a file and keep its permissions; follows a symlinked file."""
    path = Path(path).resolve()
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def restore_file(path: Path, relative: str, original: bytes | None = None) -> str:
    """Remove TOMC Memory's keys from one host settings file; returns what happened."""
    path = Path(path)
    if not path.is_file():
        return "missing"
    try:
        data = path.read_bytes()
        change = (codex_without_gateway if relative == CODEX_CONFIG else claude_without_gateway)(
            data, original
        )
    except (ValueError, UnicodeError):
        return "unreadable_left_unchanged"
    if change is None:
        return "already_direct"
    if change == b"":
        path.unlink()
        return "removed_file_created_by_tomc"
    write_preserving_mode(path, change)
    return "restored"


def restore_direct(home: Path | str | None = None) -> dict:
    """Point Codex and Claude Code back at their own providers."""
    home = Path(home if home is not None else Path.home()).expanduser()
    files = {relative: restore_file(home / relative, relative) for relative in HOST_SETTINGS}
    changed = any(result.startswith(("restored", "removed")) for result in files.values())
    return {
        "status": "restored" if changed else "already_restored",
        "files": files,
        "next": "Quit and reopen Codex and Claude Code so they reconnect directly."
        if changed
        else "Codex and Claude Code already connect directly.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        result = restore_direct(args.home)
    except OSError as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__, "detail": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
