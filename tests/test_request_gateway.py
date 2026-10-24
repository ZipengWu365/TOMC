"""Loopback-only gateway integration tests; all auth values and sessions are fixtures."""

from __future__ import annotations

import gzip
import http.client
import json
import socket
import sqlite3
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import zstandard

from tomc import request_gateway
from tomc.request_gateway import Gateway, GatewayHTTPServer, Handler, ResponseMetrics, decode_body

FAKE_AUTH = "Bearer fixture-only-never-a-real-token"
FAKE_API_KEY = "fixture-only-never-a-real-api-key"


def payload(host="codex", session="fixture-session", *, stream=False):
    messages = []
    for index in range(8):
        messages.extend(
            [
                {
                    "role": "user",
                    "content": "\n".join(
                        f"Project decision {index}-{j}: capacity {40 + j}; keep the teal design."
                        for j in range(35)
                    ),
                },
                {"role": "assistant", "content": f"Recorded decision {index}."},
            ]
        )
    messages.append({"role": "user", "content": "What is the latest capacity?"})
    if host == "codex":
        return {
            "model": "fixture-model",
            "stream": stream,
            "input": messages,
            "instructions": "Retain this exact instruction.",
            "client_metadata": {"thread_id": session},
        }
    return {
        "model": "fixture-model",
        "max_tokens": 20,
        "stream": stream,
        "messages": messages,
        "system": "Retain this exact instruction.",
        "metadata": {"user_id": json.dumps({"session_id": session})},
    }


def response_body(host="codex", *, stream=False, failed=False):
    if host == "codex":
        response = {
            "id": "response-fixture",
            "status": "completed",
            "usage": {"input_tokens": 750, "input_tokens_details": {"cached_tokens": 125}},
            "output": [],
        }
        if stream:
            event = {
                "type": "response.failed" if failed else "response.completed",
                "response": response,
            }
            return (
                b": fixture keepalive\r\n\r\n"
                + b"data: "
                + json.dumps(event).encode()
                + b"\r\n\r\n"
            )
        return json.dumps(response).encode()
    response = {
        "id": "message-fixture",
        "content": [{"type": "text", "text": "Fixture reply."}],
        "usage": {
            "input_tokens": 500,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 150,
        },
    }
    if stream:
        return (
            b"event: message_start\ndata: "
            + json.dumps({"type": "message_start", "message": response}).encode()
            + b'\n\nevent: message_stop\ndata: {"type":"message_stop"}\n\n'
        )
    return json.dumps(response).encode()


