"""Loopback-only HTTP/SSE gateway. Credentials and raw requests are never logged.

The clients keep their authentication, model and upstream. Only supported old
context is rewritten; unsupported requests and disabled sessions pass through.
This module does not proxy arbitrary destinations or retry model requests.
"""

from __future__ import annotations

import argparse
import gzip
import json
import socket
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from .context_library import ContextLibrary
from .request_activity import RequestActivity
from .session_store import SessionStore
from .usage import UsageStore

MAX_BODY = 64 * 1024 * 1024
HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


class ClientDisconnected(Exception):
    """The host closed its side, for example a cancelled turn; not an upstream failure."""


class ResponseMetrics:
    """Bounded in-memory usage extraction; never persist model output text."""

    def __init__(self, sse):
        self.sse = sse
        self.buffer = b""
        self.completed = False
        self.failed = False
        self.input_tokens = None
        self.cached_tokens = None
        self._framing_checked = bool(sse)

    def observe(self, item):
        if not isinstance(item, dict):
            return
        kind = item.get("type")
        if kind in {"error", "response.failed", "response.incomplete"} or item.get("error"):
            self.failed = True
        if kind in {"response.completed", "message_stop"}:
            self.completed = True
        response = item.get("response", item.get("message", item))
        if not isinstance(response, dict):
            return
        if not self.sse and (response.get("status") == "completed" or "content" in response):
            self.completed = True
        usage = response.get("usage", item.get("usage"))
        if not isinstance(usage, dict):
            return
        value = usage.get("input_tokens")
        if isinstance(value, int) and value >= 0:
            # Anthropic input_tokens excludes cache creation/read input.
            for key in ("cache_creation_input_tokens", "cache_read_input_tokens"):
                extra = usage.get(key, 0)
                if isinstance(extra, int) and extra >= 0:
                    value += extra
            self.input_tokens = max(value, self.input_tokens or 0)
        cached = usage.get("cache_read_input_tokens")
        if cached is None:
            details = usage.get("input_tokens_details") or {}
            cached = details.get("cached_tokens") if isinstance(details, dict) else None
        if isinstance(cached, int) and cached >= 0:
            self.cached_tokens = max(cached, self.cached_tokens or 0)

    def feed(self, chunk):
        self.buffer += chunk
        if not self._framing_checked:
            # Some compatible upstreams emit SSE with a generic Content-Type.
            # Inspect only the leading event framing, never model text or headers.
            prefix = self.buffer[:512].removeprefix(b"\xef\xbb\xbf").lstrip()
            if prefix.startswith((b"event:", b"data:", b":")):
                self.sse = True
                self._framing_checked = True
                self.buffer = self.buffer.removeprefix(b"\xef\xbb\xbf")
            elif prefix and not any(
                marker.startswith(prefix) for marker in (b"event:", b"data:", b":", b"\xef\xbb\xbf")
            ):
                self._framing_checked = True
            elif len(self.buffer) >= 512:
                self._framing_checked = True
        if self.sse:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if line.startswith(b"data:"):
                    try:
                        self.observe(json.loads(line[5:].strip()))
                    except (ValueError, UnicodeError):
                        pass
        if len(self.buffer) > 2 * 1024 * 1024:
            self.buffer = b""  # Do not retain an unbounded event or response.

    def end(self):
        if self.sse:
            self.feed(b"\n")
        else:
            try:
                self.observe(json.loads(self.buffer))
            except (ValueError, UnicodeError):
                pass
        self.buffer = b""


def decode_body(raw, encoding):
    if encoding in ("", "identity"):
        return raw
    if encoding == "zstd":
        import io

        import zstandard

        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as source:
            data = source.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValueError("Decoded request too large")
        return data
    if encoding == "gzip":
        import io

        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:
            data = source.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValueError("Decoded request too large")
        return data
    raise ValueError("Unsupported request encoding")


