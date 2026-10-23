"""Real stdio SDK client: tool discovery, calls, restart, isolation and deletion."""

import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@asynccontextmanager
async def connected(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def test_stdio_memory_roundtrip(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tomc", "mcp", "--store", str(tmp_path / "memory.sqlite3")],
        )

        async def call(client, tool, args=None):
            result = await client.call_tool(tool, args)
            assert not result.isError, result
            return json.loads(result.content[0].text)

        async with connected(params) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == {
                "prepare_context",
                "remember_memory",
                "recall_memory",
                "list_memories",
                "forget_memory",
                "get_usage_stats",
                "get_status",
                "list_contexts",
                "get_context",
                "make_handoff",
            }
            assert tools["forget_memory"].annotations.destructiveHint
            assert not tools["recall_memory"].annotations.readOnlyHint
            assert not tools["prepare_context"].annotations.readOnlyHint
            assert tools["get_usage_stats"].annotations.readOnlyHint
            assert not tools["remember_memory"].annotations.readOnlyHint
            await call(
                client,
                "remember_memory",
                {"name": "parser", "content": "Focused tests passed. Full suite is unverified."},
            )
            await call(
                client, "remember_memory", {"name": "other", "content": "Other project secret."}
            )
        # A genuinely new process must see the saved local notebook.
        async with connected(params) as client:
            memory = await call(
                client, "recall_memory", {"name": "parser", "task": "What should we do next?"}
            )
            assert "unverified" in memory["memory"] and "secret" not in memory["memory"]
            prepared = await call(
                client, "prepare_context", {"history": "A temporary note", "task": "continue"}
            )
            assert prepared["memory"] == "A temporary note"
            assert prepared["context_reduction"]["reduced_tokens"] == 0
            assert prepared["context_reduction"]["recorded"]
            assert prepared["context_record"]["status"] == "saved"
            snapshot_id = prepared["context_record"]["id"]
            assert (await call(client, "get_context", {"context_id": snapshot_id}))["memory"] == "A temporary note"
            prompt = await call(client, "make_handoff", {"context_id": snapshot_id})
            assert "A temporary note" in prompt["prompt"]
            assert len((await call(client, "list_contexts"))["contexts"]) == 2
            stats = await call(client, "get_usage_stats")
            assert stats["preparations"] == 2
            assert (await call(client, "get_usage_stats")) == stats
            notebooks = await call(client, "list_memories")
            assert len(notebooks["notebooks"]) == 2
            await call(client, "forget_memory", {"name": "parser"})
            assert len((await call(client, "list_memories"))["notebooks"]) == 1
            missing = await client.call_tool(
                "recall_memory", {"name": "parser", "task": "continue"}
            )
            assert missing.isError

        async with connected(params) as client:
            assert (await call(client, "get_usage_stats"))["preparations"] == 2

    asyncio.run(run())


def test_session_pause_and_recording_are_independent(tmp_path):
    from tomc.session_store import SessionStore

    database = tmp_path / "session.sqlite3"
    sessions = SessionStore(database)
    sessions.register("codex", "chat-a", title="Paused chat")
    sessions.register("codex", "chat-b", title="Enabled chat")
    sessions.set_enabled("codex", "chat-a", False)

    async def run():
        params = StdioServerParameters(command=sys.executable,
                                      args=["-m", "tomc", "mcp", "--store", str(database)])
        async with connected(params) as client:
            async def call(tool, args=None):
                result = await client.call_tool(tool, args)
                assert not result.isError, result
                return json.loads(result.content[0].text)

            arguments = {"history": "project = TOMC", "task": "Continue project",
                         "tomc_host": "codex", "tomc_session_id": "chat-a"}
            assert (await call("prepare_context", arguments))["status"] == "paused"
            assert (await call("get_usage_stats"))["preparations"] == 0
            assert (await call("list_contexts"))["contexts"] == []
            arguments["tomc_session_id"] = "chat-b"
            result = await call("prepare_context", arguments)
            assert result["status"] == "prepared" and result["session_id"] == "chat-b"
            assert not result["request_replacement_verified"]
            sessions.update_settings(save_contexts=False)
            result = await call("prepare_context", arguments)
            assert result["context_record"]["status"] == "disabled"
            assert (await call("get_usage_stats"))["preparations"] == 2
            assert len((await call("list_contexts"))["contexts"]) == 1
            # A globally active card must never attribute an unidentified call to chat-b.
            result = await call("prepare_context", {"history": "unassociated", "task": "continue"})
            assert result["status"] == "identity_required" and not result["prepared"]
            assert (await call("get_usage_stats"))["preparations"] == 2
            sessions.set_enabled("codex", "chat-a", True)
            result = await call("prepare_context", {"history": "unassociated", "task": "continue"})
            assert result["session_id"] is None and result["attribution"] == "unassociated"
            sessions.update_settings(enabled=False)
            assert (await call("prepare_context", arguments))["status"] == "paused"
            assert (await call("get_usage_stats"))["preparations"] == 3
            unknown = await client.call_tool("prepare_context", {**arguments, "tomc_session_id": "missing"})
            assert unknown.isError

    asyncio.run(run())


@pytest.mark.parametrize("version", ["2024-11-05", "2025-03-26"])
def test_legacy_client_handshake_and_tool_call(tmp_path, version):
    async def run():
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tomc",
            "mcp",
            "--store",
            str(tmp_path / "legacy.sqlite3"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        async def send(message):
            proc.stdin.write((json.dumps(message) + "\n").encode())
            await proc.stdin.drain()

        try:
            await send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "legacy-test", "version": "1"},
                    },
                }
            )
            result = json.loads(await asyncio.wait_for(proc.stdout.readline(), 10))
            assert result["result"]["protocolVersion"] == version
            await send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            await send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "prepare_context",
                        "arguments": {"history": "Full suite is unverified.", "task": "continue"},
                    },
                }
            )
            result = json.loads(await asyncio.wait_for(proc.stdout.readline(), 10))
            assert result["id"] == 2 and not result["result"].get("isError")
            assert "unverified" in result["result"]["content"][0]["text"]
        finally:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), 10)

    asyncio.run(run())
