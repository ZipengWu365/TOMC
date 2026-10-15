"""Behavioral contracts: executable semantics, provenance, budgets and offline operation."""

import json
import random
import socket

import pytest

from tomc import STRATEGIES, Message, compile_memory
from tomc._vendor import reference
from tomc.tokenization import RegexCounter


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not call network services")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def state(text, budget=4096):
    return compile_memory(text, "current state", budget, "tomc")


def test_snapshot_copy_keeps_historical_dependency():
    result = state("A = 3\nB copies A\nA = 8\nC copies B")
    values = {r.key: r for r in result.ledger}
    assert {k: r.value for k, r in values.items()} == {"A": "8", "B": "3", "C": "3"}
    assert values["C"].sources == ("u0", "u1", "u3")
    assert values["A"].sources == ("u2",)
    assert all(r.included for r in result.ledger)


def test_default_api_executes_paper_state_updates_and_retains_source_text():
    result = compile_memory("drink = tea\nbackup copies drink\ndrink = water", "current drink")
    assert {r.key: r.value for r in result.ledger} == {"drink": "water", "backup": "tea"}
    assert result.diagnostics["kernel"] == "paper-reference"
    assert "drink = tea" in result.raw_fallback and "drink = water" in result.raw_fallback
    assert "[VERIFIER]" not in result.compiled_memory
    assert "[NEXT_ACTION]" not in result.compiled_memory


def test_dependency_outside_query_retrieval_is_still_executed():
    text = (
        "origin = 7\n"
        + "\n".join(f"unrelated_{i} = {i}" for i in range(300))
        + "\nresult copies origin"
    )
    result = state(text)
    # Kernel cap is 96 alphabetically sorted state rows; result is within this cap.
    assert next(r.value for r in result.ledger if r.key == "result") == "7"


def test_missing_copy_is_explicit_unknown():
    assert state("B copies absent").ledger[0].value == "<UNKNOWN>"


def test_plain_prose_does_not_invent_state():
    result = state("I might prefer tea someday, but I have not decided.")
    assert result.ledger == []
    assert "not decided" in result.raw_fallback


def test_typed_path_requires_matching_labels_and_preserves_witnesses():
    text = "alex -[assigned]-> team\nteam -[owns]-> archive\nteam -[likes]-> garden"
    result = compile_memory(text, "relation: assigned > owns", 120, "tomc")
    assert [(r.key, r.value, r.sources) for r in result.ledger] == [
        ("alex", "assigned > owns => archive", ("u0", "u1"))
    ]


def test_count_scope_and_occurrence_support_are_distinct():
    result = compile_memory("apple apple\napple pear", "count apple", 120, "tomc")
    assert next(r.value for r in result.ledger if r.key == "apple") == "occ=3, support=2"
    assert result.diagnostics["count_scope"] == "all_content_lines"


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("budget", [0, 1, 8, 31, 64, 250])
def test_budget_contract(strategy, budget):
    text = "\n".join(
        [
            "current = 已更新",
            "A = 9",
            "B copies A",
            "x -[path]-> y",
            "FAILED test; pytest src/check.py",
            "Long " + "word" * 200,
        ]
    )
    result = compile_memory(text, "current state", budget, strategy)
    assert result.stats.output_tokens == RegexCounter().count(result.compiled_memory)
    assert result.stats.budget_compliant == (result.stats.output_tokens <= budget)
    if strategy != "raw":
        assert result.stats.output_tokens <= budget
    else:
        assert result.compiled_memory == text
    source_ids = {u.source_id for u in result.evidence}
    assert all(set(r.sources) <= source_ids for r in result.ledger if r.included)


def test_message_role_and_exact_line_provenance():
    result = compile_memory(
        [Message("  drink = tea  ", "user"), {"role": "tool", "content": "note"}],
        "current drink",
        100,
        "tomc",
    )
    assert result.evidence[0].text == "  drink = tea  "
    assert (
        result.evidence[0].message_index,
        result.evidence[0].line_number,
        result.evidence[0].role,
    ) == (0, 1, "user")
    assert result.ledger[0].value == "tea"


