"""Isolated probe: who owns Codex history, and does Codex adopt a served compaction window?

Runs one Codex binary as an isolated app-server (empty CODEX_HOME, placeholder API
key, workspace outside any repository) against a local fixture upstream. The fixture
answers ``/responses`` with valid SSE and ``/responses/compact`` with a chosen window.
Never contacts a real model, never reads real authentication, never touches a
production thread. All conversation text is synthetic, so request bodies are kept
as evidence (authorization-like headers are dropped before recording).

Scenarios
  S1 explicit compaction answered with readable text (a TOMC-style window).
  S2 explicit compaction answered with exactly one server-minted ``compaction``
     item; later turns and a restart/resume show what history Codex keeps.
  S3 automatic compaction after reported usage exceeds a configured limit.
  S4 compaction failure (HTTP 500).
  S5 context-window-exceeded failure on an ordinary turn.

Codex 0.163.x compacts through an ordinary ``/responses`` turn whose turn
metadata has ``request_kind: compaction`` and whose input ends with a
``compaction_trigger`` item ("responses compaction v2"). The legacy
``/responses/compact`` route is still answered so that any use of it is recorded.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DROP_HEADERS = {
    "authorization",
    "cookie",
    "chatgpt-account-id",
    "openai-organization",
    "openai-project",
    "proxy-authorization",
}
FACT = "FIXTURE_FACT_ALPHA_17"
TOMC_MARKER = "TOMC_FIXTURE_WINDOW"
OPAQUE_MARKER = "FIXTURE_OPAQUE_STATE"


def _decode(raw: bytes, encoding: str) -> bytes:
    if encoding in ("", "identity"):
        return raw
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "zstd":
        import zstandard

        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as source:
            return source.read()
    raise ValueError(encoding)


class Fixture:
    """Local stand-in for the Responses upstream; behaviour is set per probe step."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.records: list[dict] = []
        self.lock = threading.Lock()
        self.usage_input = 50
        self.compact_mode = "tomc"
        self.fail_next_turn: str | None = None
        self.replies = 0

    def window(self, body: dict) -> list[dict]:
        items = body.get("input") if isinstance(body.get("input"), list) else []
        users = [
            i
            for i in items
            if isinstance(i, dict)
            and i.get("type", "message") == "message"
            and i.get("role") == "user"
        ]
        retained = users[-1:] if users else []
        if self.compact_mode == "tomc":
            memory = {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"{TOMC_MARKER}: <tomc_history>compiled fixture evidence; the earlier code was "
                            f"{FACT}</tomc_history>"
                        ),
                    }
                ],
            }
            return [memory, *retained]
        return [*retained, {"type": "compaction", "encrypted_content": OPAQUE_MARKER}]

    def handler(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _body(self) -> bytes:
                if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                    data = bytearray()
                    while True:
                        size = int(self.rfile.readline().split(b";")[0].strip(), 16)
                        if size == 0:
                            while self.rfile.readline() not in (b"\r\n", b""):
                                pass
                            return bytes(data)
                        data.extend(self.rfile.read(size))
                        self.rfile.read(2)
                return self.rfile.read(int(self.headers.get("Content-Length", "0")))

            def _record(self, body):
                headers = {
                    k.lower(): v for k, v in self.headers.items() if k.lower() not in DROP_HEADERS
                }
                with fixture.lock:
                    seq = len(fixture.records) + 1
                    entry = {
                        "seq": seq,
                        "method": self.command,
                        "path": self.path.split("?")[0],
                        "headers": headers,
                        "body_file": None,
                    }
                    if body is not None:
                        name = f"requests/{seq:03d}.json"
                        (fixture.directory / name).write_text(
                            json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8"
                        )
                        entry["body_file"] = name
                        entry["body"] = body
                    fixture.records.append(entry)
                return entry

            def _send(self, status, payload: bytes, content_type: str):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._record(None)
                if self.headers.get("Upgrade"):
                    return self._send(426, b"", "text/plain")
                self._send(
                    404, b'{"error":{"message":"fixture","type":"not_found"}}', "application/json"
                )

            def do_POST(self):
                raw = self._body()
                try:
                    body = json.loads(
                        _decode(raw, self.headers.get("Content-Encoding", "").lower())
                    )
                except Exception:
                    body = {"undecodable": True, "bytes": len(raw)}
                entry = self._record(body)
                path = entry["path"].rstrip("/")
                if path.endswith("/responses/compact"):
                    if fixture.compact_mode == "error":
                        return self._send(
                            500,
                            b'{"error":{"message":"fixture compact failure",'
                            b'"type":"server_error"}}',
                            "application/json",
                        )
                    window = fixture.window(body)
                    entry["served_window"] = window
                    return self._send(
                        200, json.dumps({"output": window}).encode(), "application/json"
                    )
                if not path.endswith("/responses"):
                    return self._send(404, b"{}", "application/json")
                fixture.replies += 1
                rid = f"resp_fixture_{fixture.replies}"
                events = [
                    ("response.created", {"type": "response.created", "response": {"id": rid}})
                ]
                failure = fixture.fail_next_turn
                fixture.fail_next_turn = None
                inputs = body.get("input") if isinstance(body.get("input"), list) else []
                compaction_turn = (
                    bool(inputs)
                    and isinstance(inputs[-1], dict)
                    and inputs[-1].get("type") == "compaction_trigger"
                )
                entry["compaction_turn"] = compaction_turn
                if compaction_turn and fixture.compact_mode == "error":
                    return self._send(
                        500,
                        b'{"error":{"message":"fixture compaction failure","type":"server_error"}}',
                        "application/json",
                    )
                if compaction_turn and fixture.compact_mode == "v2_item":
                    item = {
                        "type": "compaction",
                        "id": f"cmp_{rid}",
                        "encrypted_content": f"{OPAQUE_MARKER}_{fixture.replies}",
                    }
                    entry["served_window"] = [item]
                    events.append(
                        (
                            "response.output_item.done",
                            {"type": "response.output_item.done", "item": item},
                        )
                    )
                    events.append(
                        (
                            "response.completed",
                            {
                                "type": "response.completed",
                                "response": {
                                    "id": rid,
                                    "status": "completed",
                                    "usage": {
                                        "input_tokens": fixture.usage_input,
                                        "input_tokens_details": {"cached_tokens": 0},
                                        "output_tokens": 5,
                                        "output_tokens_details": {"reasoning_tokens": 0},
                                        "total_tokens": fixture.usage_input + 5,
                                    },
                                },
                            },
                        )
                    )
                    stream = "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events)
                    return self._send(200, stream.encode(), "text/event-stream")
                if compaction_turn and fixture.compact_mode == "tomc":
                    # Readable replacement text where Codex expects one compaction item.
                    entry["served_window"] = [
                        {"type": "message", "role": "assistant", "text": TOMC_MARKER}
                    ]
                    events.append(
                        (
                            "response.output_item.done",
                            {
                                "type": "response.output_item.done",
                                "item": {
                                    "type": "message",
                                    "role": "assistant",
                                    "id": f"msg_{rid}",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": (
                                                f"{TOMC_MARKER}: <tomc_history>{FACT}</tomc_history>"
                                            ),
                                        }
                                    ],
                                },
                            },
                        )
                    )
                    events.append(
                        (
                            "response.completed",
                            {
                                "type": "response.completed",
                                "response": {
                                    "id": rid,
                                    "status": "completed",
                                    "usage": {
                                        "input_tokens": fixture.usage_input,
                                        "input_tokens_details": {"cached_tokens": 0},
                                        "output_tokens": 5,
                                        "output_tokens_details": {"reasoning_tokens": 0},
                                        "total_tokens": fixture.usage_input + 5,
                                    },
                                },
                            },
                        )
                    )
                    stream = "".join(f"event: {n}\ndata: {json.dumps(d)}\n\n" for n, d in events)
                    return self._send(200, stream.encode(), "text/event-stream")
                if failure:
                    events.append(
                        (
                            "response.failed",
                            {
                                "type": "response.failed",
                                "response": {
                                    "id": rid,
                                    "status": "failed",
                                    "error": {"code": failure, "message": f"fixture {failure}"},
                                },
                            },
                        )
                    )
                else:
                    events.append(
                        (
                            "response.output_item.done",
                            {
                                "type": "response.output_item.done",
                                "item": {
                                    "type": "message",
                                    "role": "assistant",
                                    "id": f"msg_{rid}",
                                    "content": [
                                        {
                                            "type": "output_text",
                                            "text": f"FIXTURE_REPLY_{fixture.replies}",
                                        }
                                    ],
                                },
                            },
                        )
                    )
                    events.append(
                        (
                            "response.completed",
                            {
                                "type": "response.completed",
                                "response": {
                                    "id": rid,
                                    "status": "completed",
                                    "usage": {
                                        "input_tokens": fixture.usage_input,
                                        "input_tokens_details": {"cached_tokens": 0},
                                        "output_tokens": 5,
                                        "output_tokens_details": {"reasoning_tokens": 0},
                                        "total_tokens": fixture.usage_input + 5,
                                    },
                                },
                            },
                        )
                    )
                stream = "".join(
                    f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events
                )
                self._send(200, stream.encode(), "text/event-stream")

        return Handler


