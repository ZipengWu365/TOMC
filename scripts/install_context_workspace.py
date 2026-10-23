"""Preview or install the context workspace into an existing local TOMC companion.

This installer does not register plugins, edit plugin caches or hooks, contact a
network, or restart applications. First install/configure the supplied independent
runtime through the supported Codex flow. Run this script without --install to
review its exact file scope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PET_MODULES = (
    "usage_widget_qt.py",
    "context_library_qt.py",
    "context_library.py",
    "session_store.py",
    "integration_status.py",
    "ui_language.py",
    "pricing_qt.py",
    "oasis_qt.py",
    "cost_estimate.py",
    "pet_growth.py",
    "impact_story.py",
    "usage_widget.py",
    "quota.py",
    "usage.py",
    "request_activity.py",
)


@dataclass(frozen=True)
class FileChange:
    relative: str
    before: bytes | None
    after: bytes


@dataclass(frozen=True)
class UpdatePlan:
    home: Path
    runtime: Path
    changes: tuple[FileChange, ...]
    notes: tuple[str, ...]


def _digest(contents):
    return hashlib.sha256(contents).hexdigest() if contents is not None else None


def _json(contents, label):
    try:
        value = json.loads(contents.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON; no files were changed.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return value


def _safe_target(home: Path, relative: str) -> Path:
    """Reject escapes and reparse redirects before any backup, replacement or removal."""
    candidate = home / relative
    if not candidate.resolve().is_relative_to(home):
        raise ValueError("An update target resolves outside the selected home directory.")
    cursor = home
    for part in Path(relative).parts:
        if part in {".", ".."}:
            raise ValueError("Update targets must use fixed home-relative paths.")
        cursor /= part
        try:
            attributes = cursor.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(attributes.st_mode)
                or getattr(attributes, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("Update targets must not traverse symbolic links or junctions.")
    return candidate


def _read_current(path):
    if path.exists() and not path.is_file():
        raise ValueError("An update target exists but is not a regular file.")
    return path.read_bytes() if path.exists() else None


def plan_update(home: Path | str, runtime: Path | str) -> UpdatePlan:
    """Validate and capture every intended byte change without writing anything."""
    home, runtime = Path(home).expanduser().resolve(), Path(runtime).expanduser().resolve()
    if not home.is_dir():
        raise ValueError("Select an existing user home directory.")
    if not runtime.is_dir():
        raise ValueError("Select the configured bundle's plugins/tomc-memory directory.")
    configuration = _json((runtime / "mcp.json").read_bytes(), "Runtime mcp.json")
    servers = configuration.get("mcpServers")
    server = servers.get("tomc") if isinstance(servers, dict) else None
    if not isinstance(server, dict) or server.get("type", "stdio") != "stdio":
        raise ValueError("Runtime mcp.json must contain a configured stdio tomc server.")
    command, arguments = server.get("command"), server.get("args")
    if (not isinstance(command, str) or not command.strip()
            or not isinstance(arguments, list) or not arguments
            or any(not isinstance(item, str) for item in arguments)
            or any("${" in item for item in [command, *arguments])):
        raise ValueError("Runtime tomc command/args are missing or contain unresolved placeholders.")
    if not (runtime / "src/server.py").is_file():
        raise ValueError("The configured runtime is missing src/server.py.")
    if "--directory" in arguments:
        index = arguments.index("--directory")
        if index + 1 >= len(arguments) or Path(arguments[index + 1]).resolve() != runtime:
            raise ValueError("Runtime tomc --directory does not point to the selected runtime.")
    sources = {}
    for name in PET_MODULES:
        path = runtime / "src/tomc" / name
        contents = path.read_bytes()
        try:
            compile(contents, name, "exec", dont_inherit=True)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Runtime module {name} does not compile; update refused.") from exc
        sources[name] = contents

    changes, notes = [], []
    claude_path = _safe_target(home, ".claude.json")
    claude_bytes = _read_current(claude_path)
    if claude_bytes is None:
        notes.append("Claude direct MCP skipped: .claude.json does not exist.")
    else:
        claude = _json(claude_bytes, "Claude user configuration")
        entries = claude.get("mcpServers", {})
        if not isinstance(entries, dict):
            raise ValueError("Claude mcpServers must be an object; update refused.")
        if "tomc-memory" not in entries:
            notes.append("Claude direct MCP skipped: no existing top-level tomc-memory entry.")
        else:
            entry = entries["tomc-memory"]
            if not isinstance(entry, dict) or entry.get("type", "stdio") != "stdio":
                raise ValueError("The existing Claude tomc-memory entry is not a stdio configuration.")
            if entry.get("command") != command or entry.get("args") != arguments:
                # All other fields, including env, stay in the existing object.
                entry["command"], entry["args"] = command, list(arguments)
                updated = (json.dumps(claude, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                if claude_bytes.startswith(b"\xef\xbb\xbf"):
                    updated = b"\xef\xbb\xbf" + updated
                changes.append(FileChange(".claude.json", claude_bytes, updated))
            else:
                notes.append("Claude direct MCP already points to the supplied runtime.")

    pet_relative = ".codex/tomc/pet-current/src/tomc"
    pet_directory = _safe_target(home, pet_relative)
    marker = _safe_target(home, f"{pet_relative}/usage_widget_qt.py")
    if not pet_directory.is_dir() or not marker.is_file():
        notes.append("Desktop cat skipped: an existing pet-current UI installation was not found.")
    else:
        for name in PET_MODULES:
            relative = f"{pet_relative}/{name}"
            previous = _read_current(_safe_target(home, relative))
            if previous != sources[name]:
                changes.append(FileChange(relative, previous, sources[name]))
        notes.append("Desktop scope: five context/UI modules only; artwork, animation and launchers stay intact.")
    _safe_target(home, ".codex/tomc/archive")
    return UpdatePlan(home, runtime, tuple(changes), tuple(notes))


def _atomic_write(path, contents):
    """Replace one file atomically using a flushed temporary sibling."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp",
                                         dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install(plan: UpdatePlan) -> dict:
    """Back up all prior bytes first, then apply checked atomic file replacements."""
    for change in plan.changes:
        if _read_current(_safe_target(plan.home, change.relative)) != change.before:
            raise ValueError("An intended file changed since validation; rerun the preview.")
    if not plan.changes:
        return {"status": "unchanged", "changes": [], "notes": list(plan.notes)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    relative_archive = f".codex/tomc/archive/session-update-{stamp}-{uuid.uuid4().hex[:8]}"
    archive = _safe_target(plan.home, relative_archive)
    archive.mkdir(parents=True, exist_ok=False)
    details = []
    for change in plan.changes:
        backup_name = f"files/{change.relative}" if change.before is not None else None
        if backup_name is not None:
            backup = _safe_target(plan.home, f"{relative_archive}/{backup_name}")
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb") as stream:
                stream.write(change.before)
                stream.flush()
                os.fsync(stream.fileno())
        details.append({"target": change.relative, "backup": backup_name,
                        "before_sha256": _digest(change.before), "after_sha256": _digest(change.after),
                        "state": "pending"})
    receipt = {"format": "tomc-context-workspace-update", "version": "0.1.5",
               "created_utc": datetime.now(timezone.utc).isoformat(), "runtime": str(plan.runtime),
               "status": "pending", "changes": details, "notes": list(plan.notes),
               "processes_restarted": False}
    receipt_path = _safe_target(plan.home, f"{relative_archive}/receipt.json")
    _atomic_write(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
    completed = []
    try:
        for index, change in enumerate(plan.changes):
            destination = _safe_target(plan.home, change.relative)
            if _read_current(destination) != change.before:
                raise ValueError("An intended file changed during the update; remaining writes stopped.")
            _atomic_write(destination, change.after)
            completed.append(index)
            details[index]["state"] = "updated"
        receipt["status"] = "installed"
    except (OSError, ValueError) as exc:
        receipt["status"] = "rolled_back"
        receipt["error_type"] = type(exc).__name__
        for index in reversed(completed):
            change = plan.changes[index]
            try:
                destination = _safe_target(plan.home, change.relative)
                if _read_current(destination) != change.after:
                    raise ValueError("A concurrently edited file cannot be rolled back safely.")
                if change.before is None:
                    destination.unlink()
                else:
                    _atomic_write(destination, change.before)
                details[index]["state"] = "rolled_back"
            except (OSError, ValueError):
                details[index]["state"] = "rollback_needs_attention"
                receipt["status"] = "rollback_needs_attention"
        _atomic_write(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
        raise RuntimeError(f"Update stopped; status {receipt['status']}. Inspect {receipt_path}") from exc
    _atomic_write(receipt_path, (json.dumps(receipt, indent=2) + "\n").encode())
    return {**receipt, "receipt": str(receipt_path), "backup_directory": str(archive)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Existing user home directory.")
    parser.add_argument("--runtime", type=Path, required=True,
                        help="Configured independent bundle's plugins/tomc-memory directory.")
    parser.add_argument("--install", action="store_true", help="Apply the validated update; default is dry-run.")
    args = parser.parse_args(argv)
    try:
        plan = plan_update(args.home, args.runtime)
        print("TOMC 0.1.5 workspace update: " + ("install" if args.install else "dry-run"))
        for change in plan.changes:
            print(f"  {'Update' if change.before is not None else 'Add'}: {change.relative}")
        for note in plan.notes:
            print(note)
        if args.install:
            result = install(plan)
            print(f"Status: {result['status']}")
            if result.get("receipt"):
                print(f"Receipt: {result['receipt']}")
        else:
            print("No files changed. Add --install to apply this plan with exact-byte backups.")
        print("No processes were restarted. New code loads on the next cat launch / MCP session.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Update stopped: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