class FakeUpstream(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass  # Clients deliberately disconnect in transport-failure fixtures.


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        fixture = self.server.fixture
        data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        fixture.received.append(
            {
                "path": self.path,
                "method": self.command,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": data,
            }
        )
        if fixture.disconnect_before_headers:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            self.close_connection = True
            return
        self.send_response(fixture.status)
        self.send_header("Content-Type", fixture.content_type)
        self.send_header("X-Request-ID", "fixture-upstream-request-id")
        for name, value in fixture.response_headers:
            self.send_header(name, value)
        if fixture.truncate:
            self.send_header("Content-Length", str(len(fixture.reply) + 100))
        else:
            self.send_header("Content-Length", str(len(fixture.reply)))
        self.end_headers()
        fixture.header_ready.set()
        if fixture.response_gate is not None:
            assert fixture.response_gate.wait(4)
        # Deliberately split UTF-8 and SSE lines across transport chunks.
        for offset in range(0, len(fixture.reply), 13):
            self.wfile.write(fixture.reply[offset : offset + 13])
            self.wfile.flush()
        if fixture.truncate:
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            self.close_connection = True


class ObservedHandler(Handler):
    def handle_one_request(self):
        try:
            return super().handle_one_request()
        finally:
            self.server.request_done.set()


class Harness:
    def __init__(self, path):
        self.received = []
        self.reply = response_body()
        self.content_type = "application/json"
        self.status = 200
        self.response_headers = []
        self.truncate = False
        self.disconnect_before_headers = False
        self.header_ready = threading.Event()
        self.response_gate = None
        self.upstream = FakeUpstream(("127.0.0.1", 0), UpstreamHandler)
        self.upstream.fixture = self
        upstream = f"http://127.0.0.1:{self.upstream.server_port}/provider"
        self.gateway = Gateway(
            {
                "store": str(path),
                "routes": {host: {"upstream": upstream} for host in ("codex", "claude")},
                "compression": {"memory_budget": 500, "min_history_tokens": 20},
            },
            transport=httpx.HTTPTransport(trust_env=False),
        )
        self.server = GatewayHTTPServer(("127.0.0.1", 0), self.gateway)
        self.server.RequestHandlerClass = ObservedHandler
        self.server.request_done = threading.Event()
        self.threads = [
            threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
            )
            for server in (self.upstream, self.server)
        ]
        for thread in self.threads:
            thread.start()

    def exchange(self, data, *, host="codex", path=None, headers=None, encode_chunked=False):
        self.server.request_done.clear()
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        request_headers = {
            "Content-Type": "application/json",
            "Authorization": FAKE_AUTH,
            "x-api-key": FAKE_API_KEY,
            "x-claude-code-request-class": "main",
        }
        request_headers.update(headers or {})
        target = path or f"/{host}/v1/{'responses' if host == 'codex' else 'messages'}"
        try:
            client.request(
                "POST", target, data, headers=request_headers, encode_chunked=encode_chunked
            )
            response = client.getresponse()
            body = response.read()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, body
        finally:
            client.close()
            assert self.server.request_done.wait(5), "Gateway handler did not finish"

    def close(self):
        for server in (self.server, self.upstream):
            server.shutdown()
            server.server_close()
        self.gateway.close()
        for thread in self.threads:
            thread.join(timeout=2)
            assert not thread.is_alive()


@pytest.fixture
def harness(tmp_path):
    fixture = Harness(tmp_path / "gateway.sqlite3")
    try:
        yield fixture
    finally:
        fixture.close()


@pytest.mark.parametrize("host", ["codex", "claude"])
@pytest.mark.parametrize("stream", [False, True])
def test_http_and_sse_compress_preserve_auth_headers_and_record_actual_usage(
    harness, host, stream, capsys
):
    original = payload(host, stream=stream)
    harness.reply = response_body(host, stream=stream)
    harness.content_type = "text/event-stream" if stream else "application/json"
    status, headers, body = harness.exchange(
        json.dumps(original).encode(),
        host=host,
        headers={
            "Anthropic-Version": "2023-06-01",
            "Anthropic-Beta": "fixture-feature",
            "OpenAI-Organization": "fixture-org",
            "X-Client-Request-Id": "fixture-client-id",
        },
    )
    assert status == 200 and body == harness.reply
    assert headers["x-request-id"] == "fixture-upstream-request-id"
    assert len(harness.received) == 1
    observed = harness.received[0]
    assert observed["headers"]["authorization"] == FAKE_AUTH
    assert observed["headers"]["x-api-key"] == FAKE_API_KEY
    assert observed["headers"]["anthropic-version"] == "2023-06-01"
    assert observed["headers"]["anthropic-beta"] == "fixture-feature"
    assert observed["headers"]["openai-organization"] == "fixture-org"
    assert observed["headers"]["x-client-request-id"] == "fixture-client-id"
    assert observed["headers"]["accept-encoding"] == "identity"
    rewritten = json.loads(observed["body"])
    key = "input" if host == "codex" else "messages"
    assert rewritten[key][-6:] == original[key][-6:]
    assert {k: v for k, v in rewritten.items() if k != key} == {
        k: v for k, v in original.items() if k != key
    }
    activity = harness.gateway.activity.last()
    assert activity["state"] == "forwarded" and activity["sent"]
    assert activity["before_tokens"] > activity["after_tokens"]
    assert 0 < activity["context_input_tokens"] < activity["before_tokens"]
    assert activity["provider_input_tokens"] == 750
    assert activity["provider_cached_tokens"] == (125 if host == "codex" else 150)
    assert harness.gateway.usage.summary()["preparations"] == 1
    assert (
        harness.gateway.usage.summary()["last_preparation"]["context_input_tokens"]
        == activity["context_input_tokens"]
    )
    assert len(harness.gateway.library.list()) == 1
    assert harness.gateway.activity.active() is None
    database = harness.gateway.path.read_bytes()
    assert FAKE_AUTH.encode() not in database and FAKE_API_KEY.encode() not in database
    assert not capsys.readouterr().err


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_disabled_session_passes_original_bytes_without_affecting_other_sessions(harness, host):
    harness.gateway.sessions.set_enabled(host, "disabled", False)
    original = json.dumps(payload(host, "disabled"), indent=2).encode()
    harness.reply = response_body(host)
    assert harness.exchange(original, host=host)[0] == 200
    assert harness.received[-1]["body"] == original
    assert harness.gateway.activity.last()["reason"] == "session_disabled"
    assert harness.gateway.activity.last()["sent"]
    assert harness.gateway.usage.summary()["preparations"] == 0
    assert harness.gateway.library.list() == []
    assert not harness.gateway.sessions.effective_enabled(host, "disabled")
    enabled = json.dumps(payload(host, "enabled")).encode()
    assert harness.exchange(enabled, host=host)[0] == 200
    assert harness.received[-1]["body"] != enabled
    assert harness.gateway.usage.summary()["preparations"] == 1
    assert not harness.gateway.sessions.effective_enabled(host, "disabled")


