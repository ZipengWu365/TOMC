"""Opt-in post-install validation of one explicitly selected synthetic Codex chat.

No provider, model, reasoning, sandbox or approval override is passed to Codex.
Only that test thread's request records are read from the production store.
The status formatter proves UI data availability, not a visual desktop check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from validate_codex_gateway import selected_events


def request_rows(store: Path, thread_id: str) -> list[dict]:
    if not store.is_file():
        return []
    with sqlite3.connect(store.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as db:
        db.row_factory = sqlite3.Row
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tomc_request_activity'"
        ).fetchone():
            return []
        return [
            dict(row)
            for row in db.execute(
                "SELECT request_id,host,session_id,state,reason,sent,before_tokens,after_tokens,"
                "provider_input_tokens,provider_cached_tokens,updated_utc "
                "FROM tomc_request_activity WHERE host='codex' AND session_id=? ORDER BY started_utc",
                (thread_id,),
            )
        ]


def command(executable: str, thread_id: str) -> list[str]:
    return [executable, "exec", "--json", "resume", thread_id, "-"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--thread-id", required=True)
    parser.add_argument(
        "--workdir", type=Path, required=True, help="Previous authorized test's fixture directory."
    )
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc" / "memory.sqlite3")
    parser.add_argument("--output-directory", type=Path, default=Path("outputs"))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    try:
        uuid.UUID(args.thread_id)
    except ValueError:
        parser.error("--thread-id must be the explicitly authorized synthetic test thread UUID")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if not args.run:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "thread_id": args.thread_id,
                    "command": command(args.codex or "codex", args.thread_id),
                    "provider_override": False,
                    "model_override": False,
                    "store_scope": "Read only rows for this test thread",
                    "desktop_visual_verification": "separate check required",
                },
                indent=2,
            )
        )
        return 0
    if not args.codex:
        parser.error("Codex executable not found; provide --codex")
    fixture = args.workdir.resolve() / "synthetic_fixture.txt"
    if not fixture.is_file() or "TOMC_FIXTURE_OK_47" not in fixture.read_text(encoding="utf-8"):
        parser.error("--workdir is not the prepared synthetic fixture directory")
    old_ids = {row["request_id"] for row in request_rows(args.store, args.thread_id)}
    prompt = (
        "Continue our authorized synthetic test only. Return the release codename, primary color, "
        "launch region, launch day and fixture marker from the earlier test. Do not use tools, "
        "inspect real projects, or read configuration or credentials. Answer in one compact line."
    )
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "created_utc": started,
        "thread_id": args.thread_id,
        "synthetic_prompt": prompt,
        "configuration_overrides": [],
        "desktop_visual_verified": False,
    }
    try:
        completed = subprocess.run(
            command(args.codex, args.thread_id),
            input=prompt,
            cwd=args.workdir.resolve(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout,
        )
        report["turn"] = selected_events(completed.stdout)
        report["exit_code"] = completed.returncode
        report["stderr_present"] = bool(completed.stderr.strip())
    except (subprocess.TimeoutExpired, OSError) as error:
        report["turn"] = {"completed": False, "error_seen": True, "answers": []}
        report["failure_class"] = type(error).__name__
    new_rows = []
    for _ in range(25):
        new_rows = [
            row
            for row in request_rows(args.store, args.thread_id)
            if row["request_id"] not in old_ids
        ]
        if any(row["sent"] and row["provider_input_tokens"] is not None for row in new_rows):
            break
        time.sleep(0.2)
    report["new_request_rows"] = new_rows
    report["cat_status_text"] = None
    if new_rows:
        try:
            from tomc.context_library_qt import request_activity_text

            report["cat_status_text"] = request_activity_text(new_rows[-1])
        except ImportError:
            report["cat_status_formatter_unavailable"] = True
    answer = " ".join(report["turn"].get("answers", [])).lower()
    report["checks"] = {
        "same_thread_completed": report["turn"].get("completed")
        and not report["turn"].get("error_seen")
        and report["turn"].get("thread_id") == args.thread_id,
        "five_facts_correct": all(
            value in answer for value in ("blueglass", "teal", "eu", "friday", "tomc_fixture_ok_47")
        ),
        "global_gateway_observed_and_forwarded": any(row["sent"] for row in new_rows),
        "provider_usage_observed": any(
            row["provider_input_tokens"] is not None for row in new_rows
        ),
        "old_context_rewritten": any(
            row["state"] == "forwarded"
            and isinstance(row["before_tokens"], int)
            and isinstance(row["after_tokens"], int)
            and row["after_tokens"] < row["before_tokens"]
            for row in new_rows
        ),
        "cat_activity_data_available": bool(report["cat_status_text"]),
    }
    report["passed"] = all(report["checks"].values())
    args.output_directory.mkdir(parents=True, exist_ok=True)
    path = (
        args.output_directory.resolve()
        / f"codex_global_verified_{started}_{uuid.uuid4().hex[:8]}.json"
    )
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(path),
                "passed": report["passed"],
                "checks": report["checks"],
                "cat_status_text": report["cat_status_text"],
                "desktop_visual_verified": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
