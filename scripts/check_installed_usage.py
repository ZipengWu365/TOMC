"""Exercise the actually registered TOMC runtime, with a separate numeric test DB."""

import argparse
import asyncio
import json
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def run(config_path: Path, output: Path, batch: int):
    config = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"]["tomc"]
    database = output / "widget_test.sqlite3"
    params = StdioServerParameters(
        command=config["command"],
        args=config["args"],
        env={**config.get("env", {}), "TOMC_MEMORY_PATH": str(database.resolve())},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
        await client.initialize()
        names = [t.name for t in (await client.list_tools()).tools]
        assert "get_usage_stats" in names

        async def call(name, args=None):
            result = await client.call_tool(name, args)
            assert not result.isError, result
            return json.loads(result.content[0].text)

        before = await call("get_usage_stats")
        count = 300 if batch == 1 else 600
        response = await call(
            "prepare_context",
            {
                "history": "\n".join(f"project_{i} = status_{i}" for i in range(count)),
                "task": f"What is project_{count - 1}?",
                "budget": 128,
            },
        )
        after = await call("get_usage_stats")
        unchanged = await call("get_usage_stats")
        assert after == unchanged
        delta = response["context_reduction"]["reduced_tokens"]
        assert response["context_reduction"]["recorded"]
        assert after["preparations"] == before["preparations"] + 1
        before_total = before["by_counter"][0]["reduced_tokens"] if before["by_counter"] else 0
        assert after["by_counter"][0]["reduced_tokens"] == before_total + delta
        assert after["last_preparation"]["reduced_tokens"] == delta
        receipt = {
            "batch": batch,
            "installed_configuration": str(config_path),
            "test_database": str(database.resolve()),
            "tools": names,
            "per_call": response["context_reduction"],
            "after": after,
        }
        (output / f"installed_call_{batch}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("batch", type=int, choices=(1, 2))
    args = p.parse_args()
    asyncio.run(run(args.config, args.output, args.batch))
