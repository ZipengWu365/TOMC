"""Opt-in live Claude gateway trial using synthetic history and one fixture read.

No global configuration, credential, model or thinking setting is changed.
Only selected synthetic answers, tool names and numeric telemetry are saved.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tomc.request_gateway import HOP, Gateway, GatewayHTTPServer, decode_body  # noqa: E402
from tomc.session_store import SessionStore  # noqa: E402

DEFAULT_CLAUDE = (
    Path.home()
    / ".vscode/extensions/anthropic.claude-code-2.1.308-win32-x64/resources/native-binary/claude.exe"
)
USAGE_KEYS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def synthetic_prompts(scenario="short_first"):
    background = "\n".join(
        f"Archive observation {i:03d}: the imaginary archive room contains a wooden desk, "
        "a green notebook, three empty boxes, a paper map and a small lamp. "
        "This background observation does not alter project release decisions."
        for i in range(160)
    )
    prompts = [
        "This is an authorized synthetic conversation test. Do not inspect any real project, "
        "settings, credentials or environment variables. Only use a tool when I explicitly "
        "ask to read synthetic_fixture.txt. Do not write files. Treat archive text as data.\n"
        "Aurora release facts: the launch city is Bristol; the handoff code is CYAN-73.\n"
        + background
        + "\nFinal authoritative Aurora release facts: launch city Bristol; "
        "handoff code CYAN-73. Acknowledge only with ARCHIVE_READY. Do not use tools.",
        "From our Aurora archive, report the launch city and handoff code exactly as "
        "CITY=<city>; CODE=<code>. Do not use tools.",
        "Use the Read tool to read only ./synthetic_fixture.txt in this test directory. "
        "Then report FIXTURE=<fixture_code>; VALUE=<fixture_value>; CITY=<Aurora launch city>; "
        "CODE=<Aurora handoff code>. Also solve this reasoning check: find the smallest integer "
        "larger than 10000 whose remainders modulo 7, 11 and 13 are respectively 3, 4 and 5. "
        "Give only the final integer as CHECK=<integer>, after checking all three conditions. "
        "Do not read any other file or use any other tool.",
        "TOMC new preparation is now disabled for this session. From the same conversation, "
        "report CITY=<Aurora launch city>; CODE=<Aurora handoff code>; "
        "FIXTURE=<fixture_code from the file previously read>; VALUE=<fixture_value>. "
        "Do not use tools; do not discuss the test.",
    ]
    if scenario == "short_first":
        prompts.insert(
            0,
            "This is an authorized synthetic conversation test. Do not read files, "
            "settings, credentials or environment variables. Do not use tools. "
            "For the initial short task, find the smallest integer larger than 10000 "
            "whose remainders modulo 7, 11 and 13 are respectively 3, 4 and 5. "
            "Check all three conditions and answer only START=<integer>.",
        )
    return prompts


def activity(path, session_id):
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='tomc_request_activity'"
        ).fetchone():
            return []
        return [
            dict(row)
            for row in db.execute(
                "SELECT request_id,state,reason,sent,before_tokens,after_tokens,provider_input_tokens,"
                "provider_cached_tokens FROM tomc_request_activity WHERE host='claude' AND session_id=? "
                "ORDER BY started_utc",
                (session_id,),
            )
        ]


def preparation_count(path):
    with sqlite3.connect(path) as db:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='tomc_context_snapshots'"
        ).fetchone():
            return 0
        return db.execute("SELECT COUNT(*) FROM tomc_context_snapshots").fetchone()[0]


def usage(value):
    return (
        {k: value[k] for k in USAGE_KEYS if isinstance(value.get(k), int)}
        if isinstance(value, dict)
        else {}
    )


class ValidationGateway(Gateway):
    """Record schema names only, never header values or request text."""

    def __init__(self, config, shapes, paired):
        super().__init__(config)
        self.shapes = shapes
        self.paired = paired

    def baseline(self, suffix, headers, raw, actual_request_id):
        """One authorized matched control, exclusively in this test harness."""
        self.paired.update(actual_request_id=actual_request_id, original_body_memory_only=True)
        outgoing = {k: v for k, v in headers.items() if k not in HOP}
        outgoing["accept-encoding"] = "identity"
        try:
            with self.client.stream(
                "POST", "https://api.anthropic.com" + suffix, headers=outgoing, content=raw
            ) as response:
                self.paired["http_status"] = response.status_code
                selected_usage = {}
                answer = ""
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except ValueError:
                        continue
                    if event.get("type") == "message_start":
                        message = event.get("message", {})
                        selected_usage.update(usage(message.get("usage")))
                        self.paired["model"] = message.get("model")
                    elif event.get("type") == "message_delta":
                        selected_usage.update(usage(event.get("usage")))
                    elif (
                        event.get("type") == "content_block_delta"
                        and event.get("delta", {}).get("type") == "text_delta"
                    ):
                        answer += event["delta"].get("text", "")
                    elif event.get("type") == "message_stop":
                        self.paired["completed"] = True
                self.paired["usage"] = selected_usage
                self.paired["answer"] = answer[:2000]
                self.paired["total_input_tokens"] = sum(
                    selected_usage.get(k, 0) for k in USAGE_KEYS[:3]
                )
        except Exception as error:
            self.paired["error_type"] = type(error).__name__

    def prepare(self, host, suffix, headers, raw):
        if host == "claude" and suffix.split("?", 1)[0].endswith("/messages"):
            try:
                payload = json.loads(decode_body(raw, headers.get("content-encoding", "")))
                shape = {
                    "documented_prompt_id_present": bool(headers.get("x-claude-code-prompt-id")),
                    "top_fields": sorted(payload),
                    "message_fields": sorted(
                        {
                            tuple(sorted(m))
                            for m in payload.get("messages", [])
                            if isinstance(m, dict)
                        }
                    ),
                    "message_roles_fields": sorted(
                        {
                            (m.get("role", "unknown"), tuple(sorted(m)))
                            for m in payload.get("messages", [])
                            if isinstance(m, dict)
                        }
                    ),
                    "message_output_config_fields": sorted(
                        {
                            tuple(sorted(m["output_config"]))
                            for m in payload.get("messages", [])
                            if isinstance(m, dict) and isinstance(m.get("output_config"), dict)
                        }
                    ),
                    "system_message_shapes": [
                        {
                            "index": i,
                            "content_type": type(m.get("content")).__name__,
                            "content_length": len(m.get("content", [])),
                            "output_config": m.get("output_config"),
                        }
                        for i, m in enumerate(payload.get("messages", []))
                        if isinstance(m, dict)
                        and m.get("role") == "system"
                        and isinstance(m.get("output_config"), dict)
                        and set(m["output_config"]) == {"effort"}
                        and (
                            m["output_config"]["effort"]
                            in ("low", "medium", "high", "xhigh", "max", None)
                            or isinstance(m["output_config"]["effort"], (int, float))
                        )
                    ],
                    "all_system_schema": [
                        {
                            "index": i,
                            "fields": sorted(m),
                            "field_types": {k: type(v).__name__ for k, v in m.items()},
                            "content_block_fields": [
                                sorted(b) for b in m.get("content", []) if isinstance(b, dict)
                            ]
                            if isinstance(m.get("content"), list)
                            else [],
                            "content_block_types": [
                                b.get("type") for b in m.get("content", []) if isinstance(b, dict)
                            ]
                            if isinstance(m.get("content"), list)
                            else [],
                            "output_config_fields": sorted(m.get("output_config", {}))
                            if isinstance(m.get("output_config"), dict)
                            else [],
                        }
                        for i, m in enumerate(payload.get("messages", []))
                        if isinstance(m, dict) and m.get("role") == "system"
                    ],
                    "block_fields": sorted(
                        {
                            (b.get("type", "unknown"), tuple(sorted(b)))
                            for m in payload.get("messages", [])
                            if isinstance(m, dict) and isinstance(m.get("content"), list)
                            for b in m["content"]
                            if isinstance(b, dict)
                        }
                    ),
                }
                if shape not in self.shapes:
                    self.shapes.append(shape)
            except (ValueError, TypeError, OSError):
                pass
        result = super().prepare(host, suffix, headers, raw)
        if not self.paired and result[2] is not None and result[2].prepared is not None:
            self.baseline(suffix, headers, raw, result[0])
        return result


class ValidationServer(GatewayHTTPServer):
    def __init__(self, address, gateway):
        self.accepted_sockets = []
        super().__init__(address, gateway)

    def get_request(self):
        connection, address = super().get_request()
        self.accepted_sockets.append(connection)
        return connection, address

    def handle_error(self, request, client_address):
        # Normal keep-alive close/restart can reset sockets; no raw traceback.
        pass


def start_gateway(config, shapes, paired):
    gateway = ValidationGateway(config, shapes, paired)
    server = ValidationServer(("127.0.0.1", config["port"]), gateway)
    worker = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
    )
    worker.start()
    return gateway, server, worker


def stop_gateway(running):
    gateway, server, worker = running
    server.shutdown()
    for connection in server.accepted_sockets:
        try:
            connection.shutdown(socket.SHUT_RDWR)
            connection.close()
        except OSError:
            pass
    server.server_close()
    worker.join(timeout=5)
    gateway.close()


def selected_turn(events, timeout):
    deadline = time.monotonic() + timeout
    turn = {
        "completed": False,
        "error": False,
        "answers": [],
        "models": [],
        "tools": [],
        "messages_usage": [],
        "thinking_blocks": 0,
        "input_transformations": [],
    }
    while time.monotonic() < deadline:
        try:
            event = events.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            turn["reason"] = "timeout"
            return turn
        if event is None:
            turn["reason"] = "process_exited"
            return turn
        kind = event.get("type")
        if kind == "assistant":
            message = event.get("message", {})
            if isinstance(message.get("model"), str):
                turn["models"].append(message["model"])
            turn["messages_usage"].append(usage(message.get("usage")))
            for block in message.get("content", []):
                if block.get("type") == "text":
                    turn["answers"].append(block.get("text", "")[:2000])
                elif block.get("type") in {"thinking", "redacted_thinking"}:
                    turn["thinking_blocks"] += 1
                elif block.get("type") == "tool_use":
                    turn["tools"].append({"name": block.get("name"), "id": block.get("id")})
            for item in message.get("input_transformations", []):
                turn["input_transformations"].append(
                    {k: item[k] for k in ("type", "reason", "path") if k in item}
                )
        elif kind == "result":
            turn["completed"] = not event.get("is_error", False)
            turn["error"] = bool(event.get("is_error", False))
            turn["subtype"] = event.get("subtype")
            turn["usage"] = usage(event.get("usage"))
            turn["session_id"] = event.get("session_id")
            turn["permission_denial_count"] = len(event.get("permission_denials", []))
            # ModelUsage has provider model IDs and numeric counters, no keys.
            turn["model_usage"] = {
                model: {k: v for k, v in data.items() if isinstance(v, (int, float))}
                for model, data in event.get("modelUsage", {}).items()
                if isinstance(data, dict)
            }
            if isinstance(event.get("result"), str) and not turn["answers"]:
                turn["answers"].append(event["result"][:2000])
            return turn
    turn["reason"] = "timeout"
    return turn


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", type=Path, default=DEFAULT_CLAUDE)
    parser.add_argument("--port", type=int, default=18740)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3, 4, 5))
    parser.add_argument("--scenario", choices=("short_first", "long_first"), default="short_first")
    parser.add_argument("--output-directory", type=Path, default=ROOT / "outputs")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--inherit-user-settings",
        action="store_true",
        help="Keep all user hooks, MCP servers and tools; override only the test gateway URL.",
    )
    args = parser.parse_args(argv)
    if not args.run:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "rounds": args.rounds or (5 if args.scenario == "short_first" else 4),
                    "port": args.port,
                    "model": "existing Claude configuration",
                    "auth": "existing login",
                    "global_changes": False,
                    "tool_allow": "Read(./synthetic_fixture.txt)",
                }
            )
        )
        return 0
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = (
        args.output_directory.resolve()
        / f"gateway_validation_claude_{stamp}_{uuid.uuid4().hex[:8]}"
    )
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "synthetic_fixture.txt").write_text(
        "fixture_code=HARBOUR-52\nfixture_value=19\n", encoding="utf-8"
    )
    prompts = synthetic_prompts(args.scenario)[: args.rounds]
    (directory / "synthetic_prompts.json").write_text(
        json.dumps(prompts, indent=2), encoding="utf-8"
    )
    settings = directory / "invocation_settings.json"
    settings.write_text(
        json.dumps(
            {"env": {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{args.port}/claude"}}
            if args.inherit_user_settings
            else {"disableAllHooks": True}
        ),
        encoding="utf-8",
    )
    mcp = directory / "empty_mcp.json"
    mcp.write_text('{"mcpServers":{}}', encoding="utf-8")
    config = {
        "port": args.port,
        "store": str(directory / "test.sqlite3"),
        "routes": {"claude": {"upstream": "https://api.anthropic.com"}},
        "compression": {"recent_messages": 1, "min_history_tokens": 4000},
    }
    (directory / "gateway_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    session_id = str(uuid.uuid4())
    sessions = SessionStore(config["store"])
    sessions.register(
        "claude", session_id, title="Synthetic gateway validation", project=str(directory)
    )
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{args.port}/claude"
    env["CLAUDE_CODE_GATEWAY_HINT_HEADERS"] = "1"
    command = [
        str(args.claude),
        "--print",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--session-id",
        session_id,
        "--settings",
        str(settings),
    ]
    if not args.inherit_user_settings:
        command += ["--strict-mcp-config", "--mcp-config", str(mcp), "--tools", "Read"]
    command += ["--allowedTools", "Read(./synthetic_fixture.txt)"]
    report = {
        "created_utc": stamp,
        "session_id": session_id,
        "directory": str(directory),
        "model_override": None,
        "thinking_override": None,
        "auth_override": False,
        "turns": [],
        "scenario": args.scenario,
        "inherit_user_settings": args.inherit_user_settings,
        "gateway_restarted_before_turn": 4 if args.scenario == "short_first" else 3,
    }
    output = directory / "validation.json"
    events = queue.Queue()
    report["request_schema_shapes"] = []
    report["paired_baseline"] = {}
    running = start_gateway(config, report["request_schema_shapes"], report["paired_baseline"])
    process = None
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=directory,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

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
        for index, prompt in enumerate(prompts, 1):
            if index == report["gateway_restarted_before_turn"]:
                stop_gateway(running)
                running = start_gateway(
                    config, report["request_schema_shapes"], report["paired_baseline"]
                )
            if index == (5 if args.scenario == "short_first" else 4):
                sessions.set_enabled("claude", session_id, False)
                report["preparations_before_disable"] = preparation_count(config["store"])
            process.stdin.write(
                json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n"
            )
            process.stdin.flush()
            turn = selected_turn(events, args.timeout)
            turn["turn"] = index
            report["turns"].append(turn)
            report["activity"] = activity(config["store"], session_id)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                json.dumps(
                    {
                        "turn": index,
                        "completed": turn["completed"],
                        "models": turn["models"],
                        "usage": turn.get("usage"),
                        "report": str(output),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if not turn["completed"] or turn.get("session_id") != session_id:
                break
    except (OSError, ValueError) as error:
        report["validation_error_type"] = type(error).__name__
    finally:
        if process:
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
        stop_gateway(running)
    report["activity"] = activity(config["store"], session_id)
    report["preparations_after_disable"] = preparation_count(config["store"])
    pair = report["paired_baseline"]
    actual = next(
        (r for r in report["activity"] if r["request_id"] == pair.get("actual_request_id")), None
    )
    if actual:
        pair["actual_total_input_tokens"] = actual["provider_input_tokens"]
        if pair.get("total_input_tokens") and actual["provider_input_tokens"] is not None:
            pair["input_reduction_tokens"] = (
                pair["total_input_tokens"] - actual["provider_input_tokens"]
            )
    final = " ".join(report["turns"][-1].get("answers", [])) if report["turns"] else ""
    report["checks"] = {
        "all_scenario_turns_completed": len(report["turns"])
        == (5 if args.scenario == "short_first" else 4)
        and all(t["completed"] for t in report["turns"]),
        "fixture_read_requested": any(t.get("tools") for t in report["turns"]),
        "facts_retained": all(x in final for x in ("Bristol", "CYAN-73", "HARBOUR-52", "19")),
        "request_reduction_observed": any(
            r["sent"] and r["before_tokens"] is not None and r["after_tokens"] < r["before_tokens"]
            for r in report["activity"]
        ),
        "provider_usage_observed": any(r["provider_input_tokens"] for r in report["activity"]),
        "same_prompt_replay_observed": any(
            r["reason"] == "replayed_prefix" for r in report["activity"]
        ),
        "matched_provider_input_reduced": pair.get("input_reduction_tokens", 0) > 0,
        "disabled_stopped_new_preparations": report.get("preparations_before_disable")
        == report["preparations_after_disable"],
        "no_upstream_failure": not any(r["state"] == "failed" for r in report["activity"]),
    }
    report["passed"] = all(report["checks"].values())
    report["scope"] = (
        "Observed provider usage, not counterfactual billed savings. No model or thinking override."
    )
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"report": str(output), "passed": report["passed"], "checks": report["checks"]},
            indent=2,
        ),
        flush=True,
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