def test_tool_call_serialization_and_validation():
    result = compile_memory(
        [{"role": "assistant", "content": None, "tool_calls": [{"name": "inspect"}]}],
        "inspect",
        120,
        "raw",
    )
    assert "TOOL_CALLS=" in result.compiled_memory
    with pytest.raises(TypeError):
        compile_memory([{"content": [{"type": "image"}]}], "describe")


def test_deterministic_except_latency():
    a = state("A = 1\nA = 2").to_dict()
    b = state("A = 1\nA = 2").to_dict()
    a["stats"].pop("latency_ms")
    b["stats"].pop("latency_ms")
    assert a == b


def test_hybrid_keeps_exact_explanation():
    text = 'venue = library\nMira said: "The garden becomes slippery after rain."'
    result = compile_memory(text, "Why? Quote Mira's exact explanation.", 100, "hybrid")
    assert result.diagnostics["selected_strategy"] == "tomc_raw"
    assert '"The garden becomes slippery after rain."' in result.compiled_memory


def test_hybrid_coding_cues_do_not_override_paper_state_task():
    history = "status = pending\nTask: fix src/a.py\npytest tests/a.py FAILED\nstatus = complete"
    result = compile_memory(history, "current status", 200, "hybrid")
    assert next(r.value for r in result.ledger if r.key == "status") == "complete"
    assert "[VERIFIER]" not in result.compiled_memory
    assert result.diagnostics["kernel"] == "paper-reference"


def test_tomc2_extracts_original_attempt_and_test_sections():
    text = "Task: fix src/a.py\nAttempted guard; did not work.\npytest tests/a.py FAILED\nPatched src/a.py; fixed.\npytest tests/a.py passed"
    result = compile_memory(text, "Continue the repair", 800, "tomc2")
    assert any(r.kind == "ATTEMPT" and "outcome=failed" in r.value for r in result.ledger)
    assert any(r.kind == "TEST_ERROR" and "passed" in r.value for r in result.ledger)
    assert any(r.kind == "VERIFIER" for r in result.ledger)
    assert "heuristic" in " ".join(result.warnings)
    assert all(r.basis != "verified" for r in result.ledger)


def test_differential_state_kernel_on_random_programs():
    rng = random.Random(42)
    for _ in range(30):
        lines = [
            f"{rng.choice('ABCD')} = {rng.randrange(10)}"
            if rng.random() < 0.7
            else f"{rng.choice('ABCD')} copies {rng.choice('ABCD')}"
            for _ in range(25)
        ]
        text = "\n".join(lines)
        cfg = reference.TOMCConfig()
        expected = reference.compile_state(
            reference.parse_default(reference.segment_lines(text)), cfg
        )
        assert {r.key: r.value for r in state(text).ledger} == {r.key: r.value for r in expected}


@pytest.mark.parametrize("budget", [-1, True, 1.5])
def test_invalid_budget(budget):
    with pytest.raises(ValueError):
        state("A = 1", budget)


def test_invalid_price_and_unknown_strategy():
    with pytest.raises(ValueError):
        compile_memory("x", "q", input_price_per_million=float("nan"))
    with pytest.raises(ValueError):
        compile_memory("x", "q", strategy="fake")


def test_cost_and_reader_export_do_not_include_audit_ledger():
    result = state("A = 1\nB = 2", 13)
    assert any(not r.included for r in result.ledger)
    messages = result.reader_messages("current A")
    assert len(messages) == 2 and messages[1]["role"] == "user"
    assert result.compiled_memory in messages[1]["content"]
    assert result.stats.estimated_input_cost_after is None
    priced = compile_memory("word " * 100, "q", 10, "head", input_price_per_million=2)
    assert priced.stats.estimated_input_cost_after == 0.00002
    json.dumps(priced.to_dict())


def test_cjk_and_punctuation_are_not_free():
    c = RegexCounter()
    assert c.count("你好，世界！") == 6
    assert c.count(c.truncate("你好，世界！", 3)) == 3
    assert c.truncate("a   b c", 2, tail=True) == "b c"