def test_unknown_identity_never_borrows_last_enabled_session(harness):
    harness.gateway.sessions.register("codex", "enabled")
    harness.gateway.sessions.set_enabled("codex", "disabled", False)
    request = payload()
    request.pop("client_metadata")
    raw = json.dumps(request).encode()
    assert harness.exchange(raw)[0] == 200
    assert harness.received[-1]["body"] == raw
    assert harness.gateway.activity.last()["session_id"] is None
    assert harness.gateway.usage.summary()["preparations"] == 0


@pytest.mark.parametrize(
    "encoding,encode", [("zstd", zstandard.ZstdCompressor().compress), ("gzip", gzip.compress)]
)
def test_encoded_request_is_decoded_only_when_rewritten(harness, encoding, encode):
    raw = json.dumps(payload()).encode()
    assert harness.exchange(encode(raw), headers={"Content-Encoding": encoding})[0] == 200
    assert "content-encoding" not in harness.received[-1]["headers"]
    assert json.loads(harness.received[-1]["body"])["model"] == "fixture-model"
    assert harness.gateway.usage.summary()["preparations"] == 1
    harness.gateway.sessions.set_enabled("codex", "fixture-session", False)
    compressed = encode(raw)
    assert harness.exchange(compressed, headers={"Content-Encoding": encoding})[0] == 200
    assert harness.received[-1]["body"] == compressed
    assert harness.received[-1]["headers"]["content-encoding"] == encoding
    assert harness.gateway.usage.summary()["preparations"] == 1


def test_request_model_is_recorded_for_pricing_but_unsafe_values_are_not(harness):
    raw = json.dumps(payload()).encode()
    assert harness.exchange(raw)[0] == 200
    assert harness.gateway.activity.last()["model"] == "fixture-model"
    request = payload()
    request["model"] = "not a model id\nwith text"
    harness.gateway.sessions.set_enabled("codex", "fixture-session", False)
    assert harness.exchange(json.dumps(request).encode())[0] == 200
    last = harness.gateway.activity.last()
    assert last["reason"] == "session_disabled" and last["model"] is None


