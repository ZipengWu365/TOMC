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
            }
            assert tools["forget_memory"].annotations.destructiveHint
            assert tools["recall_memory"].annotations.readOnlyHint
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
            notebooks = await call(client, "list_memories")
            assert len(notebooks["notebooks"]) == 2
            await call(client, "forget_memory", {"name": "parser"})
            assert len((await call(client, "list_memories"))["notebooks"]) == 1
            missing = await client.call_tool(
                "recall_memory", {"name": "parser", "task": "continue"}
            )
            assert missing.isError

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
