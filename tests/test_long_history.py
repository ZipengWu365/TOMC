"""Long histories are compiled, not refused: no 200,000-character input guard.

The default keeps 80% of a short history and progressively less of a longer one,
down to 60% at a million estimated tokens. Only synthetic text is used.
"""

import pytest

from tomc.easy import MIN_DEFAULT_BUDGET, default_budget, prepare_context

FACT = "The release codename is AMBER-HERON-42."
TASK = "What is the release codename?"


def long_messages(turns=700):
    messages = []
    for i in range(turns):
        text = f"Batch {i}: module_{i % 97} uses port {4000 + i % 900}; " + " ".join(
            f"item{j}-{(i * j) % 1009}" for j in range(40)
        )
        messages.append({"role": "user", "content": text + (f" {FACT}" if i == 3 else "")})
        messages.append(
            {"role": "assistant", "content": f"Recorded batch {i} for module_{i % 97}."}
        )
    return messages


def test_history_over_200k_characters_is_compiled():
    history = long_messages()
    assert sum(len(message["content"]) for message in history) > 250_000
    result = prepare_context(history, TASK)
    assert "AMBER-HERON-42" in result.compilation.compiled_memory
    assert 0 < result.compilation.stats.output_tokens <= result.compilation.stats.token_budget


@pytest.mark.parametrize(
    "tokens,budget",
    [
        (500, MIN_DEFAULT_BUDGET),
        (5_000, 4_000),
        (10_000, 8_000),
        (100_000, 70_000),
        (1_000_000, 600_000),
        (3_000_000, 1_800_000),
    ],
)
def test_default_keeps_80_percent_of_short_and_60_percent_of_long_histories(tokens, budget):
    assert default_budget(tokens) == budget


def test_default_budget_never_shrinks_as_history_grows_and_ratio_stays_in_range():
    # Every adjacent size around both bends, plus a coarse sweep across the whole range.
    sizes = sorted(
        {
            *range(9_990, 10_020),
            *range(99_990, 100_020),
            *range(999_990, 1_000_020),
            *(10_000 + 997 * step for step in range(1_000)),
        }
    )
    budgets = [default_budget(size) for size in sizes]
    assert all(later >= earlier for earlier, later in zip(budgets, budgets[1:]))
    assert all(0.6 <= budget / size <= 0.8 + 1 / size for size, budget in zip(sizes, budgets))


def test_claude_adapter_compiles_long_old_history_instead_of_passing_it_through():
    from tomc.anthropic_request import adapt_request

    payload = {
        "model": "fixture",
        "max_tokens": 100,
        "messages": [*long_messages(), {"role": "user", "content": TASK}],
    }
    result = adapt_request(payload, recent_messages=1, min_history_tokens=20)
    assert result.transformed, result.reason
    assert "AMBER-HERON-42" in result.payload["messages"][0]["content"]
    assert result.payload["messages"][-1] == payload["messages"][-1]
    assert result.after_tokens < result.before_tokens


def test_codex_adapter_compiles_every_supported_old_turn_beyond_200k_characters():
    from tomc.responses_request import adapt_request

    items = [
        {
            "type": "message",
            "role": m["role"],
            "content": [
                {
                    "type": "input_text" if m["role"] == "user" else "output_text",
                    "text": m["content"],
                }
            ],
        }
        for m in long_messages()
    ]
    task = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": TASK}]}
    payload = {
        "model": "fixture",
        "input": [*items, task],
        "client_metadata": {"thread_id": "fixture"},
    }
    result = adapt_request(payload, recent_messages=1, min_history_tokens=20)
    assert result.transformed, result.reason
    # Only the compiled evidence and the untouched current turn remain.
    assert len(result.payload["input"]) == 2 and result.payload["input"][-1] == task
    assert "AMBER-HERON-42" in result.payload["input"][0]["content"][0]["text"]


def test_notebook_keeps_growing_past_200k_characters(tmp_path):
    from tomc.store import MemoryStore

    store = MemoryStore(tmp_path / "notebooks.sqlite3")
    history = long_messages()
    for start in range(0, len(history), 280):
        chunk = "\n".join(f"{m['role']}: {m['content']}" for m in history[start : start + 280])
        assert store.remember("long-project", chunk)["saved"]
    prepared = store.recall("long-project", TASK)
    assert "AMBER-HERON-42" in prepared.compilation.compiled_memory