def test_chunked_request_body_is_reassembled_and_forwarded_once(harness):
    raw = json.dumps(payload()).encode()
    parts = [raw[start : start + 79] for start in range(0, len(raw), 79)]
    assert harness.exchange(parts, encode_chunked=True)[0] == 200
    assert len(harness.received) == 1
    assert "transfer-encoding" not in harness.received[0]["headers"]
    assert (
        harness.gateway.activity.last()["before_tokens"]
        > harness.gateway.activity.last()["after_tokens"]
    )
    assert harness.gateway.usage.summary()["preparations"] == 1


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("turn", "old_history_compiled_cache_may_change"),
        ("prewarm", "auxiliary_request"),
        ("memory", "auxiliary_request"),
        ("compaction", "host_compaction_request"),
    ],
)
def test_codex_header_request_kind_allows_turn_and_preserves_auxiliary(harness, kind, reason):
    raw = json.dumps(payload()).encode()
    transformed = kind == "turn"
    assert (
        harness.exchange(
            raw, headers={"x-codex-turn-metadata": json.dumps({"request_kind": kind})}
        )[0]
        == 200
    )
    assert (harness.received[0]["body"] != raw) is transformed
    assert harness.gateway.usage.summary()["preparations"] == int(transformed)
    last = harness.gateway.activity.last()
    assert last["reason"] == reason and last["protocol_detail"]["request_kind"] == kind
    if not transformed:
        assert last["before_tokens"] is None
        assert last["after_tokens"] is None


def test_codex_turn_with_opaque_compaction_state_is_host_managed_and_content_never_stored(harness):
    request = payload()
    request["input"][2:2] = [{"type": "compaction", "encrypted_content": "FIXTURE_OPAQUE_STATE"}]
    metadata = json.dumps(
        {
            "request_kind": "turn",
            "window_number": 3,
            "agent_name": "/root",
            "thread_id": "fixture-session",
            "turn_id": "fixture-turn",
        }
    )
    raw = json.dumps(request).encode()
    assert harness.exchange(raw, headers={"x-codex-turn-metadata": metadata})[0] == 200
    assert harness.received[-1]["body"] == raw
    last = harness.gateway.activity.last()
    assert last["state"] == "passthrough" and last["sent"]
    assert last["reason"] == "native_compaction_state"
    assert last["protocol_detail"] == {
        "agent": "root",
        "compaction_items": 1,
        "request_kind": "turn",
        "window": 3,
    }
    assert harness.gateway.activity.prepared_events() == []
    database = harness.gateway.path.read_bytes()
    assert b"FIXTURE_OPAQUE_STATE" not in database and b"fixture-turn" not in database


def test_legacy_standalone_compact_endpoint_is_recorded_and_never_rewritten(harness):
    raw = json.dumps(payload()).encode()
    harness.reply = b'{"output":[]}'
    assert harness.exchange(raw, path="/codex/v1/responses/compact")[0] == 200
    assert harness.received[-1]["path"] == "/provider/v1/responses/compact"
    assert harness.received[-1]["body"] == raw
    last = harness.gateway.activity.last()
    assert last["reason"] == "host_compaction_request" and last["sent"]
    assert last["protocol_detail"]["endpoint"] == "responses_compact"
    assert harness.gateway.usage.summary()["preparations"] == 0


def test_codex_disabled_session_keeps_switch_reason_and_records_compaction_detail(harness):
    harness.gateway.sessions.set_enabled("codex", "fixture-session", False)
    request = payload()
    request["input"].append({"type": "compaction_trigger"})
    metadata = json.dumps(
        {"request_kind": "compaction", "compaction": {"trigger": "auto", "phase": "pre_turn"}}
    )
    assert (
        harness.exchange(json.dumps(request).encode(), headers={"x-codex-turn-metadata": metadata})[
            0
        ]
        == 200
    )
    last = harness.gateway.activity.last()
    assert last["reason"] == "session_disabled"
    assert last["protocol_detail"]["compaction_trigger"] == "auto"


