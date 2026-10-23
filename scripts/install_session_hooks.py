"""Preview or explicitly install metadata-only TOMC hooks, preserving user settings.

No host CLI is launched, no trust/permission setting is changed, and preview
output contains only the new TOMC definitions, never existing configuration.
"""

import argparse
import base64
import copy
import json
import os
import shlex
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
if not (SOURCE / "tomc/session_hook.py").is_file():
    SOURCE = ROOT / "plugins/tomc-memory/src"
sys.path.insert(0, str(SOURCE))

from tomc.session_hook import TOOL_PATTERN  # noqa: E402

MARKER = "--tomc-session-hook"


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def hook_definition(host, *, python, script, store, event):
    """Build one hook handler, with shell-safe Windows and POSIX commands."""
    args = [str(script), "--host", host, "--store", str(store), "--event", event, MARKER]
    if host == "claude_code":
        # Official exec form avoids all shell re-parsing, including Windows paths.
        return {"type": "command", "command": str(python), "args": args, "timeout": 10}
    command = shlex.join([str(python), *args])
    ps = (
        "$OutputEncoding = [Console]::OutputEncoding = "
        "[System.Text.UTF8Encoding]::new($false); "
        "$tomcHookInput = [Console]::In.ReadToEnd(); "
        "$tomcHookInput | & " + " ".join(_ps_quote(x) for x in [python, *args])
        + "; exit $LASTEXITCODE"
    )
    encoded = base64.b64encode(ps.encode("utf-16-le")).decode("ascii")
    windows = (
        "powershell.exe -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden "
        "-EncodedCommand " + encoded
    )
    return {"type": "command", "command": command, "commandWindows": windows, "timeout": 10}


def definitions(host, *, python, script, store):
    hooks = {}
    for event in ("SessionStart", "UserPromptSubmit", "Stop", "PreToolUse"):
        handler = hook_definition(host, python=python, script=script, store=store, event=event)
        group = {"hooks": [copy.deepcopy(handler)]}
        if event == "SessionStart":
            group["matcher"] = "startup|resume|clear|compact|fork"
        if event == "PreToolUse":
            group["matcher"] = TOOL_PATTERN
        hooks[event] = [group]
    return hooks


def _ours(handler):
    if not isinstance(handler, dict):
        return False
    args = handler.get("args")
    command = handler.get("command", "")
    return (
        isinstance(args, list) and MARKER in args
        and any(isinstance(x, str) and x.endswith("session_hook.py") for x in args)
    ) or (isinstance(command, str) and MARKER in command and "session_hook.py" in command)


def merge_hooks(existing, additions):
    """Replace only this installer's marked handlers, retaining other hook groups."""
    if not isinstance(existing, dict):
        raise ValueError("Configuration must be a JSON object.")
    updated = copy.deepcopy(existing)
    hooks = updated.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing hooks must be a JSON object.")
    for event, groups in additions.items():
        original = hooks.get(event, [])
        if not isinstance(original, list):
            raise ValueError("Existing hook event must be an array.")
        retained = []
        for group in original:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError("Existing hook group has an unsupported shape.")
            handlers = [h for h in group["hooks"] if not _ours(h)]
            if handlers:
                retained.append({**group, "hooks": handlers})
        hooks[event] = retained + copy.deepcopy(groups)
    return updated


def _read(path):
    try:
        original = path.read_bytes()
    except FileNotFoundError:
        return None, {}
    return original, json.loads(original.decode("utf-8-sig"))


def install_file(path, original, updated):
    """Back up exact bytes before an atomic update; reject concurrent edits."""
    current, _ = _read(path)
    if current != original:
        raise ValueError("Configuration changed since preview; run the installer again.")
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if original is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(path.name + ".tomc-backup-" + stamp + "-" + uuid.uuid4().hex[:8])
        with backup.open("xb") as stream:
            stream.write(original)
    temp = path.with_name(path.name + ".tomc-tmp-" + uuid.uuid4().hex)
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(updated, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--store", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--script", type=Path, default=SOURCE / "tomc/session_hook.py")
    parser.add_argument("--host", choices=("codex", "claude_code", "both"), default="both")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--install", action="store_true", help="Write the reviewed hook definitions.")
    action.add_argument("--dry-run", action="store_true", help="Preview only (the default).")
    args = parser.parse_args(argv)
    home = args.home.expanduser().resolve()
    python = args.python.expanduser().resolve()
    script = args.script.expanduser().resolve()
    store = (args.store or home / ".tomc/memory.sqlite3").expanduser().resolve()
    if not python.is_file() or not script.is_file():
        parser.error("Python and hook script must be existing files.")
    if os.name == "nt" and python.suffix.lower() != ".exe":
        parser.error("Windows hooks require a real Python .exe, not a batch shim.")
    hosts = ("codex", "claude_code") if args.host == "both" else (args.host,)
    plans = []
    try:
        for host in hosts:
            path = home / (".codex/hooks.json" if host == "codex" else ".claude/settings.json")
            original, current = _read(path)
            additions = definitions(host, python=python, script=script, store=store)
            updated = merge_hooks(current, additions)
            plans.append((host, path, original, updated, additions))
        # Validate both hosts before making the first change.
        for host, path, original, updated, additions in plans:
            if args.install:
                backup = install_file(path, original, updated)
                print(json.dumps({"host": host, "written": str(path),
                                  "backup": str(backup) if backup else None}, ensure_ascii=True))
            else:
                print(json.dumps({"host": host, "target": str(path), "hooks": additions},
                                 ensure_ascii=True, indent=2))
    except (OSError, ValueError, UnicodeError):
        print("TOMC hooks were not fully installed: configuration could not be safely updated.",
              file=sys.stderr)
        return 1
    print("Codex requires /hooks review and trust; this installer never changes trust or permissions.")
    print("Hook events show session activity, not foreground UI focus or automatic request savings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
