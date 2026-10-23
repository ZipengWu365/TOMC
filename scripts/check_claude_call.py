"""Ask the installed Claude Code model to call TOMC, using isolated test statistics."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tomc.usage import UsageStore  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--batch", type=int, default=1)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    registered = json.loads((Path.home() / ".claude.json").read_text("utf-8"))
    server = registered["mcpServers"]["tomc-memory"]
    database = output / "widget_test.sqlite3"
    config = {"mcpServers": {"tomc-memory": {
        **server, "env": {**server.get("env", {}), "TOMC_MEMORY_PATH": str(database)},
    }}}
    config_path = output / "claude-test-mcp.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    executables = sorted((Path.home() / ".vscode/extensions").glob(
        "anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe"),
        key=lambda p: p.stat().st_mtime)
    executable = executables[-1]
    count = 120 if args.batch == 1 else 180
    history = "\n".join(f"project_{i} = status_{i}" for i in range(count))
    prompt = (
        "Run a TOMC integration test using only the supplied external history below. "
        "Call mcp__tomc-memory__prepare_context exactly once, with the COMPLETE history "
        f"as supplied, task='What is project_{count-1}?', budget=128. "
        "Then call mcp__tomc-memory__get_usage_stats once, and report the answer and "
        "context reduction percentage. Do not save a notebook. Do not compress this chat "
        "or claim quota savings. Do not use any other tools.\n<external_history>\n"
        + history + "\n</external_history>"
    )
    before = UsageStore(database).summary()
    result = subprocess.run([
        str(executable), "-p", "--output-format", "stream-json", "--verbose",
        "--no-session-persistence", "--no-chrome", "--disable-slash-commands",
        "--strict-mcp-config", "--mcp-config", str(config_path),
        "--tools", "", "--allowedTools",
        "mcp__tomc-memory__prepare_context,mcp__tomc-memory__get_usage_stats",
        "--permission-mode", "dontAsk", "--setting-sources", "user",
        "--effort", "low", "--max-budget-usd", "1",
    ], input=prompt, text=True, encoding="utf-8", capture_output=True,
        cwd=output, timeout=180, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    tool_calls = []
    for event in events:
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_calls.append(block["name"])
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    after = UsageStore(database).summary()
    receipt = {
        "host": "Claude Code", "executable": str(executable),
        "registered_runtime": server["args"], "isolated_database": str(database),
        "tool_calls": tool_calls, "exit_code": result.returncode,
        "model_result": final.get("result"), "model_error": final.get("is_error"),
        "before_preparations": before["preparations"], "after": after,
        "production_database_written": False, "desktop_control_used": False,
    }
    receipt["passed"] = (result.returncode == 0 and not final.get("is_error", True)
        and tool_calls.count("mcp__tomc-memory__prepare_context") == 1
        and "mcp__tomc-memory__get_usage_stats" in tool_calls
        and after["preparations"] == before["preparations"] + 1)
    (output / f"claude-call-{args.batch}.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if not receipt["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
