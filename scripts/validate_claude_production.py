"""Opt-in three-turn acceptance of already installed Claude user settings.

No environment/settings/model/auth/approval/tool overrides. No matched duplicate
request. Only synthetic answers and this new session's numeric events are saved.
"""

from __future__ import annotations

import argparse
import json
import queue
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from validate_claude_gateway import DEFAULT_CLAUDE, ROOT, activity, selected_turn, synthetic_prompts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--history-copies", type=int, choices=range(1, 41), default=1, metavar="1-40",
                        help="Repeat the synthetic history: 2 reaches the 10K context stage, "
                             "17 the 100K stage (well over 200,000 characters).")
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc/memory.sqlite3")
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"mode": "dry-run", "rounds": 3, "overrides": False, "store": str(args.store)}))
        return 0
    if not args.store.is_file():
        raise SystemExit("The installed production store must already exist.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = ROOT / "outputs" / f"global_claude_compression_{stamp}_{uuid.uuid4().hex[:8]}"
    directory.mkdir()
    session_id = str(uuid.uuid4())
    prompts = ["Reply exactly READY. Do not use any tools.", *synthetic_prompts("long_first")[:2]]
    prompts[1] = "\n\n".join([prompts[1]] * args.history_copies)
    (directory / "synthetic_prompts.json").write_text(json.dumps(prompts, indent=2), encoding="utf-8")
    command = [str(DEFAULT_CLAUDE), "--print", "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--session-id", session_id]
    report = {"created_utc": stamp, "session_id": session_id, "new_session": True,
              "synthetic_history_copies": args.history_copies,
              "environment_overrides": False, "settings_overrides": False, "model_override": None,
              "auth_override": False, "approval_override": False, "tools_override": False,
              "duplicate_baseline_request": False, "turns": []}
    output = directory / "validation.json"
    events = queue.Queue()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                               cwd=directory, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def reader():
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.put(event)
        events.put(None)

    threading.Thread(target=reader, daemon=True).start()
    try:
        for index, prompt in enumerate(prompts, 1):
            process.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n")
            process.stdin.flush()
            turn = selected_turn(events, 240)
            turn["turn"] = index
            report["turns"].append(turn)
            report["activity"] = activity(args.store, session_id)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"turn": index, "completed": turn["completed"], "models": turn["models"],
                              "usage": turn.get("usage"), "report": str(output)}, ensure_ascii=False), flush=True)
            if not turn["completed"] or turn.get("session_id") != session_id:
                break
    except (OSError, ValueError) as error:
        report["error_type"] = type(error).__name__
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    report["activity"] = activity(args.store, session_id)
    with sqlite3.connect(args.store) as db:
        lengths = dict(db.execute(
            "SELECT request_id,context_input_tokens FROM tomc_request_activity WHERE session_id=?",
            (session_id,),
        ))
    for record in report["activity"]:
        record["context_input_tokens"] = lengths.get(record["request_id"])
    final = " ".join(report["turns"][-1].get("answers", [])) if report["turns"] else ""
    report["checks"] = {
        "three_turns_completed": len(report["turns"]) == 3 and all(t["completed"] for t in report["turns"]),
        "facts_retained": "CITY=Bristol; CODE=CYAN-73" in final,
        "no_tools_requested": not any(t.get("tools") for t in report["turns"]),
        "real_production_rewrite_sent": any(r["sent"] and r["reason"] == "old_history_compiled_cache_may_change"
                                             and r["after_tokens"] < r["before_tokens"] for r in report["activity"]),
        "provider_usage_observed": all(r["provider_input_tokens"] for r in report["activity"]),
        "no_upstream_failure": not any(r["state"] == "failed" for r in report["activity"]),
        "system_schema_supported": not any(r["reason"] == "unsupported_system_message" for r in report["activity"]),
        "context_length_observed": any(isinstance(r.get("context_input_tokens"), int)
                                       and r["context_input_tokens"] > 0 for r in report["activity"]),
    }
    report["passed"] = all(report["checks"].values())
    report["scope"] = "Production user configuration acceptance; no paired counterfactual or billing comparison."
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "passed": report["passed"], "checks": report["checks"]}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