@pytest.mark.parametrize(
    "headers,reason,detail",
    [
        (
            {"x-claude-code-request-class": "compaction", "x-claude-code-compaction": "auto"},
            "host_compaction_request",
            {"request_class": "compaction", "compaction_trigger": "auto"},
        ),
        (
            {"x-claude-code-request-class": "main", "x-claude-code-compaction": "reactive"},
            "host_compaction_request",
            {"request_class": "main", "compaction_trigger": "reactive"},
        ),
        (
            {"x-claude-code-request-class": "subagent", "x-claude-code-agent-id": "fixture-agent"},
            "non_main_request",
            {"request_class": "subagent", "agent": "subagent"},
        ),
    ],
)
def test_claude_host_compaction_and_side_requests_are_labelled(harness, headers, reason, detail):
    raw = json.dumps(payload("claude")).encode()
    harness.reply = response_body("claude")
    assert harness.exchange(raw, host="claude", headers=headers)[0] == 200
    assert harness.received[-1]["body"] == raw
    last = harness.gateway.activity.last()
    assert last["reason"] == reason and last["protocol_detail"] == detail
    assert b"fixture-agent" not in harness.gateway.path.read_bytes()


def test_claude_native_reset_reaches_stateful_adapter_and_removes_previous_mapping(harness):
    raw = json.dumps(payload("claude")).encode()
    harness.reply = response_body("claude")
    assert harness.exchange(raw, host="claude")[0] == 200
    with sqlite3.connect(harness.gateway.path) as db:
        assert db.execute("SELECT COUNT(*) FROM tomc_anthropic_prefixes").fetchone()[0] == 1
    assert (
        harness.exchange(raw, host="claude", headers={"x-claude-code-context-compacted": "1"})[0]
        == 200
    )
    assert harness.received[-1]["body"] == raw
    assert harness.gateway.activity.last()["reason"] == "native_compaction_reset"
    with sqlite3.connect(harness.gateway.path) as db:
        assert db.execute("SELECT COUNT(*) FROM tomc_anthropic_prefixes").fetchone()[0] == 0
    assert harness.gateway.usage.summary()["preparations"] == 1


def test_claude_disabled_existing_signed_prefix_is_compatible_replay_without_new_growth(harness):
    request = payload("claude")
    raw = json.dumps(request).encode()
    harness.reply = response_body("claude")
    assert harness.exchange(raw, host="claude")[0] == 200
    established = json.loads(harness.received[-1]["body"])["messages"][0]
    harness.gateway.sessions.set_enabled("claude", "fixture-session", False)
    request["messages"].extend(
        [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "fixture private block",
                        "signature": "fixture signature",
                    },
                    {"type": "tool_use", "id": "tool-fixture", "name": "lookup", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool-fixture", "content": "42"}
                ],
            },
        ]
    )
    assert harness.exchange(json.dumps(request).encode(), host="claude")[0] == 200
    observed = json.loads(harness.received[-1]["body"])
    assert observed["messages"][0] == established
    assert observed["messages"][-2:] == request["messages"][-2:]
    assert harness.gateway.activity.last()["reason"] == "disabled_compatible_replay"
    assert harness.gateway.usage.summary()["preparations"] == 1


@pytest.mark.parametrize(
    "raw,encoding",
    [
        (b"not a JSON document", ""),
        (b"[]", ""),
        (b"null", ""),
        (b"\xff\xfe\x80", ""),
        (b"opaque encoded body", "future-provider-encoding"),
        (b"invalid zstd", "zstd"),
        (gzip.compress(b"{}")[0:5], "gzip"),
    ],
)
def test_unsupported_or_malformed_payload_is_forwarded_unchanged(harness, raw, encoding):
    status, _, _ = harness.exchange(raw, headers={"Content-Encoding": encoding})
    assert status == 200 and len(harness.received) == 1
    assert harness.received[0]["body"] == raw
    assert harness.received[0]["headers"].get("content-encoding", "") == encoding
    assert harness.gateway.usage.summary()["preparations"] == 0


@pytest.mark.parametrize(
    "encoding,encode", [("zstd", zstandard.ZstdCompressor().compress), ("gzip", gzip.compress)]
)
def test_decoded_body_size_limit_also_applies_to_frames_with_known_size(
    monkeypatch, encoding, encode
):
    monkeypatch.setattr(request_gateway, "MAX_BODY", 32)
    with pytest.raises(ValueError, match="large"):
        decode_body(encode(b"x" * 512), encoding)


