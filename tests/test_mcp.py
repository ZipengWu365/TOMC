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
                "try_tomc",
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
                "erase_all_memory",
            }
            assert tools["forget_memory"].annotations.destructiveHint
            assert tools["erase_all_memory"].annotations.destructiveHint
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
        # Saving MCP results is opt-in; this user turned it on.
        from tomc.session_store import SessionStore

        SessionStore(tmp_path / "memory.sqlite3").update_settings(save_mcp_results=True)
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
            assert (await call(client, "get_context", {"context_id": snapshot_id}))[
                "memory"
            ] == "A temporary note"
            prompt = await call(client, "make_handoff", {"context_id": snapshot_id})
            assert "A temporary note" in prompt["prompt"]
            assert len((await call(client, "list_contexts"))["contexts"]) == 2
            stats = await call(client, "get_usage_stats")
            assert stats["preparations"] == 2
            assert (await call(client, "get_usage_stats")) == stats
            notebooks = await call(client, "list_memories")
            assert len(notebooks["notebooks"]) == 2
            forgotten = await call(client, "forget_memory", {"name": "parser"})
            # The recall snapshot derived from the notebook goes with it.
            assert forgotten["deleted_entries"] == 1 and forgotten["deleted_snapshots"] == 1
            assert [c["source"] for c in (await call(client, "list_contexts"))["contexts"]] == [
                "prepare"
            ]
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
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "tomc", "mcp", "--store", str(database)]
        )
        async with connected(params) as client:

            async def call(tool, args=None):
                result = await client.call_tool(tool, args)
                assert not result.isError, result
                return json.loads(result.content[0].text)

            arguments = {
                "history": "project = TOMC",
                "task": "Continue project",
                "tomc_host": "codex",
                "tomc_session_id": "chat-a",
            }
            assert (await call("prepare_context", arguments))["status"] == "paused"
            assert (await call("get_usage_stats"))["preparations"] == 0
            assert (await call("list_contexts"))["contexts"] == []
            arguments["tomc_session_id"] = "chat-b"
            result = await call("prepare_context", arguments)
            assert result["status"] == "prepared"
            assert result["details"]["session_id"] == "chat-b"
            assert not result["details"]["request_replacement_verified"]
            # Results are not saved by default.
            assert result["context_record"] == {
                "status": "disabled",
                "setting": "save_mcp_results",
            }
            assert (await call("list_contexts"))["contexts"] == []
            sessions.update_settings(save_mcp_results=True)
            result = await call("prepare_context", arguments)
            assert result["context_record"]["status"] == "saved"
            sessions.update_settings(save_contexts=False)
            result = await call("prepare_context", arguments)
            assert result["context_record"]["status"] == "disabled"
            assert (await call("get_usage_stats"))["preparations"] == 3
            assert len((await call("list_contexts"))["contexts"]) == 1
            # A globally active card must never attribute an unidentified call to chat-b.
            result = await call("prepare_context", {"history": "unassociated", "task": "continue"})
            assert result["status"] == "identity_required" and not result["prepared"]
            assert (await call("get_usage_stats"))["preparations"] == 3
            sessions.set_enabled("codex", "chat-a", True)
            result = await call("prepare_context", {"history": "unassociated", "task": "continue"})
            assert result["details"]["session_id"] is None
            assert result["details"]["attribution"] == "unassociated"
            sessions.update_settings(enabled=False)
            assert (await call("prepare_context", arguments))["status"] == "paused"
            assert (await call("get_usage_stats"))["preparations"] == 4
            unknown = await client.call_tool(
                "prepare_context", {**arguments, "tomc_session_id": "missing"}
            )
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


FAKE_KEY = "sk-" + "FAKE0123456789abcdefSECRET"  # Split: keeps the release scan clean.
SENTENCE = "The quarterly migration plan moves billing to the new cluster"


def test_default_mcp_calls_store_no_conversation_text_and_erase_all_needs_confirmation(
    tmp_path,
):
    database = tmp_path / "memory.sqlite3"
    history = f"{SENTENCE}. OPENAI_API_KEY={FAKE_KEY}\nNext we verify the rollout."

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "tomc", "mcp", "--store", str(database)]
        )
        async with connected(params) as client:

            async def call(tool, args=None):
                result = await client.call_tool(tool, args)
                assert not result.isError, result
                return json.loads(result.content[0].text)

            prepared = await call("prepare_context", {"history": history, "task": SENTENCE})
            assert SENTENCE in prepared["memory"]
            assert prepared["context_record"]["status"] == "disabled"
            assert (await call("list_contexts"))["contexts"] == []
            raw = database.read_bytes()
            assert FAKE_KEY.encode() not in raw and SENTENCE.encode() not in raw
            # Only the explicit save tool stores text; erasing removes it again.
            await call("remember_memory", {"name": "plan", "content": history})
            recalled = await call("recall_memory", {"name": "plan", "task": "continue"})
            assert recalled["context_record"]["status"] == "disabled"
            assert (await call("list_contexts"))["contexts"] == []
            refused = await call("erase_all_memory", {"confirm": "yes"})
            assert refused["status"] == "confirmation_required" and not refused["erased"]
            assert len((await call("list_memories"))["notebooks"]) == 1
            erased = await call("erase_all_memory", {"confirm": "ERASE ALL"})
            assert erased["erased"] and erased["deleted"]["entries"] == 1
            assert (await call("list_memories"))["notebooks"] == []

    asyncio.run(run())
    raw = database.read_bytes()
    assert FAKE_KEY.encode() not in raw and SENTENCE.encode() not in raw


def _initialize(proc):
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "lifecycle-test", "version": "1"},
        },
    }
    proc.stdin.write((json.dumps(message) + "\n").encode())
    proc.stdin.flush()
    assert b'"result"' in proc.stdout.readline()


def test_server_exits_when_the_client_closes_stdin(tmp_path):
    import subprocess

    proc = subprocess.Popen(
        [sys.executable, "-m", "tomc", "mcp", "--store", str(tmp_path / "m.sqlite3")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        _initialize(proc)
        proc.stdin.close()
        assert proc.wait(timeout=15) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()


@pytest.mark.skipif(sys.platform == "win32", reason="uses a POSIX pipe and process check")
def test_server_exits_when_its_parent_dies_without_closing_stdin(tmp_path):
    """A killed wrapper (for example uv run) leaves stdin open; the server must still stop."""
    import os
    import subprocess
    import time

    read, write = os.pipe()
    launcher = (
        "import subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-m', 'tomc', 'mcp', '--store', sys.argv[1]],"
        " stdin=int(sys.argv[2]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,"
        " pass_fds=(int(sys.argv[2]),))\n"
        "print(child.pid, flush=True)\n"
        "sys.stdin.readline()\n"
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", launcher, str(tmp_path / "m.sqlite3"), str(read)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        pass_fds=(read,),
    )
    os.close(read)
    try:
        server = int(parent.stdout.readline())
        time.sleep(1)
        os.kill(server, 0)  # Running, and its stdin (our pipe) is still open.
        parent.kill()
        parent.wait(timeout=10)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                os.kill(server, 0)
            except ProcessLookupError:
                break
            time.sleep(0.2)
        else:
            os.kill(server, 9)
            pytest.fail("The MCP server outlived its parent process")
    finally:
        os.close(write)
        parent.stdin.close()
        parent.stdout.close()
