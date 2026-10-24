"""Results fit one tool output, and repeat calls in a conversation send only changes."""

import asyncio
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from tomc.easy import prepare_context
from tomc.tokenization import get_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "adaptive"))
from suite import note_cases, two_hop_cases  # noqa: E402

COUNTER = get_counter("regex")


def broad():
    case = two_hop_cases()[-1]  # about 3,500 lines of document text
    return case.history, "Summarize the release work, incidents and reviews in these notes."


def test_max_chars_keeps_the_most_relevant_memory_within_one_tool_output():
    history, task = broad()
    full = prepare_context(history, task).compilation
    assert len(full.compiled_memory) > 100_000
    capped = prepare_context(history, task, max_chars=20_000)
    result = capped.compilation
    assert 15_000 <= len(result.compiled_memory) <= 20_000
    limit = result.diagnostics["delivery_limit"]
    assert limit["max_chars"] == 20_000 and limit["budget"] < limit["requested_budget"]
    assert "within 20,000 characters" in capped.note


def test_max_chars_also_limits_tokens_for_chinese_text():
    lines = [f"第{i}条记录：项目进展正常，团队完成了例行检查和文档更新。" for i in range(3000)]
    prepared = prepare_context("\n".join(lines), "总结项目进展", max_chars=8_000)
    assert prepared.compilation.stats.output_tokens <= 2_000
    assert len(prepared.compilation.compiled_memory) <= 8_000


def test_cli_prepare_can_fit_an_agent_tool_output():
    history, task = broad()
    run = subprocess.run(
        [sys.executable, "-m", "tomc", "prepare", "-", "--task", task, "--max-chars", "8000"],
        input=history,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    memory = run.stdout.split("MEMORY\n", 1)[1].split("\n\nTASK\n", 1)[0]
    assert 4_000 < len(memory) <= 8_000


def test_a_history_within_the_limit_is_unchanged():
    case = note_cases()[0]
    plain = prepare_context(case.history, case.task, 4096).compilation
    limited = prepare_context(case.history, case.task, 4096, max_chars=50_000).compilation
    assert limited.compiled_memory == plain.compiled_memory
    assert "delivery_limit" not in limited.diagnostics


mcp = pytest.importorskip("mcp")
from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import (  # noqa: E402
    StdioServerParameters,
    get_default_environment,
    stdio_client,
)


@asynccontextmanager
async def connected(params):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def server(tmp_path, **env):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "tomc", "mcp", "--store", str(tmp_path / "memory.sqlite3")],
        env={**get_default_environment(), **env},
    )


async def call(client, tool, args):
    result = await client.call_tool(tool, args)
    assert not result.isError, result
    return json.loads(result.content[0].text)


def test_mcp_results_fit_one_tool_output(tmp_path):
    history, task = broad()

    async def run():
        async with connected(server(tmp_path)) as client:
            reply = await call(client, "prepare_context", {"history": history, "task": task})
            assert reply["max_chars"] == 20_000
            assert len(reply["memory"]) <= 20_000 and reply["delivery"]["kind"] == "full"
        async with connected(server(tmp_path, TOMC_MCP_MAX_CHARS="6000")) as client:
            reply = await call(client, "prepare_context", {"history": history, "task": task})
            assert reply["max_chars"] == 6_000 and len(reply["memory"]) <= 6_000

    asyncio.run(run())


def test_mcp_repeat_calls_send_only_changes(tmp_path):
    case = note_cases()[0]
    changed = case.history.replace("**amber**", "**jade**", 1)

    async def run():
        async with connected(server(tmp_path)) as client:

            async def prepare(history, since=None):
                args = {"history": history, "task": case.task}
                if since:
                    args["since_delivery_id"] = since
                return await call(client, "prepare_context", args)

            first = await prepare(case.history)
            assert first["delivery"]["kind"] == "full"
            assert "The current release channel is **amber**." in first["memory"]
            same = await prepare(case.history, first["delivery"]["id"])
            assert same["delivery"]["kind"] == "unchanged"
            assert same["delivery"]["estimated_tokens"] < 50
            assert "Only what changed since TOMC delivery" in same["note"]
            update = await prepare(changed, same["delivery"]["id"])
            assert update["delivery"]["kind"] == "update"
            assert "now: The current release channel is **jade**." in update["memory"]
            # A superseded or unknown ID never yields changes without their base.
            assert (await prepare(changed, first["delivery"]["id"]))["delivery"]["kind"] == "full"
            assert (await prepare(changed, "d-unknown"))["delivery"]["kind"] == "full"

    asyncio.run(run())
