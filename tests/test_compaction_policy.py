"""Cost-aware compaction policy and the dynamic Messages adapter; offline only."""

import copy
import json
import sqlite3

import pytest

from tomc.anthropic_request import AnthropicAdapter
from tomc.compaction_policy import (
    Prices,
    SessionStats,
    cache_warm,
    decide,
    expected_remaining,
    load_stats,
    observe_usage,
    prices_for,
)

SONNET_1H = Prices(2.0, 0.1, 4.0, "test")
HEADERS = {"x-claude-code-session-id": "session-d"}


def test_catalog_prices_follow_cache_lifetime_and_unknown_models_default():
    long = prices_for("anthropic", "claude-sonnet-5-5", long_ttl=True)
    short = prices_for("anthropic", "claude-sonnet-5-5[1m]")
    assert (long.input, long.cache_read, long.cache_write) == (2.0, 0.1, 4.0)
    assert short.cache_write == 2.5 and short.source.startswith("catalog:")
    unknown = prices_for("anthropic", "not-a-model", long_ttl=True)
    assert (unknown.cache_read, unknown.cache_write) == (0.1, 2.0)
    assert prices_for("openai", None).cache_write == 1.0


def test_short_warm_task_from_the_swe_trace_is_not_worth_compiling():
    # astropy-13398, request 10: the measured rebuild that cost more than it saved.
    decision = decide(
        before=21280,
        after=19377,
        kept=15500,
        previous=20804,
        prices=SONNET_1H,
        warm=True,
        remaining=4.5,
        ratio=1.37,
    )
    assert not decision.apply and decision.reason == "unprofitable"
    assert decision.cost > decision.gain


def test_long_warm_session_pays_only_with_enough_remaining_requests():
    numbers = dict(
        before=150_000,
        after=85_000,
        kept=30_000,
        previous=148_000,
        prices=SONNET_1H,
        warm=True,
        ratio=1.0,
    )
    assert not decide(**numbers, remaining=20).apply
    assert decide(**numbers, remaining=200).apply


def test_cold_cache_and_window_pressure_compile_without_future_requests():
    numbers = dict(
        before=30_000, after=20_000, kept=5_000, previous=29_000, prices=SONNET_1H, remaining=0
    )
    assert not decide(**numbers, warm=True).apply
    cold = decide(**numbers, warm=False)
    assert cold.apply and cold.reason == "cold_cache"
    pressed = decide(**numbers, warm=True, window=32_000, pressure=0.8)
    assert pressed.apply and pressed.reason == "window_pressure"
    assert not decide(**{**numbers, "after": 30_000}, warm=False).apply


def test_remaining_requests_use_history_or_a_conservative_prior():
    assert expected_remaining(10, [3, 50]) == 5.0
    assert expected_remaining(10, [12, 14, 20, 30, 40, 60, 100, 110, 9]) == 25.0


def test_cache_warmth_needs_a_recent_request_that_was_cached():
    stats = SessionStats(last_seen=1000.0, ttl=3600)
    assert cache_warm(stats, 1100.0)
    assert not cache_warm(stats, 1000.0 + 3600)
    stats.observe_usage(20_000, 30_000, 0)
    assert not cache_warm(stats, 1100.0)
    assert not cache_warm(SessionStats(), 0.0)


def test_session_stats_count_repeated_compiled_calls_once_and_round_trip():
    stats = SessionStats()
    assert stats.risk == pytest.approx(0.1)
    stats.remember_compiled(["k1", "k2"])
    stats.observe_calls([("a", "k1"), ("a", "k1"), ("b", "k9")])
    assert stats.refetches == 1 and stats.compiled_calls == 2
    assert SessionStats.from_json(stats.to_json()) == stats
    assert SessionStats.from_json({"unknown": 1}) == SessionStats()


# ---- dynamic Messages adapter -------------------------------------------------