def test_hop_by_hop_headers_are_removed_in_both_directions(harness):
    harness.response_headers = [
        ("Connection", "keep-alive, X-Upstream-Private"),
        ("X-Upstream-Private", "must-not-cross-proxy"),
    ]
    status, headers, _ = harness.exchange(
        json.dumps(payload()).encode(),
        headers={
            "Connection": "keep-alive, X-Client-Private",
            "X-Client-Private": "must-not-cross-proxy",
        },
    )
    assert status == 200
    assert "x-client-private" not in harness.received[0]["headers"]
    assert "x-upstream-private" not in headers


@pytest.mark.parametrize(
    "path",
    [
        "/codex/../admin",
        "/codex/%2e%2e/admin",
        "/codex/%2E%2E/admin",
        "/codex/a/%2e%2e/admin",
        "/codex/%2e%2e%5cadmin",
        "/codex/v1\\..\\admin",
        "http://external.invalid/codex/v1/responses",
        "//external.invalid/codex/v1/responses",
    ],
)
def test_unsafe_paths_never_reach_upstream(harness, path):
    assert harness.exchange(b"{}", path=path)[0] in {400, 403, 404}
    assert harness.received == []


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"Host": "external.invalid"}, 403),
        ({"Origin": "https://external.invalid"}, 403),
        ({"Transfer-Encoding": "chunked", "Content-Length": "2"}, 400),
        ({"Content-Length": "-1"}, 400),
        ({"Content-Length": str(1024**3)}, 400),
    ],
)
def test_invalid_host_browser_or_body_framing_is_rejected(harness, headers, status):
    assert harness.exchange(b"{}", headers=headers)[0] == status
    assert harness.received == []


def test_unknown_routes_and_health_never_forward(harness):
    assert harness.exchange(b"{}", path="/other/v1/responses")[0] == 404
    connection = http.client.HTTPConnection("127.0.0.1", harness.server.server_port, timeout=5)
    try:
        connection.request("GET", "/health")
        result = connection.getresponse()
        assert result.status == 200 and json.loads(result.read())["ready"]
    finally:
        connection.close()
    assert harness.received == []


def test_websocket_upgrade_returns_codex_http_fallback_without_upstream_call(harness):
    status, _, body = harness.exchange(
        b"", headers={"Connection": "Upgrade", "Upgrade": "websocket"}
    )
    assert status == 426 and json.loads(body)["error"]["code"] == "use_http_sse"
    assert harness.received == []


def test_safe_query_and_non_target_endpoint_are_preserved(harness):
    raw = b' { "fixture" : true } '
    assert harness.exchange(raw, path="/codex/v1/models?limit=4&cursor=fixture")[0] == 200
    assert harness.received[0]["path"] == "/provider/v1/models?limit=4&cursor=fixture"
    assert harness.received[0]["body"] == raw
    assert harness.gateway.activity.summary()["total_requests"] == 0


@pytest.mark.parametrize("failure", ["http", "sse_error", "incomplete", "truncated", "disconnect"])
def test_upstream_failures_do_not_grow_pet_or_retry_request(harness, failure):
    if failure == "http":
        harness.status = 429
        harness.reply = b'{"error":{"message":"fixture rate limit"}}'
    elif failure == "sse_error":
        harness.content_type = "text/event-stream"
        harness.reply = response_body(stream=True, failed=True)
    elif failure == "incomplete":
        harness.content_type = "text/event-stream"
        harness.reply = b'data: {"type":"response.output_text.delta","delta":"unfinished"}\n\n'
    elif failure == "truncated":
        harness.truncate = True
        harness.content_type = "text/event-stream"
        harness.reply = b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n'
    else:
        harness.disconnect_before_headers = True
    try:
        status, _, _ = harness.exchange(json.dumps(payload()).encode())
        assert status == (429 if failure == "http" else 502 if failure == "disconnect" else 200)
    except http.client.IncompleteRead:
        assert failure == "truncated"
    assert len(harness.received) == 1
    assert harness.gateway.usage.summary()["preparations"] == 0
    assert harness.gateway.library.list() == []
    assert harness.gateway.activity.active() is None
    if failure in {"truncated", "disconnect"}:
        assert harness.gateway.activity.last()["reason"] == "upstream_transport_failed"


