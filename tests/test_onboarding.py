"""First run: the try-it card, assistant-facing wording, setup --write, doctor and hints."""

import asyncio
import json
import os
import re
import stat
import subprocess
import sys
from importlib.resources import files

import pytest

from tomc import prepare_context
from tomc.cli import main
from tomc.doctor import check, passed, render
from tomc.mcp_server import INSTRUCTIONS, TOOL_NAMES
from tomc.setup import config_path, next_step, write_config
from tomc.tokenization import get_counter
from tomc.tryout import load_sample, run_sample

CJK = re.compile(r"[㐀-鿿]")


# The bundled sample ---------------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "zh"])
def test_sample_is_packaged_long_and_has_the_planted_decisions(language):
    assert files("tomc").joinpath(f"data/try_sample_{language}.json").is_file()
    sample = load_sample(language)
    lines = sample["lines"]
    text = "\n".join(lines)
    assert 5_500 <= get_counter("regex").count(text) <= 7_500
    assert sum(line.startswith("framework = ") for line in lines) == 4
    assert "backup_framework copies framework" in lines and "db = postgres" in lines
    days = {int(d) for d in re.findall(r"(?:Day|第) (\d+)", text)}
    assert days == set(range(1, 121))


@pytest.mark.parametrize("language", ["en", "zh"])
def test_card_numbers_are_computed_not_written_down(language):
    result = run_sample(language)
    sample = load_sample(language)
    expected = prepare_context("\n".join(sample["lines"]), sample["question"], sample["budget"])
    stats = expected.compilation.stats
    details = result["details"]
    assert (details["input_estimated_tokens"], details["memory_estimated_tokens"]) == (
        stats.input_tokens,
        stats.output_tokens,
    )
    card = result["card"].splitlines()
    assert f"{stats.input_tokens:,}" in card[1] and f"{stats.output_tokens:,}" in card[1]
    assert f"{details['reduction_percent']}%" in card[1]
    assert ("estimates" if language == "en" else "估算") in card[1]
    assert list(result)[0] == "summary" and result["saved"] is False
    found = {item["key"]: item for item in details["found"]}
    assert found["framework"]["value"] == "Litestar"
    assert found["backup_framework"]["value"] == "Django" and found["backup_framework"]["copied"]
    assert found["db"]["value"] == "postgres"
    # Line numbers point at the sample's own lines.
    assert sample["lines"][found["framework"]["lines"][0] - 1] == "framework = Litestar"
    assert len(card) <= 10
    if language == "zh":
        assert card[0].startswith("TOMC Memory 试跑") and "下一步" in result["card"]
    else:
        assert card[0].startswith("TOMC Memory trial") and not CJK.search(result["card"])