def _summary(entry: dict) -> dict:
    body = entry.get("body") or {}
    items = body.get("input") if isinstance(body.get("input"), list) else []
    shape = []
    for item in items:
        if not isinstance(item, dict):
            shape.append("?")
            continue
        label = item.get("type", "message")
        if label == "message":
            label += ":" + str(item.get("role"))
        text = json.dumps(item, ensure_ascii=False)
        tags = [
            tag
            for tag, marker in (("TOMC", TOMC_MARKER), ("OPAQUE", OPAQUE_MARKER), ("FACT", FACT))
            if marker in text
        ]
        shape.append(label + ("[" + ",".join(tags) + "]" if tags else ""))
    turn_header = entry["headers"].get("x-codex-turn-metadata")
    metadata = (
        body.get("client_metadata") if isinstance(body.get("client_metadata"), dict) else None
    )

    def parse(value):
        try:
            return json.loads(value) if isinstance(value, str) else value
        except ValueError:
            return {"unparseable": True}

    return {
        "seq": entry["seq"],
        "method": entry["method"],
        "path": entry["path"],
        "thread_id_header": entry["headers"].get("thread-id"),
        "turn_metadata_header": parse(turn_header),
        "client_metadata": {k: parse(v) for k, v in (metadata or {}).items()},
        "top_level_keys": sorted(body) if isinstance(body, dict) else None,
        "store": body.get("store"),
        "previous_response_id": body.get("previous_response_id"),
        "has_context_management": "context_management" in body,
        "input_shape": shape,
        "served_window": entry.get("served_window"),
        "body_file": entry.get("body_file"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", default="gpt-6-astra")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = root / "outputs" / f"codex_compaction_probe_{args.label}_{stamp}"
    (directory / "requests").mkdir(parents=True)
    scratch = Path(tempfile.mkdtemp(prefix="tomc-codex-probe-"))  # outside any repository
    home, work = scratch / "home", scratch / "workspace"
    home.mkdir()
    work.mkdir()
    fixture = Fixture(directory)
    server = ThreadingHTTPServer(("127.0.0.1", 0), fixture.handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/v1"
    (home / "config.toml").write_text(
        f"model = {json.dumps(args.model)}\nopenai_base_url = {json.dumps(url)}\n"
        f"chatgpt_base_url = {json.dumps(url)}\nmodel_auto_compact_token_limit = 3000\n"
        "check_for_update_on_startup = false\n",
        encoding="utf-8",
    )
    allowed = {
        "SYSTEMROOT",
        "WINDIR",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "APPDATA",
        "COMSPEC",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(CODEX_HOME=str(home), OPENAI_API_KEY="fixture-not-a-real-key", RUST_LOG="error")
    version = subprocess.run(
        [str(args.executable), "--version"], capture_output=True, text=True
    ).stdout.strip()
    report: dict = {
        "schema_version": 1,
        "executable_version": version,
        "label": args.label,
        "created_utc": stamp,
        "no_model_execution": True,
        "production_touched": False,
        "fixture_auth_only": True,
        "auth_mode": "api_key_placeholder",
        "auto_compact_token_limit": 3000,
        "steps": [],
    }
    state: dict = {}

    def launch():
        process = subprocess.Popen(
            [str(args.executable), "app-server"],
            cwd=work,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        inbox: queue.Queue = queue.Queue()

        def reader():
            for line in process.stdout:
                try:
                    inbox.put(json.loads(line))
                except ValueError:
                    pass
            inbox.put({"probe_eof": True})

        threading.Thread(target=reader, daemon=True).start()
        state.update(process=process, inbox=inbox, notices=[], serial=state.get("serial", 0))

    def write(message):
        state["process"].stdin.write(json.dumps(message) + "\n")
        state["process"].stdin.flush()

    def take(deadline):
        result = state["inbox"].get(timeout=max(0.01, deadline - time.monotonic()))
        if result.get("probe_eof"):
            raise RuntimeError("fixture app-server exited")
        if "id" in result and "method" in result:
            write({"id": result["id"], "error": {"code": -32601, "message": "fixture declines"}})
        elif "method" in result:
            state["notices"].append(result)
        return result

    def call(method, params, timeout=60):
        state["serial"] += 1
        request_id = state["serial"]
        write({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = take(deadline)
            if response.get("id") == request_id and "method" not in response:
                return response
        raise TimeoutError(method)

    def settle(notice_start, timeout=45, need=("turn/completed",)):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            seen = {n.get("method") for n in state["notices"][notice_start:]}
            if all(name in seen for name in need):
                return True
            try:
                take(deadline)
            except queue.Empty:
                break
        return False

    def initialize():
        init = call(
            "initialize",
            {
                "clientInfo": {"name": "tomc-compaction-probe", "version": "0.0.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        if "error" in init:
            raise RuntimeError("initialize failed")
        write({"method": "initialized"})

    def step(label, method, params, *, need=("turn/completed",), timeout=45):
        first, notice_start = len(fixture.records), len(state["notices"])
        response = call(method, params)
        settled = "error" not in response and settle(notice_start, timeout, need)
        time.sleep(0.3)
        notices = state["notices"][notice_start:]
        record = {
            "step": label,
            "rpc": method,
            "rpc_error": response.get("error", {}).get("message") if "error" in response else None,
            "settled": settled,
            "notifications": sorted({n.get("method") for n in notices}),
            "turn_status": next(
                (
                    n["params"]["turn"].get("status")
                    for n in notices
                    if n.get("method") == "turn/completed"
                ),
                None,
            ),
            "turn_error": next(
                (
                    n["params"]["turn"].get("error")
                    for n in notices
                    if n.get("method") == "turn/completed" and n["params"]["turn"].get("error")
                ),
                None,
            ),
            "item_types": sorted(
                {
                    n["params"].get("item", {}).get("type")
                    for n in notices
                    if n.get("method") in {"item/started", "item/completed"}
                }
                - {None}
            ),
            "traffic": [_summary(e) for e in fixture.records[first:]],
        }
        report["steps"].append(record)
        return response

    def turn(label, thread_id, text, **kwargs):
        return step(
            label,
            "turn/start",
            {"threadId": thread_id, "input": [{"type": "text", "text": text}]},
            **kwargs,
        )

    def new_thread():
        response = call("thread/start", {"cwd": str(work), "model": args.model})
        return response["result"]["thread"]["id"]

    try:
        launch()
        initialize()
        # S1: explicit compaction answered with readable replacement text.
        t1 = new_thread()
        report["S1_thread"] = t1
        turn(
            "S1.turn1_fresh_thread",
            t1,
            f"Fixture turn one. Remember the code {FACT}. Reply briefly.",
        )
        turn("S1.turn2", t1, "Fixture turn two. Reply briefly.")
        fixture.compact_mode = "tomc"
        step("S1.compact_readable_text", "thread/compact/start", {"threadId": t1})
        turn("S1.turn3_after_rejected_compaction", t1, "Fixture turn three. What was the code?")
        # S2: exactly one server-minted compaction item, then ordinary turns and restart/resume.
        t2 = new_thread()
        report["S2_thread"] = t2
        turn("S2.turn1", t2, f"Fixture S2 turn one. Remember {FACT}.")
        turn("S2.turn2", t2, "Fixture S2 turn two.")
        fixture.compact_mode = "v2_item"
        step("S2.compact_v2_item", "thread/compact/start", {"threadId": t2})
        turn("S2.turn3_ordinary_with_opaque_state", t2, "Fixture S2 turn three.")
        turn("S2.turn4_ordinary_with_opaque_state", t2, "Fixture S2 turn four.")
        state["process"].terminate()
        state["process"].wait(timeout=15)
        launch()
        initialize()
        resumed = call("thread/resume", {"threadId": t2, "excludeTurns": True})
        report["S2_resume_same_id"] = resumed.get("result", {}).get("thread", {}).get("id") == t2
        turn("S2.turn5_after_restart_resume", t2, "Fixture S2 turn five after restart.")
        # S3: automatic compaction triggered by reported usage above the configured limit.
        t3 = new_thread()
        report["S3_thread"] = t3
        fixture.usage_input = 9000
        turn("S3.turn1_reports_usage_9000", t3, "Fixture S3 turn one.")
        fixture.usage_input = 50
        turn("S3.turn2_expect_auto_compaction", t3, "Fixture S3 turn two.")
        # S4: compaction failure.
        t4 = new_thread()
        report["S4_thread"] = t4
        turn("S4.turn1", t4, "Fixture S4 turn one.")
        fixture.compact_mode = "error"
        step("S4.compaction_http_500", "thread/compact/start", {"threadId": t4})
        fixture.compact_mode = "v2_item"
        turn("S4.turn2_after_failed_compaction", t4, "Fixture S4 turn two.")
        # S5: context window exceeded on an ordinary turn.
        t5 = new_thread()
        report["S5_thread"] = t5
        turn("S5.turn1", t5, "Fixture S5 turn one.")
        fixture.fail_next_turn = "context_length_exceeded"
        turn("S5.turn2_context_length_exceeded", t5, "Fixture S5 turn two.")
        turn("S5.turn3_next", t5, "Fixture S5 turn three.")
    except Exception as exc:
        report["probe_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        process = state.get("process")
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        server.shutdown()
        server.server_close()
        # The isolated rollout is the host's own persisted history (synthetic text only).
        if (home / "sessions").exists():
            shutil.copytree(home / "sessions", directory / "isolated-rollouts", dirs_exist_ok=True)
        shutil.rmtree(scratch, ignore_errors=True)
        path = directory / "report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(path)
    return 1 if "probe_error" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
