"""Preview a minimal correction to existing TOMC Claude routing settings.

No-op when both values already match: touching mtime alone does not establish
that a running session reloaded its environment. --apply uses the existing
exact-byte backup and checked atomic replacement installer. No process, login,
model, approval, other environment variable or conversation is changed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from install_context_workspace import FileChange, UpdatePlan, _read_current, _safe_target, install

KEYS = ("ANTHROPIC_BASE_URL", "CLAUDE_CODE_GATEWAY_HINT_HEADERS")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys must be resolved before refreshing settings.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Nonstandard JSON constants are not supported.")


def plan_refresh(home: Path | str, port: int = 43187) -> UpdatePlan:
    home = Path(home).expanduser().resolve()
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Port must be an integer from 1024 to 65535.")
    relative = ".claude/settings.json"
    before = _read_current(_safe_target(home, relative))
    if before is None:
        raise ValueError("An existing Claude settings file is required.")
    try:
        original = json.loads(before.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                              parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Claude settings must be valid UTF-8 JSON.") from error
    env = original.get("env") if isinstance(original, dict) else None
    if not isinstance(env, dict) or not all(key in env for key in KEYS):
        raise ValueError("Both existing TOMC environment entries are required; use the installer for initial setup.")
    existing = env[KEYS[0]]
    if not isinstance(existing, str):
        raise ValueError("The existing TOMC base URL must be a string.")
    parsed = urlsplit(existing)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.path.rstrip("/") != "/claude" or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError("Refusing to replace a non-TOMC or credential-bearing upstream.")
    target = f"http://127.0.0.1:{port}/claude"
    updated = copy.deepcopy(original)
    updated["env"][KEYS[0]] = target
    updated["env"][KEYS[1]] = "1"
    changes = ()
    if updated != original:
        after = (json.dumps(updated, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if before.startswith(b"\xef\xbb\xbf"):
            after = b"\xef\xbb\xbf" + after
        changes = (FileChange(relative, before, after),)
    return UpdatePlan(home, Path(__file__).resolve().parents[1], changes, (
        "Only the two existing TOMC routing entries can change; all other JSON values are preserved.",
        "Matching values are not rewritten merely to alter the file timestamp.",
        "Claude Code supports settings env reload; a session's next observed request must verify routing.",
        "Host-managed routing and Claude Desktop can override or ignore these settings.",
    ))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--port", type=int, default=43187)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only (the default).")
    mode.add_argument("--apply", action="store_true", help="Back up and atomically correct differing TOMC entries.")
    args = parser.parse_args(argv)
    try:
        plan = plan_refresh(args.home, args.port)
        changed_keys = []
        if plan.changes:
            before = json.loads(plan.changes[0].before.decode("utf-8-sig"))["env"]
            after = json.loads(plan.changes[0].after.decode("utf-8-sig"))["env"]
            changed_keys = [key for key in KEYS if before[key] != after[key]]
        output = {"mode": "apply" if args.apply else "dry-run", "changed_keys": changed_keys,
                  "status": "changes_planned" if plan.changes else "unchanged", "notes": plan.notes}
        if args.apply:
            result = install(plan)
            output.update(status=result["status"], receipt=result.get("receipt"))
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        # Exception type only: OS/JSON exceptions may include private paths/data.
        print(json.dumps({"status": "refused", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