def _loop(groups, *, notes=False, task="Fix the failing capacity test.", ids="t"):
    messages = [{"role": "user", "content": [{"type": "text", "text": task}]}]
    for i in range(groups):
        if notes:
            messages.append({"role": "system", "content": f"Environment update {i}"})
        messages += [
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": f"step {i}", "signature": f"sig-{i}"},
                    {
                        "type": "tool_use",
                        "id": f"{ids}{i}",
                        "name": "Read",
                        "input": {"file_path": f"/f{i}.py"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"{ids}{i}",
                        "content": "\n".join(f"file {i} line {j}: capacity {j}" for j in range(60)),
                        **(
                            {"cache_control": {"type": "ephemeral", "ttl": "1h"}}
                            if i == groups - 1
                            else {}
                        ),
                    }
                ],
            },
        ]
    return {
        "model": "claude-sonnet-5-5",
        "system": [
            {
                "type": "text",
                "text": "Host instructions",
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        "tools": [{"name": "Read", "input_schema": {"type": "object"}}],
        "messages": messages,
    }


OPTIONS = dict(policy="dynamic", recent_messages=4, min_history_tokens=200)


def _system_follows_assistant(messages):
    for i, message in enumerate(messages):
        if message["role"] == "system" and message.get("content") not in ([], ""):
            assert messages[i + 1]["role"] == "assistant"


def test_dynamic_short_warm_loop_never_rewrites(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    for step in range(1, 14):
        payload = _loop(step)
        result = adapter.adapt(payload, HEADERS, now=10.0 * step, **OPTIONS)
        assert not result.transformed and result.payload == payload
    assert result.reason == "compaction_not_profitable"
    assert result.policy["policy"] == "unprofitable" and result.policy["policy_warm"]


def test_dynamic_cold_cache_compiles_then_replays_byte_stable(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    first = adapter.adapt(_loop(2), HEADERS, now=0.0, **OPTIONS)
    assert not first.transformed and first.reason == "no_eligible_segment"
    payload = _loop(12)
    original = copy.deepcopy(payload)
    cold = adapter.adapt(payload, HEADERS, now=4000.0, **OPTIONS)  # after the 1h cache expired
    assert cold.transformed and cold.reason == "segment_compiled_cold_cache"
    out = cold.payload["messages"]
    assert out[:2] == original["messages"][:2]
    assert out[2]["content"][0] == original["messages"][2]["content"][0]
    assert "<tomc_history>" in out[2]["content"][-1]["text"]
    assert out[3:] == original["messages"][cold.prefix_count :]
    _system_follows_assistant(out)
    replay = adapter.adapt(_loop(13), HEADERS, now=4010.0, **OPTIONS)
    assert replay.reason == "replayed_prefix"
    assert replay.payload["messages"][:3] == out[:3]


def test_dynamic_extension_keeps_earlier_memory_and_advances(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    first = adapter.adapt(_loop(12), HEADERS, now=0.0, **OPTIONS)
    assert first.transformed and first.reason == "segment_compiled_cold_cache"
    memory = first.payload["messages"][2]["content"]
    later = adapter.adapt(_loop(20), HEADERS, now=9000.0, **OPTIONS)
    assert later.reason == "segment_compiled_cold_cache"
    assert later.prefix_count > first.prefix_count
    carrier = later.payload["messages"][2]["content"]
    assert carrier[: len(memory)] == memory and len(carrier) == len(memory) + 1
    assert later.payload["messages"][3:] == _loop(20)["messages"][later.prefix_count :]


def test_dynamic_compiles_host_notes_across_turns_and_keeps_new_prompt_raw(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    payload = _loop(10, notes=True)
    payload["messages"] += [
        {"role": "assistant", "content": [{"type": "text", "text": "Done."}]},
        {"role": "user", "content": "Now also update the docs."},
        {"role": "system", "content": "Environment update late"},
    ] + _loop(3, ids="u")["messages"][1:]
    result = adapter.adapt(payload, HEADERS, now=0.0, **OPTIONS)
    assert result.transformed
    out = result.payload["messages"]
    assert "HOST_SYSTEM_NOTE" in out[3]["content"][-1]["text"]  # [u, s, a, carrier, ...]
    assert any(m.get("content") == "Now also update the docs." for m in out)
    _system_follows_assistant(out)


def test_dynamic_new_user_turn_replays_frozen_memory_instead_of_recompiling(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    first = adapter.adapt(_loop(12), HEADERS, now=0.0, **OPTIONS)
    payload = _loop(12)
    payload["messages"] += [
        {"role": "assistant", "content": [{"type": "text", "text": "Done."}]},
        {"role": "user", "content": "Thanks, one more question."},
    ]
    result = adapter.adapt(payload, HEADERS, now=30.0, **OPTIONS)
    assert result.reason == "replayed_prefix"
    assert result.payload["messages"][:3] == first.payload["messages"][:3]


def test_dynamic_counts_repeated_compiled_calls_and_records_usage(tmp_path):
    path = tmp_path / "s.sqlite3"
    adapter = AnthropicAdapter(path)
    first = adapter.adapt(_loop(12), HEADERS, now=0.0, **OPTIONS)
    assert first.transformed
    payload = _loop(12)
    payload["messages"] += [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "again",
                    "name": "Read",
                    "input": {"file_path": "/f3.py", "offset": 10},
                }
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "again", "content": "x"}],
        },
    ]
    adapter.adapt(payload, HEADERS, now=20.0, **OPTIONS)
    observe_usage(
        path, "claude", "session-d", sent_tokens=1000, provider_input=1400, provider_cached=1300
    )
    with sqlite3.connect(path) as db:
        stats = load_stats(db, "claude", "session-d")
    assert stats.refetches == 1 and stats.compactions == 1 and stats.requests == 2
    assert stats.token_ratio == pytest.approx(1.4) and stats.ttl == 3600


def test_dynamic_disabled_session_keeps_signed_replay_else_sends_raw(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "s.sqlite3")
    assert adapter.adapt(_loop(12), HEADERS, now=0.0, **OPTIONS).transformed
    payload = _loop(12)
    payload["messages"] += [
        {"role": "assistant", "content": [{"type": "text", "text": "Ok."}]},
        {"role": "user", "content": "Another task."},
    ]
    # The retained tail still carries thinking signed against the rewrite.
    bound = adapter.adapt(payload, HEADERS, enabled=False, now=10.0, **OPTIONS)
    assert bound.transformed and bound.reason == "disabled_compatible_replay"
    other = {"x-claude-code-session-id": "session-e"}
    fresh = adapter.adapt(_loop(12), other, enabled=False, now=10.0, **OPTIONS)
    assert not fresh.transformed and fresh.reason == "session_disabled"


def test_dynamic_rejects_unknown_policy(tmp_path):
    with pytest.raises(ValueError):
        AnthropicAdapter(tmp_path / "s.sqlite3").adapt(_loop(2), HEADERS, policy="always")


# ---- dynamic Responses (Codex) adapter -----------------------------------------

from tomc.responses_request import ResponsesAdapter, _tool_pairs  # noqa: E402

CODEX = {"thread-id": "thread-d"}


def _codex_loop(groups, *, parallel=False, custom=False):
    items = [
        {
            "type": "message",
            "role": "developer",
            "content": [{"type": "input_text", "text": "Developer rules."}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "<environment_context>cwd=/repo</environment_context>",
                }
            ],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Fix the failing capacity test."}],
        },
    ]
    for i in range(groups):
        calls = ["a", "b"] if parallel else ["a"]
        items.append({"type": "reasoning", "summary": [], "encrypted_content": f"cipher-{i}"})
        items += [
            {
                "type": "function_call",
                "call_id": f"c{i}{c}",
                "name": "shell",
                "arguments": json.dumps({"cmd": f"cat f{i}{c}.py"}),
            }
            for c in calls
        ]
        items += [
            {
                "type": "function_call_output",
                "call_id": f"c{i}{c}",
                "output": "\n".join(f"file {i}{c} line {j}: capacity {j}" for j in range(60)),
            }
            for c in calls
        ]
    if custom:  # Codex 0.164: custom tools whose outputs are lists of text blocks.
        for item in items:
            if item["type"] == "function_call":
                item.update(type="custom_tool_call", input=item.pop("arguments"))
            elif item["type"] == "function_call_output":
                item.update(
                    type="custom_tool_call_output",
                    output=[{"type": "input_text", "text": item["output"]}],
                )
    return {
        "model": "gpt-6.1-sol",
        "store": False,
        "input": items,
        "tools": [{"type": "function", "name": "shell"}],
    }


CODEX_OPTIONS = dict(recent_messages=4, min_history_tokens=200)


def test_codex_short_warm_loop_never_rewrites(tmp_path):
    adapter = ResponsesAdapter(tmp_path / "s.sqlite3")
    adapter.adapt(_codex_loop(1), CODEX, now=0.0, **CODEX_OPTIONS)
    for step in range(2, 12):
        payload = _codex_loop(step)
        result = adapter.adapt(payload, CODEX, now=10.0 * step, **CODEX_OPTIONS)
        assert not result.transformed and result.payload == payload


def test_codex_cold_cache_compiles_whole_groups_then_replays(tmp_path):
    adapter = ResponsesAdapter(tmp_path / "s.sqlite3")
    payload = _codex_loop(12)
    original = copy.deepcopy(payload)
    result = adapter.adapt(payload, CODEX, now=0.0, **CODEX_OPTIONS)
    assert result.transformed and result.reason == "segment_compiled_cold_cache"
    out = result.payload["input"]
    assert out[:5] == original["input"][:5]  # instructions, host context, task, first call
    assert "<tomc_history>" in out[5]["output"]
    assert out[6:] == original["input"][result.prefix_count :]
    assert out[6]["type"] == "reasoning"
    assert _tool_pairs(out)[2] is None
    replay = adapter.adapt(_codex_loop(13), CODEX, now=10.0, **CODEX_OPTIONS)
    assert replay.reason == "replayed_prefix" and replay.payload["input"][:6] == out[:6]


def test_codex_parallel_outputs_are_never_split_from_their_calls(tmp_path):
    adapter = ResponsesAdapter(tmp_path / "s.sqlite3")
    result = adapter.adapt(_codex_loop(10, parallel=True), CODEX, now=0.0, **CODEX_OPTIONS)
    assert result.transformed
    out = result.payload["input"]
    carrier = next(i for i, item in enumerate(out) if "<tomc_history>" in str(item))
    assert out[carrier]["call_id"] == "c0b"
    assert _tool_pairs(out)[2] is None and not _tool_pairs(out)[1]


def test_codex_custom_tool_list_output_is_a_carrier(tmp_path):
    adapter = ResponsesAdapter(tmp_path / "s.sqlite3")
    payload = _codex_loop(12, custom=True)
    result = adapter.adapt(payload, CODEX, now=0.0, **CODEX_OPTIONS)
    assert result.transformed
    carrier = result.payload["input"][5]["output"]
    assert carrier[0] == payload["input"][5]["output"][0]
    assert carrier[-1]["type"] == "input_text" and "<tomc_history>" in carrier[-1]["text"]
    assert _tool_pairs(result.payload["input"])[2] is None


# ---- dynamic Chat Completions adapter (openai route) ---------------------------

from tomc.chat_request import ChatCompletionsAdapter, _groups  # noqa: E402

CHAT = {"x-tomc-session-id": "mini-d"}


def _chat_loop(groups, *, parallel=False):
    messages = [
        {"role": "system", "content": "You can run bash."},
        {"role": "user", "content": "Please solve this issue: fix the capacity test."},
    ]
    for i in range(groups):
        ids = [f"c{i}a", f"c{i}b"] if parallel else [f"c{i}a"]
        messages.append(
            {
                "role": "assistant",
                "content": f"Step {i}.",
                "tool_calls": [
                    {
                        "id": c,
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": json.dumps({"command": f"cat {c}"}),
                        },
                    }
                    for c in ids
                ],
            }
        )
        messages += [
            {
                "role": "tool",
                "tool_call_id": c,
                "content": "\n".join(f"file {c} line {j}: capacity {j}" for j in range(60)),
            }
            for c in ids
        ]
    return {"model": "dots3-note-prev", "messages": messages, "tools": [{"type": "function"}]}


def test_chat_cold_cache_compiles_then_replays_byte_stable(tmp_path):
    adapter = ChatCompletionsAdapter(tmp_path / "s.sqlite3")
    payload = _chat_loop(12)
    result = adapter.adapt(payload, CHAT, now=0.0, **CODEX_OPTIONS)
    assert result.transformed and result.reason == "segment_compiled_cold_cache"
    out = result.payload["messages"]
    assert out[:3] == payload["messages"][:3]
    assert "<tomc_history>" in out[3]["content"]
    assert out[4:] == payload["messages"][result.prefix_count :]
    assert _groups(out)[1] is None
    replay = adapter.adapt(_chat_loop(13), CHAT, now=10.0, **CODEX_OPTIONS)
    assert replay.reason == "replayed_prefix" and replay.payload["messages"][:4] == out[:4]


def test_chat_parallel_results_stay_with_their_call(tmp_path):
    adapter = ChatCompletionsAdapter(tmp_path / "s.sqlite3")
    result = adapter.adapt(_chat_loop(10, parallel=True), CHAT, now=0.0, **CODEX_OPTIONS)
    assert result.transformed
    out = result.payload["messages"]
    carrier = next(i for i, m in enumerate(out) if "<tomc_history>" in str(m.get("content")))
    assert out[carrier]["tool_call_id"] == "c0b" and _groups(out)[1] is None


def test_chat_accepts_empty_sdk_response_fields(tmp_path):
    payload = _chat_loop(12)
    for m in payload["messages"]:
        if m["role"] == "assistant":
            m.update(refusal=None, annotations=None, audio=None, function_call=None)
    adapter = ChatCompletionsAdapter(tmp_path / "s.sqlite3")
    assert adapter.adapt(payload, CHAT, now=0.0, **CODEX_OPTIONS).transformed
    payload["messages"][2]["function_call"] = {"name": "bash", "arguments": "{}"}
    assert _groups(payload["messages"])[1] == "unsupported_message_fields"


def test_chat_without_session_header_or_when_disabled_is_untouched(tmp_path):
    adapter = ChatCompletionsAdapter(tmp_path / "s.sqlite3")
    payload = _chat_loop(12)
    assert adapter.adapt(payload, {}, now=0.0).reason == "identity_unavailable"
    off = adapter.adapt(payload, CHAT, enabled=False, now=0.0, **CODEX_OPTIONS)
    assert not off.transformed and off.payload == payload


def test_token_objective_compiles_where_the_cost_objective_declines():
    from tomc.compaction_policy import objective_prices

    numbers = dict(
        before=21280, after=19377, kept=15500, previous=20804, warm=True, remaining=4.5, ratio=1.37
    )
    assert not decide(prices=objective_prices(SONNET_1H, "cost"), **numbers).apply
    tokens = decide(prices=objective_prices(SONNET_1H, "tokens"), **numbers)
    assert tokens.apply and tokens.reason == "profitable"
    with pytest.raises(ValueError):
        objective_prices(SONNET_1H, "speed")


def test_codex_token_objective_compiles_a_warm_segment(tmp_path):
    adapter = ResponsesAdapter(tmp_path / "s.sqlite3")
    adapter.adapt(_codex_loop(1), CODEX, now=0.0, objective="tokens", **CODEX_OPTIONS)
    warm = adapter.adapt(_codex_loop(12), CODEX, now=10.0, objective="tokens", **CODEX_OPTIONS)
    assert warm.transformed and warm.reason == "segment_compiled_profitable"
    assert warm.policy["policy_warm"]
