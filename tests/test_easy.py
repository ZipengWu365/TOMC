"""First-use imports, real handoff behavior and persistent notebook boundaries."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from tomc import prepare_context
from tomc.input import parse_history
from tomc.store import MemoryStore


def test_text_jsonl_and_content_blocks_preserve_roles_and_text():
    text = '\ufeff{"role":"user","content":[{"type":"text","text":"你好"}]}\n{"role":"assistant","content":"hello"}'
    parsed = parse_history(text)
    assert [(m.role, m.content) for m in parsed] == [("user", "你好"), ("assistant", "hello")]
    assert parse_history("[STATE] drink = tea") == "[STATE] drink = tea"
    with pytest.raises(ValueError, match="Only text blocks"):
        parse_history([{"content": [{"type": "image", "source": "private"}]}])
    with pytest.raises(ValueError):
        parse_history('{"messages": invalid}')


def test_easy_keeps_fitting_prose_and_returns_ready_messages():
    text = "There are 28 attendees. Venue B has a lift. Booking is still pending."
    result = prepare_context(text, "Which venue fits?")
    assert result.compilation.compiled_memory == text
    assert result.compilation.diagnostics["selected_strategy"] == "raw"
    assert "Which venue fits?" in result.prompt and text in result.prompt
    assert result.messages[0]["role"] == "system"
    assert "untrusted" in result.messages[0]["content"]


def test_easy_long_trace_retains_sources_without_legacy_agent_instructions():
    from importlib.resources import files

    data = json.loads(files("tomc").joinpath("data/agent.json").read_text())
    result = prepare_context(data, data["query"], 512)
    assert result.compilation.diagnostics["selected_strategy"] == "rag"
    assert result.compilation.raw_fallback
    assert "[VERIFIER]" not in result.prompt and "[NEXT_ACTION]" not in result.prompt
    assert 0 < result.compilation.stats.output_tokens <= 512
    empty = prepare_context("a very long indivisible line " * 20, "quote it", 1)
    assert not empty.prompt and "Increase" in empty.note


def test_default_budget_keeps_most_of_a_long_history_and_short_ones_intact():
    from tomc.easy import MIN_DEFAULT_BUDGET, default_budget
    from tomc.ledger import normalize
    from tomc.tokenization import get_counter

    lines = "\n".join(f"Note {i}: the team reviewed item {i} and left it open." for i in range(400))
    tokens = get_counter("regex").count(normalize(parse_history(lines))[0])
    result = prepare_context(lines, "Which items were reviewed?")
    assert tokens > MIN_DEFAULT_BUDGET
    assert result.compilation.stats.token_budget == default_budget(tokens)
    assert default_budget(tokens) == max(MIN_DEFAULT_BUDGET, -(-tokens * 8 // 10))
    assert result.compilation.stats.output_tokens <= result.compilation.stats.token_budget
    short = prepare_context("drink = tea", "current drink")
    assert short.compilation.stats.token_budget == MIN_DEFAULT_BUDGET
    assert short.compilation.diagnostics["selected_strategy"] == "raw"
    explicit = prepare_context(lines, "Which items were reviewed?", 256)
    assert explicit.compilation.stats.token_budget == 256


@pytest.mark.parametrize(
    "history,task,budget",
    [
        ("", "next", 100),
        ("hello", "", 100),
        ("hello", "next", True),
        ("hello", "next", 0),
        ([{"content": ""}], "next", 100),
    ],
)
def test_easy_rejects_unusable_inputs(history, task, budget):
    with pytest.raises(ValueError):
        prepare_context(history, task, budget)


def test_notebooks_survive_restart_isolate_names_and_delete_exactly(tmp_path):
    path = tmp_path / "memory.sqlite3"
    store = MemoryStore(path)
    store.remember("work", "drink = tea")
    assert not store.remember("work", "drink = tea")["saved"]
    store.remember("work", "backup_drink copies drink\ndrink = water")
    store.remember("other", "private other notebook")
    restarted = MemoryStore(path)
    result = restarted.recall("work", "current drink")
    assert "drink = water" in result.prompt and "private other" not in result.prompt
    assert len(restarted.list()) == 2
    assert restarted.forget("work")["deleted_entries"] == 2
    assert restarted.list()[0]["name"] == "other"
    with pytest.raises(ValueError, match="not found"):
        restarted.recall("work", "continue")


def test_store_rolls_back_overflow_and_serializes_concurrent_appends(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("full", "a" * 150_000)
    with pytest.raises(ValueError, match="full"):
        store.remember("full", "b" * 100_000)
    assert store.list()[0]["entries"] == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: store.remember("parallel", f"note {i}"), range(10)))
    assert next(n for n in store.list() if n["name"] == "parallel")["entries"] == 10


def test_prepare_cli_stdin_and_absolute_client_configuration():
    run = subprocess.run(
        [sys.executable, "-m", "tomc", "prepare", "-", "--task", "continue", "--messages"],
        input="Task progress: tests pending",
        capture_output=True,
        text=True,
        check=True,
    )
    assert "tests pending" in json.loads(run.stdout)[1]["content"]
    run = subprocess.run(
        [sys.executable, "-m", "tomc", "setup", "--client", "cursor"],
        capture_output=True,
        text=True,
        check=True,
    )
    config = json.loads(run.stdout)["mcpServers"]["tomc"]
    assert config["command"] == sys.executable
    assert config["args"][:3] == ["-m", "tomc", "mcp"]


def test_easy_demo_upload_and_handoff():
    pytest.importorskip("gradio")
    from demo.easy import prepare_view, upload_text

    assert upload_text("你好".encode("utf-8")) == "你好"
    result = prepare_view("Venue B is not booked.", "What remains?", "Balanced / 默认")
    assert "not booked" in result[0] and "What remains?" in result[0]
    assert result[3]["compiled_memory"] == "Venue B is not booked."


def test_ui_empty_long_paragraph_gives_recovery_and_never_ready_status():
    pytest.importorskip("gradio")
    from demo.easy import prepare_view

    paragraph = "会议记录：" + "入口在东侧；" * 1300 + "最终安排在B厅。"
    result = prepare_view(paragraph, "最终安排在哪个厅？", "More detail / 更多细节")
    assert result[0] == ""
    assert "Ready to copy" not in result[1]
    assert "More detail is already selected" in result[1]
    assert "add line breaks between sentences" in result[1]


def test_ui_validation_gives_an_actionable_missing_task_example():
    gradio = pytest.importorskip("gradio")
    from demo.easy import prepare_view

    with pytest.raises(gradio.Error, match="Add your next task, for example: Which venue fits"):
        prepare_view("B会议室尚未预订。", "", "Balanced / 默认")
