"""Preview or install core compile modules into installed tomc-memory MCP runtimes.

Updates only modules whose installed bytes equal either the version at --base-ref
(the source they were built from) or the current source; any other installed
version is reported and left untouched. Uses the existing exact-byte backup and
atomic installer. Running MCP servers keep their loaded code until their host
restarts them; new sessions load the update. Never edits plugin registration,
hooks, client configuration or credentials.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from install_context_workspace import FileChange, UpdatePlan, _read_current, _safe_target, install

MODULES = ("input.py", "easy.py", "store.py")
RUNTIMES = (
    ".codex/tomc/context-preview.1/plugins/tomc-memory",
    ".codex/tomc/assistant-preview.5/plugins/tomc-memory",
)


def plan(home, source, base_ref):
    home, source = Path(home).resolve(), Path(source).resolve()
    changes, notes = [], []
    for runtime in RUNTIMES:
        if not _safe_target(home, runtime + "/src/server.py").is_file():
            notes.append(f"{runtime}: not installed; skipped.")
            continue
        for name in MODULES:
            new = (source / "src/tomc" / name).read_bytes()
            compile(new, name, "exec", dont_inherit=True)
            base = subprocess.run(
                ["git", "-C", str(source), "show", f"{base_ref}:src/tomc/{name}"],
                capture_output=True,
                check=True,
            ).stdout
            relative = f"{runtime}/src/tomc/{name}"
            current = _read_current(_safe_target(home, relative))
            if current == new:
                continue
            if current != base:
                notes.append(
                    f"{relative}: installed version differs from {base_ref}; left unchanged."
                )
                continue
            changes.append(FileChange(relative, current, new))
    notes.append("Running MCP servers keep their loaded modules until restarted by their host.")
    return UpdatePlan(home, source, tuple(changes), tuple(notes))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--base-ref", required=True, help="Git ref the installed modules were built from"
    )
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)
    update = plan(args.home, args.source, args.base_ref)
    print(
        json.dumps(
            {
                "mode": "install" if args.install else "preview",
                "files": [c.relative for c in update.changes],
                "notes": list(update.notes),
            },
            indent=2,
        )
    )
    if args.install and update.changes:
        result = install(update)
        print(json.dumps({"status": result["status"], "receipt": result.get("receipt")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