def test_cli_try_follows_language_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TOMC_MEMORY_PATH", str(tmp_path / "memory.sqlite3"))
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    assert main(["try"]) == 0
    assert capsys.readouterr().out.startswith("TOMC Memory 试跑")
    assert main(["try", "--language", "en", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["details"]["language"] == "en"
    assert list(tmp_path.iterdir()) == []


# The MCP server -------------------------------------------------------------------------


def _session(database, scenario):
    pytest.importorskip("mcp")
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "tomc", "mcp", "--store", str(database)]
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                initialized = await client.initialize()
                return await scenario(client, initialized)

    return asyncio.run(run())


def _payload(result):
    assert not result.isError, result
    return json.loads(result.content[0].text)


def test_try_tomc_and_quickstart_save_nothing(tmp_path):
    database = tmp_path / "memory.sqlite3"
    from tomc.session_store import SessionStore

    # Even with saving switched on, the trial is never stored.
    SessionStore(database).update_settings(save_mcp_results=True)

    async def scenario(client, _):
        prompts = {prompt.name: prompt for prompt in (await client.list_prompts()).prompts}
        assert "quickstart" in prompts
        message = (await client.get_prompt("quickstart", {"language": "zh"})).messages[0]
        assert "try_tomc" in message.content.text and 'language="zh"' in message.content.text
        english = (await client.get_prompt("quickstart", {})).messages[0].content.text
        assert "try_tomc" in english and not CJK.search(english)
        zh = _payload(await client.call_tool("try_tomc", {"language": "zh"}))
        en = _payload(await client.call_tool("try_tomc", {}))
        contexts = _payload(await client.call_tool("list_contexts", {}))
        notebooks = _payload(await client.call_tool("list_memories", {}))
        stats = _payload(await client.call_tool("get_usage_stats", {}))
        return zh, en, contexts, notebooks, stats

    zh, en, contexts, notebooks, stats = _session(database, scenario)
    assert zh["card"].startswith("TOMC Memory 试跑") and en["card"].startswith("TOMC Memory trial")
    assert list(zh)[:2] == ["summary", "card"]
    assert contexts["contexts"] == [] and notebooks["notebooks"] == []
    assert stats["preparations"] == 0
    assert b"Litestar" not in database.read_bytes()


def test_instructions_and_descriptions_say_when_to_call(tmp_path):
    async def scenario(client, initialized):
        tools = (await client.list_tools()).tools
        return initialized.instructions, tools

    instructions, tools = _session(tmp_path / "memory.sqlite3", scenario)
    assert instructions == INSTRUCTIONS
    first = instructions.split(". ")[0]
    for trigger in ("long text", "remember", "记住", "接着上次", "试一下 TOMC Memory"):
        assert trigger in instructions
    assert first.startswith("Call TOMC Memory when")
    assert "10,000" not in instructions and len(instructions.split()) < 300
    for rule in ("host manages the active conversation", "never guess", "ERASE ALL", "paused"):
        assert rule in instructions
    assert tuple(sorted(tool.name for tool in tools)) == tuple(sorted(TOOL_NAMES))
    for tool in tools:
        assert tool.description.startswith("Call "), tool.name
        assert tool.inputSchema.get("additionalProperties") is False, tool.name


@pytest.mark.parametrize(
    "arguments",
    [
        {"budget": 0},
        {"budget": -5},
        {"budget": "100"},
        {"budget": 1.5},
        {"budget": True},
        {"unknown": 1},
        {"tomc_host": "cursor"},
    ],
)
def test_prepare_context_rejects_bad_budget_and_unknown_arguments(tmp_path, arguments):
    async def scenario(client, _):
        bad = await client.call_tool(
            "prepare_context", {"history": "a = 1", "task": "a?", **arguments}
        )
        stray = await client.call_tool("try_tomc", {"lang": "zh"})
        good = await client.call_tool(
            "prepare_context", {"history": "a = 1", "task": "a?", "budget": 64}
        )
        return bad, stray, good

    bad, stray, good = _session(tmp_path / "memory.sqlite3", scenario)
    assert bad.isError and stray.isError and not good.isError


def test_every_response_starts_with_a_summary_and_details_hold_diagnostics(tmp_path):
    async def scenario(client, _):
        calls = [
            ("prepare_context", {"history": "framework = Flask", "task": "framework?"}),
            ("remember_memory", {"name": "demo", "content": "framework = Flask"}),
            ("recall_memory", {"name": "demo", "task": "framework?"}),
            ("list_memories", {}),
            ("get_status", {}),
            ("get_usage_stats", {}),
            ("list_contexts", {}),
            ("forget_memory", {"name": "demo"}),
            ("erase_all_memory", {}),
            ("try_tomc", {}),
        ]
        results = {name: _payload(await client.call_tool(name, args)) for name, args in calls}
        results["get_status_zh"] = _payload(
            await client.call_tool("get_status", {"language": "zh"})
        )
        return results

    results = _session(tmp_path / "memory.sqlite3", scenario)
    for name, result in results.items():
        assert list(result)[0] == "summary", name
        assert isinstance(result["summary"], str) and "\n" not in result["summary"], name
    prepared = results["prepare_context"]
    assert {"memory", "context_reduction", "context_record", "details"} <= set(prepared)
    assert "selected_method" in prepared["details"] and "host" not in prepared
    # Short input: say so plainly instead of "saving 0 tokens (0.00%)".
    assert "as is" in prepared["summary"]
    assert not CJK.search(json.dumps(results["get_status"], ensure_ascii=False))
    assert CJK.search(json.dumps(results["get_status_zh"], ensure_ascii=False))


# Setup ----------------------------------------------------------------------------------


def test_write_merges_backs_up_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".cursor" / "mcp.json"
    target.parent.mkdir()
    original = {"mcpServers": {"other": {"command": "other-server"}}, "theme": "dark"}
    target.write_text(json.dumps(original), encoding="utf-8")
    os.chmod(target, 0o640)
    store = tmp_path / "memory.sqlite3"

    first = write_config("cursor", store)
    assert first["changed"] and first["path"] == str(target)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["theme"] == "dark" and data["mcpServers"]["other"] == {"command": "other-server"}
    assert data["mcpServers"]["tomc"]["type"] == "stdio"
    assert data["mcpServers"]["tomc"]["args"][-1] == str(store)
    backups = list(target.parent.glob("mcp.json.tomc-backup-*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == original
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o640
        assert stat.S_IMODE(backups[0].stat().st_mode) == 0o600

    second = write_config("cursor", store)
    assert not second["changed"] and second["backup"] is None
    assert len(list(target.parent.glob("mcp.json.tomc-backup-*"))) == 1
    assert "12 tools" in second["next_step"] and "试一下 TOMC Memory" in second["next_step"]
    assert len(TOOL_NAMES) == 12
    assert not store.exists()


def test_claude_aliases_and_new_files(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))  # Claude Desktop on Windows
    store = tmp_path / "memory.sqlite3"
    assert main(["setup", "--client", "claude-code", "--write", "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert "Added TOMC Memory" in out and "/mcp" in out
    server = json.loads((tmp_path / ".claude.json").read_text())["mcpServers"]["tomc"]
    assert server["type"] == "stdio" and server["args"][:3] == ["-m", "tomc", "mcp"]
    if os.name == "posix":
        assert stat.S_IMODE((tmp_path / ".claude.json").stat().st_mode) == 0o600
    assert config_path("claude-desktop") == config_path("claude")
    assert config_path("claude").name == "claude_desktop_config.json"
    assert main(["setup", "--client", "claude-desktop", "--write", "--store", str(store)]) == 0
    assert "restart Claude Desktop" in capsys.readouterr().out
    assert "tomc" in json.loads(config_path("claude").read_text())["mcpServers"]
    assert main(["setup", "--client", "claude-code", "--store", str(store)]) == 0
    assert capsys.readouterr().out.startswith("claude mcp add --scope user tomc -- ")


def test_codex_toml_keeps_other_settings(tmp_path, monkeypatch):
    pytest.importorskip("tomlkit")
    monkeypatch.setenv("HOME", str(tmp_path))
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir()
    config.write_text('model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n', encoding="utf-8")
    assert write_config("codex", tmp_path / "m.sqlite3")["changed"]
    text = config.read_text(encoding="utf-8")
    assert text.startswith('model = "gpt-5"') and "[mcp_servers.other]" in text
    assert "[mcp_servers.tomc]" in text
    assert not write_config("codex", tmp_path / "m.sqlite3")["changed"]


def test_write_refuses_broken_files_and_clients_without_a_fixed_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    broken = tmp_path / ".cursor" / "mcp.json"
    broken.parent.mkdir()
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        write_config("cursor")
    assert broken.read_text(encoding="utf-8") == "{not json"
    with pytest.raises(SystemExit) as error:
        main(["setup", "--client", "trae", "--write"])
    assert error.value.code == 2
    project = tmp_path / "project" / ".trae" / "mcp.json"
    assert main(["setup", "--client", "trae", "--write", "--config", str(project)]) == 0
    assert "tomc" in json.loads(project.read_text())["mcpServers"]
    assert "restart TRAE" in next_step("trae")


# Doctor, terminal hint and old Python ---------------------------------------------------


def test_doctor_starts_the_server_without_touching_the_real_database(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    monkeypatch.setenv("HOME", str(tmp_path))
    store = tmp_path / "data" / "memory.sqlite3"
    results = check(store, home=tmp_path)
    text = render(results)
    assert passed(results), text
    assert "✓ MCP server started" in text and f"{len(TOOL_NAMES)} tools" in text
    assert "✓ prepare_context works" in text
    assert "No assistant is set up yet" in text
    assert not store.exists() and not (tmp_path / ".tomc").exists()


def test_doctor_reports_missing_extra_and_unwritable_database(tmp_path, monkeypatch, capsys):
    import tomc.doctor as doctor

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(doctor, "find_spec", lambda name: None)
    monkeypatch.setattr(doctor, "_writable", lambda path: False)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    assert main(["doctor", "--store", str(tmp_path / "m.sqlite3")]) == 1
    out = capsys.readouterr().out
    assert "✗ MCP support is not installed" in out and "tomc-memory[mcp]" in out
    assert "✗ Cannot write the memory database" in out
    assert "uv not found" in out and "pypi.tuna.tsinghua.edu.cn" in out
    assert "required checks failed" in out


@pytest.mark.skipif(os.name != "posix", reason="uses a pseudo-terminal")
def test_mcp_in_a_terminal_prints_a_hint_instead_of_waiting(tmp_path):
    import pty

    main_fd, terminal = pty.openpty()
    try:
        process = subprocess.run(
            [sys.executable, "-m", "tomc", "mcp", "--store", str(tmp_path / "m.sqlite3")],
            stdin=terminal,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        os.close(main_fd)
        os.close(terminal)
    assert process.returncode == 0 and process.stdout == ""
    assert "tomc setup" in process.stderr and "MCP server for an assistant" in process.stderr
    assert len(process.stderr.strip().splitlines()) == 1


def test_old_python_gets_a_clear_message(monkeypatch, capsys):
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    with pytest.raises(SystemExit) as error:
        main(["setup", "--client", "cursor"])
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert "needs Python 3.10 or newer" in message and "3.9.6" in message


def test_the_card_keeps_a_doubtful_value_with_the_line_that_may_have_changed_it():
    from tomc.tryout import run_sample

    for language in ("en", "zh"):
        result = run_sample(language)
        found = {item["key"]: item for item in result["details"]["found"]}
        assert found["framework"]["may_have_changed_at_line"] is None
        assert found["db"]["may_have_changed_at_line"] is None
        backup = found["backup_framework"]
        assert backup["value"] == "Django" and backup["may_have_changed_at_line"]
        assert f"{backup['may_have_changed_at_line']:,}" in result["card"]
