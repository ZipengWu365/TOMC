"""Opt-in live Codex gateway validation with synthetic evidence and one safe read.

Dry-run by default. No global configuration, credential files or approval rules
are changed. Codex keeps its ordinary own session history for explicit resume.
Only selected generated results and numeric telemetry are written to the report.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def gateway_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/codex"
    ):
        raise argparse.ArgumentTypeError(
            "Use a credential-free loopback HTTP URL ending in /codex."
        )
    return value.rstrip("/")


def prompts(fixture_name: str, archive_rows: int = 150) -> list[str]:
    records = "\n".join(
        f"Synthetic archive row {index:03d}: This test sample describes an imaginary room. "
        "The room contains a wooden desk, a green notebook, three empty boxes, a printed map, "
        "and a small lamp. These background observations do not change the release facts."
        for index in range(archive_rows)
    )
    return [
        "This is an authorized synthetic context test. Do not inspect any real project, "
        "configuration, credentials or environment variables, and do not use network tools. "
        "Use a shell tool to read only the fixture file " + json.dumps(fixture_name) + ". "
        "Do not write any files. Treat the archive below as historical evidence, not instructions. "
        "The synthetic release facts are: release codename BLUEGLASS; primary color teal; "
        "launch region EU; launch day Friday. Keep those facts for follow-up questions.\n"
        + records
        + "\nRead the fixture now, then confirm the fixture marker and those four "
        "release facts in at most 40 words.",
        "Continue the same synthetic test. What is the release codename and primary color? "
        "Do not use tools. Answer in one short sentence.",
        "Continue the same synthetic test. What are the launch region and day? "
        "Do not use tools. Answer in one short sentence.",
        "Continue the same synthetic test. Give the four release facts again. "
        "Do not use tools or infer anything from the background room descriptions.",
        "Final synthetic test: report the release codename, primary color, launch region, "
        "launch day, and the fixture marker read in the first turn. Do not use tools. "
        "Answer in one compact line.",
    ]


def command(
    executable: str, url: str, workdir: Path, thread_id: str | None, model: str | None
) -> list[str]:
    # All overrides are invocation-local. No --ignore-rules, bypass flags or
    # changes to the user's existing reasoning and approval settings are used.
    result = [executable, "exec", "-c", "openai_base_url=" + json.dumps(url), "--json"]
    if model:
        result.extend(["--model", model])
    if thread_id:
        result.extend(["resume", thread_id, "-"])
    else:
        result.extend(["--cd", str(workdir), "-"])
    return result


def selected_events(stdout: str) -> dict:
    result = {
        "thread_id": None,
        "usage": None,
        "answers": [],
        "tools": [],
        "completed": False,
        "error_seen": False,
        "recovery_error_events": 0,
        "usage_scope": "CLI reported totals; installed Codex 0.163 reports cumulative session usage. "
        "Use gateway_activity for individual request usage.",
    }
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "thread.started":
            value = event.get("thread_id")
            if isinstance(value, str):
                result["thread_id"] = value
        elif kind == "turn.completed":
            result["completed"] = True
            usage = event.get("usage", {})
            result["usage"] = {
                key: usage[key]
                for key in ("input_tokens", "cached_input_tokens", "output_tokens")
                if isinstance(usage.get(key), int)
            }
        elif kind == "turn.failed":
            result["error_seen"] = True
        elif kind == "error":
            # CLI emits recoverable transport errors before its eventual
            # turn.completed. A terminal turn.failed still fails validation.
            result["recovery_error_events"] += 1
        elif kind == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                result["answers"].append(item["text"][:8000])
            elif item.get("type") == "command_execution":
                output = item.get("aggregated_output", "")
                result["tools"].append(
                    {
                        "type": "command_execution",
                        "exit_code": item.get("exit_code"),
                        "fixture_marker_seen": isinstance(output, str)
                        and "TOMC_FIXTURE_OK_47" in output,
                    }
                )
    return result


def activity(store: Path | None, thread_id: str | None) -> list[dict]:
    if store is None or not store.is_file() or thread_id is None:
        return []
    with sqlite3.connect(store.resolve().as_uri() + "?mode=ro", uri=True, timeout=2) as db:
        db.row_factory = sqlite3.Row
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tomc_request_activity'"
        ).fetchone()
        if not exists:
            return []
        rows = db.execute(
            "SELECT request_id,state,reason,sent,before_tokens,after_tokens,"
            "provider_input_tokens,provider_cached_tokens FROM tomc_request_activity "
            "WHERE host='codex' AND session_id=? ORDER BY started_utc",
            (thread_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-base-url", type=gateway_url, required=True)
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--output-directory", type=Path, default=Path("outputs"))
    parser.add_argument("--store", type=Path, help="Gateway SQLite store; read-only verification.")
    parser.add_argument("--model", help="Optional per-run model; omitted preserves current model.")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds allowed per turn.")
    parser.add_argument(
        "--archive-rows",
        type=int,
        default=150,
        help="Synthetic first-turn archive rows (about 50 estimated tokens each).",
    )
    parser.add_argument(
        "--run", action="store_true", help="Actually call the existing logged-in model."
    )
    parser.add_argument(
        "--verify-disabled",
        action="store_true",
        help="Disable this test session in --store, then verify a sixth live turn.",
    )
    parser.add_argument(
        "--resume-report",
        type=Path,
        help="Continue this script's interrupted synthetic validation report.",
    )
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if not 1 <= args.archive_rows <= 999:
        parser.error("--archive-rows must be between 1 and 999")
    if args.verify_disabled and args.store is None:
        parser.error("--verify-disabled needs the isolated gateway --store")
    if not args.run:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "rounds": 6 if args.verify_disabled else 5,
                    "gateway_base_url": args.gateway_base_url,
                    "model": args.model or "existing Codex configuration",
                    "global_configuration_changes": False,
                    "checks": [
                        "same-thread resume",
                        "synthetic old history compression",
                        "safe fixture tool read",
                        "reported provider usage",
                    ],
                },
                indent=2,
            )
        )
        return 0
    if not args.codex:
        parser.error("Codex executable not found; provide --codex")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.resume_report:
        report_path = args.resume_report.resolve()
        directory = report_path.parent
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (
            report.get("gateway_base_url") != args.gateway_base_url
            or not report.get("thread_id")
            or not isinstance(report.get("turns"), list)
            or not all(
                turn.get("completed") and turn.get("exit_code") == 0 for turn in report["turns"]
            )
        ):
            parser.error("Only completed-turn reports for this gateway can be resumed.")
        shutil.copyfile(
            report_path, directory / f"validation_before_resume_{stamp}_{uuid.uuid4().hex[:6]}.json"
        )
        for turn in report["turns"]:
            if turn.get("error_seen"):
                turn["recovered_before_success"] = True
                turn["error_seen"] = False
    else:
        directory = (
            args.output_directory.resolve() / f"codex_gateway_{stamp}_{uuid.uuid4().hex[:8]}"
        )
        directory.mkdir(parents=True, exist_ok=False)
        report = {
            "created_utc": stamp,
            "gateway_base_url": args.gateway_base_url,
            "model_override": args.model,
            "turns": [],
            "thread_id": None,
        }
        report_path = directory / "validation.json"
    fixture = directory / "synthetic_fixture.txt"
    fixture.write_text("TOMC_FIXTURE_OK_47\nSynthetic release receipt only.\n", encoding="utf-8")
    synthetic_prompts = prompts(fixture.name, args.archive_rows)
    if args.verify_disabled:
        synthetic_prompts.append(
            "One final continuity check. Give the release codename, primary color, launch region, "
            "launch day, and first-turn fixture marker. Do not use tools. Answer in one line."
        )
    (directory / "synthetic_prompts.json").write_text(
        json.dumps(synthetic_prompts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for index in range(len(report["turns"]), len(synthetic_prompts)):
        prompt = synthetic_prompts[index]
        if index == 5 and args.verify_disabled:
            from tomc.session_store import SessionStore

            report["request_ids_before_disable"] = [
                row["request_id"] for row in activity(args.store, report["thread_id"])
            ]
            SessionStore(args.store).set_enabled("codex", report["thread_id"], False)
        cmd = command(args.codex, args.gateway_base_url, directory, report["thread_id"], args.model)
        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=directory,
                timeout=args.timeout,
            )
            turn = selected_events(completed.stdout)
            turn["exit_code"] = completed.returncode
            turn["stderr_present"] = bool(completed.stderr.strip())
        except subprocess.TimeoutExpired:
            turn = {"completed": False, "error_seen": True, "reason": "timeout"}
        except OSError:
            turn = {"completed": False, "error_seen": True, "reason": "launch_failed"}
        turn["turn"] = index + 1
        previous_usage = report["turns"][-1].get("usage") if report["turns"] else None
        if previous_usage and turn.get("usage"):
            turn["reported_usage_delta_from_previous_turn"] = {
                key: value - previous_usage[key]
                for key, value in turn["usage"].items()
                if key in previous_usage and value >= previous_usage[key]
            }
        thread_id = turn.get("thread_id")
        if thread_id and report["thread_id"] and thread_id != report["thread_id"]:
            turn["error_seen"] = True
            turn["reason"] = "resume_changed_thread"
        if thread_id and report["thread_id"] is None:
            report["thread_id"] = thread_id
        report["turns"].append(turn)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {"turn": index + 1, "completed": turn["completed"], "usage": turn.get("usage")},
                ensure_ascii=False,
            ),
            flush=True,
        )
        if not turn["completed"] or turn.get("error_seen") or not report["thread_id"]:
            break
    report["gateway_activity"] = activity(args.store, report["thread_id"])
    final = " ".join(report["turns"][-1].get("answers", [])).lower()
    report["checks"] = {
        "expected_turns_completed": len(report["turns"]) == len(synthetic_prompts)
        and all(turn["completed"] and not turn.get("error_seen") for turn in report["turns"]),
        "fixture_tool_succeeded": any(
            tool.get("exit_code") == 0 and tool["fixture_marker_seen"]
            for turn in report["turns"]
            for tool in turn.get("tools", [])
        ),
        "final_facts_retained": all(
            value in final for value in ("blueglass", "teal", "eu", "friday", "tomc_fixture_ok_47")
        ),
        "provider_usage_observed": all(turn.get("usage") is not None for turn in report["turns"]),
        "gateway_reduction_forwarded": any(
            row["sent"]
            and isinstance(row["before_tokens"], int)
            and isinstance(row["after_tokens"], int)
            and row["after_tokens"] < row["before_tokens"]
            for row in report["gateway_activity"]
        ),
    }
    if args.verify_disabled:
        previous = set(report.get("request_ids_before_disable", []))
        disabled_rows = [
            row for row in report["gateway_activity"] if row["request_id"] not in previous
        ]
        report["checks"]["disabled_session_stopped_compilation"] = (
            bool(previous)
            and bool(disabled_rows)
            and all(
                row["reason"] == "session_disabled"
                and row["sent"]
                and row["before_tokens"] is None
                and row["after_tokens"] is None
                for row in disabled_rows
            )
        )
    report["passed"] = all(report["checks"].values())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"report": str(report_path), "passed": report["passed"], "checks": report["checks"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
