"""Exercise the extracted MCPB's locked UV runtime through a real MCP client."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from zipfile import ZipFile

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def runtime_environment(root: Path, database: Path) -> dict[str, str]:
    """Keep smoke-test downloads temporary while respecting explicit runtime paths."""

    def directory(name: str, fallback: Path) -> str:
        return str(Path(os.environ.get(name) or fallback).expanduser().resolve())

    env = {
        "TOMC_MEMORY_PATH": str(database),
        "UV_CACHE_DIR": directory("UV_CACHE_DIR", root / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": directory("UV_PYTHON_INSTALL_DIR", root / "uv-python"),
    }
    if "UV_PYTHON" in os.environ:
        env["UV_PYTHON"] = os.environ["UV_PYTHON"]
    return env


async def check(bundle: Path, uv: str) -> dict:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="tomc-plugin-") as folder:
        root = Path(folder)
        install = root / "Moved installation 测试"
        with ZipFile(bundle) as archive:
            for name in archive.namelist():
                if Path(name).is_absolute() or ".." in Path(name).parts:
                    raise ValueError("Unsafe archive path")
            archive.extractall(install)
        # The client invokes the same command as the manifest, outside the checkout.
        manifest = json.loads((install / "manifest.json").read_text(encoding="utf-8"))
        config = manifest["server"]["mcp_config"]
        args = [arg.replace("${__dirname}", str(install)) for arg in config["args"]]
        database = root / "user-data" / "memory.sqlite3"
        params = StdioServerParameters(
            command=uv,
            args=args,
            cwd=str(root),
            env=runtime_environment(root, database),
        )

        @asynccontextmanager
        async def connected():
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    yield client

        async def call(client, tool, arguments=None):
            reply = await client.call_tool(tool, arguments)
            assert not reply.isError, f"Tool failed: {tool}"
            return json.loads(reply.content[0].text)

        async with connected() as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert tools == {
                "prepare_context",
                "remember_memory",
                "recall_memory",
                "list_memories",
                "forget_memory",
            }
            await call(
                client,
                "remember_memory",
                {
                    "name": "workshop",
                    "content": "人数28人。B会议室有空，但尚未预订。无障碍设施待确认。",
                },
            )
            await call(client, "remember_memory", {"name": "other", "content": "隔离主题测试"})
        async with connected() as client:
            memory = await call(
                client, "recall_memory", {"name": "workshop", "task": "会议室还有什么需要确认？"}
            )
            assert "尚未预订" in memory["memory"] and "待确认" in memory["memory"]
            assert "隔离主题" not in memory["memory"]
            assert len((await call(client, "list_memories"))["notebooks"]) == 2
            prepared = await call(
                client,
                "prepare_context",
                {"history": "Temporary note / 临时笔记", "task": "continue"},
            )
            assert "临时笔记" in prepared["memory"]
            await call(client, "forget_memory", {"name": "workshop"})
            assert (await call(client, "list_memories"))["notebooks"][0]["name"] == "other"
        assert database.exists() and not list(install.rglob("*.sqlite3"))
        return {
            "status": "pass",
            "bundle": bundle.name,
            "tools": sorted(tools),
            "checks": "locked isolated runtime; Chinese notes; restart recall; notebook isolation; prepare; delete; external database; path with spaces and Chinese",
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "desktop_gui": "not tested; requires Claude Desktop or Cursor on the target machine",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--uv", default=shutil.which("uv"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.uv:
        parser.error("UV is required for this runtime check")
    result = asyncio.run(asyncio.wait_for(check(args.bundle, args.uv), timeout=180))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