def test_client_disconnect_is_recorded_separately_from_upstream_failure(harness):
    harness.content_type = "text/event-stream"
    harness.reply = b'data: {"type":"response.output_text.delta","delta":"x"}\n\n' * 8000
    harness.response_gate = threading.Event()
    raw = json.dumps(payload()).encode()
    harness.server.request_done.clear()
    client = socket.create_connection(("127.0.0.1", harness.server.server_port), timeout=5)
    # Close with a reset, as a cancelled host turn does, so the next relay write fails.
    linger = struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    client.sendall(
        b"POST /codex/v1/responses HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        b"Content-Type: application/json\r\n" + f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw
    )
    try:
        assert harness.header_ready.wait(3)
    finally:
        client.close()
        harness.response_gate.set()
    assert harness.server.request_done.wait(5)
    last = harness.gateway.activity.last()
    assert last["state"] == "failed" and last["reason"] == "client_disconnected" and last["sent"]


def test_compiler_failure_preserves_original_and_does_not_claim_reduction(harness, monkeypatch):
    from tomc import responses_request

    def broken(*args, **kwargs):
        raise RuntimeError("fixture compiler failure")

    monkeypatch.setattr(responses_request, "adapt_request", broken)
    original = json.dumps(payload(), indent=2).encode()
    assert harness.exchange(original)[0] == 200
    assert harness.received[0]["body"] == original
    assert harness.gateway.activity.last()["reason"] == "preparation_failed"
    assert harness.gateway.usage.summary()["preparations"] == 0


@pytest.mark.parametrize("response", [b'[{"error":"fixture"}]', b"null", b"not json", b"{}"])
def test_unrecognized_response_json_does_not_invent_completion(harness, response):
    harness.reply = response
    assert harness.exchange(json.dumps(payload()).encode())[2] == response
    assert harness.gateway.usage.summary()["preparations"] == 0
    assert harness.gateway.library.list() == []


def test_model_stream_lifetime_is_not_cpu_preparation_lifetime(harness):
    harness.response_gate = threading.Event()
    result = []
    worker = threading.Thread(
        target=lambda: result.append(harness.exchange(json.dumps(payload()).encode()))
    )
    worker.start()
    try:
        assert harness.header_ready.wait(3)
        assert harness.gateway.activity.active() is None
        assert harness.gateway.activity.last()["provider_input_tokens"] is None
        assert harness.gateway.activity.last()["context_input_tokens"] > 0
        assert harness.gateway.usage.summary()["preparations"] == 0
    finally:
        harness.response_gate.set()
        worker.join(timeout=5)
    assert not worker.is_alive() and result[0][0] == 200
    assert harness.gateway.activity.last()["provider_input_tokens"] == 750


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_context_length_comes_from_compiler_before_transport_not_whole_json(harness, host):
    original = payload(host)
    request_id, session_id, plan, _, changed = harness.gateway.prepare(
        host,
        "/v1/responses" if host == "codex" else "/v1/messages",
        {"x-claude-code-request-class": "main"},
        json.dumps(original).encode(),
    )
    assert changed and plan.prepared is not None
    context_input = plan.prepared.compilation.stats.input_tokens
    activity = harness.gateway.activity.last()
    assert activity["state"] == "prepared" and not activity["sent"]
    assert activity["context_input_tokens"] == context_input
    prepared_events = harness.gateway.activity.prepared_events()
    assert len(prepared_events) == 1
    assert prepared_events[0]["request_id"] == request_id
    assert prepared_events[0]["context_input_tokens"] == context_input
    assert activity["before_tokens"] == plan.before_tokens != context_input
    assert harness.gateway.usage.summary()["preparations"] == 0
    harness.gateway.activity.sent(request_id)
    metrics = ResponseMetrics(False)
    metrics.feed(response_body(host))
    metrics.end()
    harness.gateway.complete(request_id, host, session_id, plan, metrics)
    harness.gateway.complete(request_id, host, session_id, plan, metrics)
    assert harness.gateway.usage.summary()["preparations"] == 1
    assert harness.gateway.usage.summary()["last_preparation"]["input_tokens"] == plan.before_tokens
    assert (
        harness.gateway.usage.summary()["last_preparation"]["context_input_tokens"] == context_input
    )
    assert harness.gateway.usage.recent_events()[0]["context_input_tokens"] == context_input
    assert harness.gateway.activity.prepared_events() == prepared_events


