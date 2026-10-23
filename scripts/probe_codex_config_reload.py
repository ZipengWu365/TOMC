"""Isolated app-server routing probe. Local fixtures only; never calls a model."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    directory = (
        root
        / "outputs"
        / ("codex_config_reload_probe_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    )
    home = directory / "isolated-home"
    work = directory / "empty-workspace"
    home.mkdir(parents=True)
    work.mkdir()
    traffic = []

    def handler(label):
        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                traffic.append(
                    {"endpoint": label, "method": "GET", "path": self.path.split("?")[0]}
                )
                self.send_response(426 if self.headers.get("Upgrade") else 400)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                traffic.append(
                    {"endpoint": label, "method": "POST", "path": self.path.split("?")[0]}
                )
                body = b'{"error":{"message":"Local fixture: no model execution","type":"invalid_request_error","code":"fixture"}}'
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Fixture

    servers = [ThreadingHTTPServer(("127.0.0.1", 0), handler(label)) for label in ("A", "B")]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    urls = [f"http://127.0.0.1:{server.server_port}/v1" for server in servers]

    def config(url):
        (home / "config.toml").write_text(
            'model = "gpt-6-astra"\nopenai_base_url = '
            + json.dumps(url)
            + "\nchatgpt_base_url = "
            + json.dumps(url)
            + "\n",
            encoding="utf-8",
        )

    config(urls[0])
    # Explicit allowlist: no inherited account, auth, remote routing or proxy vars.
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
    executable = Path(os.environ["LOCALAPPDATA"]) / "OpenAI/Codex/bin/896a0166b774037a/codex.exe"
    process = subprocess.Popen(
        [str(executable), "app-server"],
        cwd=work,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    messages = queue.Queue()
    notices = []
    serial = 0
    report = {
        "no_model_execution": True,
        "production_touched": False,
        "fixture_auth_only": True,
        "steps": [],
    }

    def reader():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put({"probe_eof": True})

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def write(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def take(deadline):
        result = messages.get(timeout=max(0.01, deadline - time.monotonic()))
        if result.get("probe_eof"):
            raise RuntimeError("fixture app-server exited")
        if "id" in result and "method" in result:
            write(
                {
                    "id": result["id"],
                    "error": {"code": -32601, "message": "Fixture does not execute tools"},
                }
            )
        elif "method" in result:
            notices.append(result)
        return result

    def call(method, params):
        nonlocal serial
        serial += 1
        request_id = serial
        write({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            response = take(deadline)
            if response.get("id") == request_id:
                return response
        raise TimeoutError(method)

    def turn(thread_id, label):
        first, notice_start = len(traffic), len(notices)
        response = call(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": "Local routing fixture. Do not use tools."}],
            },
        )
        if "error" in response:
            report["steps"].append(
                {
                    "step": label,
                    "rpc_error_code": response["error"].get("code"),
                    "traffic": traffic[first:],
                }
            )
            return
        turn_id = response["result"]["turn"]["id"]
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            done = next(
                (
                    n
                    for n in notices[notice_start:]
                    if n.get("method") == "turn/completed"
                    and n.get("params", {}).get("turn", {}).get("id") == turn_id
                ),
                None,
            )
            if done:
                report["steps"].append(
                    {
                        "step": label,
                        "turn_status": done["params"]["turn"]["status"],
                        "traffic": traffic[first:],
                    }
                )
                return
            take(deadline)
        raise TimeoutError("fixture turn")

    try:
        init = call(
            "initialize",
            {
                "clientInfo": {"name": "tomc-routing-fixture", "version": "0.0.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        if "error" in init:
            raise RuntimeError("fixture initialize failed")
        write({"method": "initialized"})
        response = call("thread/start", {"cwd": str(work), "model": "gpt-6-astra"})
        if "error" in response:
            raise RuntimeError("fixture thread start failed")
        thread_id = response["result"]["thread"]["id"]
        turn(thread_id, "before_file_change")
        config(urls[1])
        read = call("config/read", {"includeLayers": False})
        report["config_read_observes_B"] = (
            read.get("result", {}).get("config", {}).get("openai_base_url") == urls[1]
        )
        turn(thread_id, "same_loaded_thread_after_file_change")
        reloaded = call("config/batchWrite", {"edits": [], "reloadUserConfig": True})
        report["reload_rpc_ok"] = "result" in reloaded
        turn(thread_id, "same_loaded_thread_after_reloadUserConfig")
        resumed = call(
            "thread/resume",
            {"threadId": thread_id, "excludeTurns": True, "config": {"openai_base_url": urls[1]}},
        )
        report["loaded_resume_rpc_ok"] = "result" in resumed
        turn(thread_id, "same_loaded_thread_after_resume_override")
        new = call("thread/start", {"cwd": str(work), "model": "gpt-6-astra"})
        if "result" in new:
            turn(new["result"]["thread"]["id"], "new_thread_in_same_process")
        unsubscribed = call("thread/unsubscribe", {"threadId": thread_id})
        report["unsubscribe_status"] = unsubscribed.get("result", {}).get("status")
        loaded = call("thread/loaded/list", {})
        report["still_loaded_after_unsubscribe"] = thread_id in loaded.get("result", {}).get(
            "data", []
        )
        call("thread/resume", {"threadId": thread_id, "excludeTurns": True})
        turn(thread_id, "same_thread_after_unsubscribe_then_immediate_resume")
        # Restart only our isolated process to exercise a truly unloaded resume.
        process.terminate()
        process.wait(timeout=10)
        reader_thread.join(timeout=5)
        while not messages.empty():
            messages.get_nowait()
        process = subprocess.Popen(
            [str(executable), "app-server"],
            cwd=work,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()
        call(
            "initialize",
            {
                "clientInfo": {"name": "tomc-routing-fixture", "version": "0.0.0"},
                "capabilities": {"experimentalApi": True},
            },
        )
        write({"method": "initialized"})
        resumed = call("thread/resume", {"threadId": thread_id, "excludeTurns": True})
        report["unloaded_resume_same_thread_id"] = (
            resumed.get("result", {}).get("thread", {}).get("id") == thread_id
        )
        turn(thread_id, "same_thread_after_isolated_process_restart_and_resume")
    except Exception as exc:
        report["probe_error"] = type(exc).__name__
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for server in servers:
            server.shutdown()
            server.server_close()
        path = directory / "report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(path), **report}, ensure_ascii=False, indent=2))
    return 1 if "probe_error" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