class Gateway:
    def __init__(self, config, *, transport=None):
        self.config = config
        self.path = Path(config["store"]).expanduser()
        self.sessions = SessionStore(self.path)
        self.activity = RequestActivity(self.path)
        self.usage = UsageStore(self.path)
        self.library = ContextLibrary(self.path)
        self.routes = config["routes"]
        for name, route in self.routes.items():
            if name not in {"codex", "claude"}:
                raise ValueError("Unsupported gateway route")
            url = urlsplit(route["upstream"])
            if (
                url.scheme not in {"https", "http"}
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Invalid upstream URL")
            if url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("Remote upstream requires HTTPS")
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(600, connect=30),
            follow_redirects=False,
            trust_env=transport is None,
        )
        self._locks = [threading.Lock() for _ in range(64)]
        from .anthropic_request import AnthropicAdapter

        self._claude = AnthropicAdapter(self.path)

    def close(self):
        self.client.close()

    def _event(self, method, *args, **kwargs):
        try:
            return getattr(self.activity, method)(*args, **kwargs)
        except (OSError, ValueError, KeyError, sqlite3.Error):
            return None

    def prepare(self, host, suffix, headers, raw):
        request_id = str(uuid.uuid4())
        session_id, plan, detail = None, None, None
        body = raw
        changed = False
        reason = "unsupported_endpoint"
        endpoint = suffix.split("?", 1)[0].rstrip("/")
        # Older Codex builds compact through a standalone endpoint; it is recorded, never rewritten.
        compact_endpoint = host == "codex" and endpoint.endswith("/responses/compact")
        target = (
            (host == "codex" and endpoint.endswith("/responses"))
            or compact_endpoint
            or (host == "claude" and endpoint.endswith("/messages"))
        )
        if not target:
            return None, session_id, plan, body, changed
        payload = None
        try:
            payload = json.loads(decode_body(raw, headers.get("content-encoding", "").lower()))
            if not isinstance(payload, dict):
                raise ValueError("Request must be an object")
        except Exception:
            payload = None
            reason = "unsupported_request_encoding_or_json"
        native = None
        if payload is not None:
            if host == "codex":
                from .responses_request import classify_request, extract_session_id
            else:
                from .anthropic_request import classify_request, extract_session_id
            session_id = extract_session_id(payload, headers)
            try:
                native, detail = classify_request(payload, headers)
            except Exception:
                native, detail = None, None  # Classification only labels; it never blocks.
            if compact_endpoint:
                native, detail = (
                    "host_compaction_request",
                    {**(detail or {}), "endpoint": "responses_compact"},
                )
        self._event("start", request_id, host, session_id)
        try:
            enabled = False
            if session_id:
                self.sessions.register(
                    host,
                    session_id,
                    event="model_request",
                    activate=host == "codex"
                    or headers.get("x-claude-code-request-class") == "main",
                )
                enabled = self.sessions.effective_enabled(host, session_id)
            if payload is None:
                pass
            elif session_id is None:
                reason = "identity_unavailable"
            elif host == "claude" and native == "host_compaction_request":
                reason = native
            elif host == "claude" and headers.get("x-claude-code-request-class") != "main":
                reason = "non_main_request"
            elif host == "codex" and not enabled:
                reason = (
                    "session_disabled" if self.sessions.settings()["enabled"] else "global_disabled"
                )
            elif host == "codex" and native is not None:
                # The host owns this context: its compaction turn, opaque compaction
                # state, server-side history or an auxiliary request.
                reason = native
            else:
                options = {
                    **self.config.get("compression", {}),
                    **self.routes[host].get("compression", {}),
                }
                options = {
                    key: options[key]
                    for key in ("memory_budget", "recent_messages", "min_history_tokens")
                    if key in options
                }
                lock = self._locks[hash((host, session_id)) % len(self._locks)]
                with lock:
                    if host == "codex":
                        from .responses_request import adapt_request

                        plan = adapt_request(payload, **options)
                    else:
                        plan = self._claude.adapt(payload, headers, enabled=enabled, **options)
                if plan is not None:
                    reason = plan.reason
                if reason == "session_disabled" and not self.sessions.settings()["enabled"]:
                    reason = "global_disabled"
                if plan is not None and plan.transformed:
                    body = json.dumps(
                        plan.payload, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                    changed = True
        except Exception:
            # A preparation failure never blocks or silently retries a model request.
            reason, plan, changed, body = "preparation_failed", None, False, raw
        self._event(
            "finish",
            request_id,
            state="prepared" if changed else "passthrough",
            reason=reason,
            before_tokens=plan.before_tokens if plan else None,
            after_tokens=plan.after_tokens if plan else None,
            context_input_tokens=plan.prepared.compilation.stats.input_tokens
            if plan and plan.prepared is not None
            else None,
            detail=detail,
        )
        return request_id, session_id, plan, body, changed

    def complete(self, request_id, host, session_id, plan, metrics):
        self._event(
            "usage",
            request_id,
            provider_input_tokens=metrics.input_tokens,
            provider_cached_tokens=metrics.cached_tokens,
        )
        if (
            not plan
            or not plan.transformed
            or metrics.failed
            or not metrics.completed
            or plan.reason == "disabled_compatible_replay"
        ):
            return
        try:
            self.usage.record(
                {
                    "request_id": request_id,
                    "counter": plan.counter,
                    "usable": True,
                    "input_tokens": plan.before_tokens,
                    "memory_tokens": plan.after_tokens,
                    "context_input_tokens": plan.prepared.compilation.stats.input_tokens
                    if plan.prepared is not None
                    else None,
                    "reduced_tokens": plan.before_tokens - plan.after_tokens,
                }
            )
            if plan.prepared is not None and self.sessions.settings()["save_contexts"]:
                self.library.save(
                    plan.prepared,
                    task=plan.task,
                    source="automatic_request",
                    host=host,
                    session_id=session_id,
                    preparation_id=request_id,
                )
        except (OSError, ValueError, sqlite3.Error):
            pass  # A local reporting failure cannot discard the delivered answer.


class GatewayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass  # Never let the default traceback handler print request-derived data.

    def __init__(self, address, gateway):
        if address[0] != "127.0.0.1":
            raise ValueError("TOMC gateway must bind to IPv4 loopback")
        self.gateway = gateway
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TOMC"

    def log_message(self, *args):
        pass  # Standard access logs include URLs; never log them.

    def error(self, status, code):
        data = json.dumps({"error": {"type": "tomc_gateway", "code": code}}).encode()
        self.close_connection = True
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.linger_close()
        except OSError:
            pass  # A disconnected client cannot receive an error response.

    def linger_close(self):
        """Half-close, then briefly discard at most 64 KiB of unread input.

        Closing with unread input resets the connection on Windows, so the client
        could see an abort instead of this response. The discarded bytes are never
        parsed, so malformed or oversized framing is not trusted.
        """
        self.connection.shutdown(socket.SHUT_WR)
        self.connection.settimeout(0.5)
        remaining = 64 * 1024
        while remaining > 0:
            chunk = self.connection.recv(min(remaining, 8192))
            if not chunk:
                break
            remaining -= len(chunk)

    def do_GET(self):
        if self.path == "/health":
            data = b'{"service":"tomc-gateway","version":1,"ready":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        if self.headers.get("Origin"):
            return self.error(403, "browser_origin_not_supported")
        if self.headers.get("Host", "").split(":")[0] not in {"127.0.0.1", "localhost"}:
            return self.error(403, "loopback_host_required")
        path = urlsplit(self.path)
        decoded_path = unquote(path.path)
        if (
            path.scheme
            or path.netloc
            or "\\" in decoded_path
            or any(part in {".", ".."} for part in decoded_path.split("/"))
        ):
            return self.error(400, "invalid_path")
        parts = path.path.split("/", 2)
        gateway = self.server.gateway
        if len(parts) < 3 or parts[1] not in gateway.routes:
            return self.error(404, "unknown_route")
        host = parts[1]
        suffix = "/" + parts[2] + ("?" + path.query if path.query else "")
        if self.headers.get("Upgrade"):
            # Codex's supported WebSocket fallback is specifically HTTP 426.
            # The client then sends the same request over HTTP/SSE.
            return self.error(426, "use_http_sse")
        try:
            self.connection.settimeout(600)
            raw = self.read_body()
        except (ValueError, OSError):
            return self.error(400, "invalid_or_oversized_body")
        headers = {key.lower(): value for key, value in self.headers.items()}
        request_id = session_id = plan = None
        body, changed = raw, False
        if self.command == "POST":
            request_id, session_id, plan, body, changed = gateway.prepare(
                host, suffix, headers, raw
            )
        excluded = HOP | {x.strip() for x in headers.get("connection", "").lower().split(",")}
        outgoing = {k: v for k, v in headers.items() if k not in excluded}
        if changed:
            outgoing.pop("content-encoding", None)
        outgoing["accept-encoding"] = "identity"
        url = gateway.routes[host]["upstream"].rstrip("/") + suffix
        started = False
        try:
            with gateway.client.stream(
                self.command, url, headers=outgoing, content=body
            ) as response:
                if request_id:
                    gateway._event("sent", request_id)
                drop = (
                    HOP
                    | {"content-encoding"}
                    | {x.strip() for x in response.headers.get("connection", "").lower().split(",")}
                )
                try:
                    self.send_response(response.status_code)
                    for key, value in response.headers.multi_items():
                        if key.lower() not in drop:
                            self.send_header(key, value)
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                except OSError as exc:
                    raise ClientDisconnected from exc
                started = True
                metrics = ResponseMetrics(
                    "text/event-stream" in response.headers.get("content-type", "").lower()
                )
                if response.status_code >= 400:
                    metrics.failed = True
                for chunk in response.iter_bytes():
                    if not chunk:
                        continue
                    metrics.feed(chunk)
                    self.send_to_client(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                self.send_to_client(b"0\r\n\r\n")
                metrics.end()
                if request_id:
                    if metrics.failed:
                        gateway._event(
                            "finish", request_id, state="failed", reason="upstream_failed"
                        )
                    gateway.complete(request_id, host, session_id, plan, metrics)
        except ClientDisconnected:
            # The host stopped reading (cancelled turn or closed app); nothing to send back.
            if request_id:
                gateway._event("finish", request_id, state="failed", reason="client_disconnected")
            self.close_connection = True
        except (httpx.HTTPError, OSError):
            if request_id:
                gateway._event(
                    "finish", request_id, state="failed", reason="upstream_transport_failed"
                )
            if not started:
                try:
                    self.error(502, "upstream_unavailable")
                except OSError:
                    pass
            self.close_connection = True

    def send_to_client(self, data):
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except OSError as exc:
            raise ClientDisconnected from exc

    def read_body(self):
        transfer = self.headers.get("Transfer-Encoding", "").lower().strip()
        length_fields = self.headers.get_all("Content-Length", [])
        if len(length_fields) > 1 or transfer and length_fields:
            raise ValueError("Ambiguous framing")
        if not transfer:
            length = int(length_fields[0]) if length_fields else 0
            if not 0 <= length <= MAX_BODY:
                raise ValueError("Request too large")
            data = self.rfile.read(length)
            if len(data) != length:
                raise ValueError("Incomplete request")
            return data
        if transfer != "chunked":
            raise ValueError("Unsupported transfer encoding")
        data = bytearray()
        while True:
            line = self.rfile.readline(8193)
            if not line.endswith(b"\r\n") or len(line) > 8192:
                raise ValueError("Invalid chunk header")
            size = int(line.split(b";", 1)[0].strip(), 16)
            if size < 0 or len(data) + size > MAX_BODY:
                raise ValueError("Request too large")
            if size == 0:
                trailer_size = 0
                while True:
                    line = self.rfile.readline(8193)
                    trailer_size += len(line)
                    if not line.endswith(b"\r\n") or trailer_size > 16384:
                        raise ValueError("Invalid trailers")
                    if line == b"\r\n":
                        return bytes(data)
            chunk = self.rfile.read(size)
            if len(chunk) != size or self.rfile.read(2) != b"\r\n":
                raise ValueError("Invalid chunk data")
            data.extend(chunk)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    gateway = Gateway(config)
    server = GatewayHTTPServer(("127.0.0.1", config.get("port", 43187)), gateway)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        gateway.close()


if __name__ == "__main__":
    main()