def test_claude_replay_does_not_claim_a_new_compiled_context_length(harness):
    original = payload("claude")
    harness.reply = response_body("claude")
    raw = json.dumps(original).encode()
    assert harness.exchange(raw, host="claude")[0] == 200
    assert harness.gateway.activity.last()["context_input_tokens"] > 0
    assert harness.exchange(raw, host="claude")[0] == 200
    replay = harness.gateway.activity.last()
    assert replay["reason"] == "replayed_prefix"
    assert replay["context_input_tokens"] is None
    assert len(harness.gateway.activity.prepared_events()) == 1
    # Preserve the existing request-level totals while identifying no new compilation.
    assert harness.gateway.usage.summary()["preparations"] == 2
    assert harness.gateway.usage.summary()["last_preparation"]["context_input_tokens"] is None
    assert harness.gateway.usage.recent_events()[-1]["context_input_tokens"] is None


def test_usage_parser_preserves_unknown_and_handles_split_sse_without_output_retention():
    metrics = ResponseMetrics(True)
    raw = response_body("claude", stream=True)
    for byte in raw:
        metrics.feed(bytes([byte]))
    metrics.end()
    assert metrics.completed and not metrics.failed
    assert metrics.input_tokens == 750 and metrics.cached_tokens == 150
    assert metrics.buffer == b""
    empty = ResponseMetrics(False)
    empty.feed(b'{"content":[]}')
    empty.end()
    assert empty.input_tokens is None and empty.cached_tokens is None


@pytest.mark.parametrize("content_type", ["application/json", "text/plain", "TEXT/EVENT-STREAM"])
def test_sse_usage_is_detected_even_with_generic_upstream_content_type(harness, content_type):
    harness.content_type = content_type
    harness.reply = response_body(stream=True)
    assert harness.exchange(json.dumps(payload(stream=True)).encode())[2] == harness.reply
    assert harness.gateway.activity.last()["provider_input_tokens"] == 750
    assert harness.gateway.usage.summary()["preparations"] == 1


def test_sse_detection_handles_first_prefix_split_across_chunks():
    metrics = ResponseMetrics(False)
    raw = (
        b"event: response.completed\ndata: "
        + json.dumps(
            {"type": "response.completed", "response": {"usage": {"input_tokens": 77}}}
        ).encode()
        + b"\n\n"
    )
    for byte in raw:
        metrics.feed(bytes([byte]))
    metrics.end()
    assert metrics.sse and metrics.completed and metrics.input_tokens == 77


@pytest.mark.parametrize(
    "upstream",
    [
        "http://external.invalid/v1",
        "https://name:secret@external.invalid/v1",
        "https://external.invalid/v1?key=secret",
        "https://external.invalid/v1#secret",
        "file:///tmp/fixture",
        "https:///missing-host",
    ],
)
def test_upstream_configuration_rejects_nonlocal_http_and_credential_urls(tmp_path, upstream):
    with pytest.raises(ValueError):
        Gateway(
            {"store": str(tmp_path / "unused.sqlite3"), "routes": {"codex": {"upstream": upstream}}}
        )
    assert not (tmp_path / "unused.sqlite3").exists()
