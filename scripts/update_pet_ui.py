"""Preview or install only the current companion's bilingual UI modules.

Uses the existing exact-byte backup/atomic installer. Does not touch client
configuration, gateway processes, credentials, stored chats or plugin caches.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from install_context_workspace import FileChange, UpdatePlan, _read_current, _safe_target, install

MODULES = (
    "ui_language.py",
    "macos_ui.py",
    "usage_widget_qt.py",
    "context_library_qt.py",
    "context_library.py",
    "pricing_qt.py",
    "oasis_qt.py",
    "cost_estimate.py",
    "pet_growth.py",
    "impact_story.py",
    "usage_widget.py",
    "quota.py",
    "usage.py",
    "request_activity.py",
    "animation_receipts.py",
    "savings.py",
    "savings_qt.py",
    "conversation_names.py",
    "conversations.py",
    "categories.py",
    "analysis.py",
    "analysis_qt.py",
)


def plan(home, source):
    home, source = Path(home).resolve(), Path(source).resolve()
    package = ".codex/tomc/pet-current/src/tomc"
    if not _safe_target(home, package + "/usage_widget_qt.py").is_file():
        raise ValueError("The current companion must already be installed")
    changes = []
    for name in MODULES:
        contents = (source / "src/tomc" / name).read_bytes()
        compile(contents, name, "exec", dont_inherit=True)
        relative = package + "/" + name
        before = _read_current(_safe_target(home, relative))
        if before != contents:
            changes.append(FileChange(relative, before, contents))
    return UpdatePlan(
        home,
        source,
        tuple(changes),
        (
            "Only the existing companion UI is updated; restart its launcher after installation.",
            "Language preferences are separate from chat, pricing and gateway settings.",
        ),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args(argv)
    update = plan(args.home, args.source)
    print(
        json.dumps(
            {
                "mode": "install" if args.install else "preview",
                "files": [c.relative for c in update.changes],
            },
            indent=2,
        )
    )
    if args.install:
        result = install(update)
        print(json.dumps({"status": result["status"], "receipt": result.get("receipt")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
