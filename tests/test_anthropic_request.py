"""Offline Messages-adapter invariants; no credentials or model calls."""

import copy
import json

import pytest

from tomc.anthropic_request import AnthropicAdapter, adapt_request, extract_session_id
from tomc.tokenization import get_counter


def _request():
    messages = []
    for i in range(8):
        messages.extend(
            [
                {
                    "role": "user",
                    "content": "\n".join(
                        f"Project decision {i}-{j}: capacity is {40 + j}; keep the blue design."
                        for j in range(35)
                    ),
                },
                {"role": "assistant", "content": f"Recorded decision {i}."},
            ]
        )
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What is the latest capacity?",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    )
    return {
        "model": "unchanged-model",
        "max_tokens": 200,
        "system": [
            {
                "type": "text",
                "text": "Original attribution and instruction",
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        "tools": [{"name": "lookup", "input_schema": {"type": "object"}}],
        "metadata": {"user_id": json.dumps({"session_id": "session-a"})},
        "stream": True,
        "unknown_top_level": {"keep": "exactly"},
        "messages": messages,
    }


def _count(payload):
    return get_counter("regex").count(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def test_real_compiler_replaces_old_prefix_and_preserves_host_request():
    payload = _request()
    original = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=500, min_history_tokens=20)
    assert result.transformed
    assert result.prepared.compilation.stats.output_tokens <= 500
    assert result.task == "What is the latest capacity?"
    assert payload == original
    assert result.payload["messages"][-6:] == original["messages"][-6:]
    assert result.payload["messages"][0]["role"] == "user"
    assert "untrusted data" in result.payload["messages"][0]["content"]
    for field in original.keys() - {"messages"}:
        assert result.payload[field] == original[field]
    assert result.before_tokens == _count(original)
    assert result.after_tokens == _count(result.payload) < result.before_tokens
    assert "estimate" in result.counter
    assert "cache_may_change" in result.reason


def _tool_loop():
    return [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tool-1", "name": "lookup", "input": {"path": "a"}}
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tool-1", "content": "capacity 19"}],
        },
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tool-2", "name": "lookup", "input": {"path": "b"}}
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool-2",
                    "content": "capacity 20",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
    ]


def test_latest_task_and_complete_tool_loop_survive_even_beyond_tail_size():
    payload = _request()
    latest = copy.deepcopy(payload["messages"][-1:]) + _tool_loop()
    payload["messages"] += _tool_loop()
    result = adapt_request(payload, memory_budget=500, recent_messages=2, min_history_tokens=20)
    assert result.transformed
    assert result.payload["messages"][-len(latest) :] == latest


def test_completed_old_tool_groups_are_exported_as_historical_data():
    payload = _request()
    payload["messages"][2:2] = _tool_loop()
    result = adapt_request(payload, memory_budget=600, min_history_tokens=20)
    assert result.transformed
    assert "tool_use" not in [
        b.get("type")
        for m in result.payload["messages"]
        if isinstance(m["content"], list)
        for b in m["content"]
    ]
    assert payload["messages"][2]["content"][0]["type"] == "tool_use"


def _direct_tool_loop():
    loop = _tool_loop()
    for message in loop:
        for block in message["content"]:
            if block["type"] == "tool_use":
                block["caller"] = {"type": "direct"}
    return loop


def test_direct_caller_current_tool_loop_is_retained_exactly():
    payload = _request()
    payload["messages"] += _direct_tool_loop()
    original = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert result.transformed and result.prepared is not None
    assert result.payload["messages"][-5:] == original["messages"][-5:]
    assert payload == original


def test_direct_caller_completed_old_turn_can_be_compiled():
    payload = _request()
    payload["messages"][2:2] = _direct_tool_loop()
    original = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert result.transformed and result.prepared is not None
    assert result.after_tokens < result.before_tokens
    assert payload == original


@pytest.mark.parametrize(
    "caller",
    [
        None,
        "direct",
        [],
        {},
        {"type": ["direct"]},
        {"type": {"future": True}},
        {"type": "direct", "unknown": True},
        {"type": "code_execution_20260120", "tool_id": "srvtoolu_test"},
        {"type": "code_execution_20250825", "tool_id": "srvtoolu_test"},
    ],
)
def test_unknown_or_programmatic_caller_is_not_compiled(caller):
    payload = _request()
    loop = _direct_tool_loop()
    loop[0]["content"][0]["caller"] = caller
    payload["messages"] += loop
    original = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=500, min_history_tokens=20)
    assert not result.transformed and result.reason == "unsupported_tool_use"
    assert result.payload == original and result.prepared is None


def test_direct_caller_does_not_relax_tool_pairing_or_unknown_fields():
    payload = _request()
    payload["messages"] += _direct_tool_loop()[:2]
    payload["messages"][-1]["content"][0]["tool_use_id"] = "unmatched"
    assert adapt_request(payload).reason == "invalid_tool_pairing"
    payload["messages"][-1]["content"][0]["tool_use_id"] = "tool-1"
    payload["messages"][-2]["content"][0]["toolset_name"] = "unknown"
    assert adapt_request(payload).reason == "unsupported_tool_use"


def test_server_tool_use_remains_a_separate_unsupported_protocol():
    payload = _request()
    payload["messages"] += _direct_tool_loop()[:2]
    payload["messages"][-2]["content"][0]["type"] = "server_tool_use"
    result = adapt_request(payload)
    assert not result.transformed and result.reason == "unsupported_content_type"
    assert result.payload == payload


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda p: p.update(compaction={"type": "summarize"}), "native_context_management"),
        (
            lambda p: p.update(context_management={"edits": [{"type": "compact_20260112"}]}),
            "native_context_management",
        ),
        (
            lambda p: p["messages"][-2].update(
                content=[{"type": "thinking", "thinking": "opaque", "signature": "sig"}]
            ),
            "retained_thinking_requires_original_prefix",
        ),
        (
            lambda p: p["messages"][-2].update(
                content=[{"type": "redacted_thinking", "data": "opaque"}]
            ),
            "retained_thinking_requires_original_prefix",
        ),
        (
            lambda p: p["messages"][1].update(
                content=[{"type": "new_provider_block", "value": "keep"}]
            ),
            "unsupported_content_type",
        ),
        (
            lambda p: p["messages"][1].update(provider_extension={"keep": "me"}),
            "unsupported_message_fields",
        ),
        (
            lambda p: p["messages"][1].update(
                content=[{"type": "text", "text": "cite", "citations": [{"source": 1}]}]
            ),
            "unsupported_text_fields",
        ),
        (lambda p: p["messages"].append(_tool_loop()[0]), "incomplete_tool_pairing"),
        (lambda p: p["messages"].append(_tool_loop()[1]), "invalid_tool_pairing"),
    ],
)
def test_unsupported_requests_are_untouched(mutation, reason):
    payload = _request()
    mutation(payload)
    original = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=400, min_history_tokens=20)
    assert not result.transformed
    assert result.reason == reason
    assert result.payload == original
    assert result.before_tokens == result.after_tokens
    assert result.prepared is None


@pytest.mark.parametrize(
    "headers,expected",
    [
        (
            {"X-Claude-Code-Compaction": "auto", "x-claude-code-request-class": "compaction"},
            (
                "host_compaction_request",
                {"request_class": "compaction", "compaction_trigger": "auto"},
            ),
        ),
        (
            {"x-claude-code-request-class": "compaction"},
            ("host_compaction_request", {"request_class": "compaction"}),
        ),
        (
            {"x-claude-code-request-class": "main", "x-claude-code-context-compacted": "manual"},
            (None, {"request_class": "main", "compaction_trigger": "manual"}),
        ),
        (
            {"x-claude-code-request-class": "subagent", "x-claude-code-agent-id": "agent-fixture"},
            (None, {"request_class": "subagent", "agent": "subagent"}),
        ),
        ({"x-claude-code-compaction": "free text\nwith newline"}, ("host_compaction_request", {})),
    ],
)
def test_documented_hint_headers_classify_host_compaction(headers, expected):
    from tomc.anthropic_request import classify_request

    assert classify_request(_request(), headers) == expected


def test_host_compaction_and_opaque_server_blocks_are_named_and_untouched(tmp_path):
    payload = _request()
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    result = adapter.adapt(payload, {"x-claude-code-compaction": "manual"}, min_history_tokens=20)
    assert result.reason == "host_compaction_request" and result.payload is payload
    payload["messages"][1]["content"] = [{"type": "compaction", "content": "opaque server summary"}]
    assert adapt_request(payload, min_history_tokens=20).reason == "native_compaction_state"


def test_tool_result_order_and_parallel_pairs_are_validated():
    payload = _request()
    payload["messages"] += _tool_loop()[:2]
    payload["messages"][-1]["content"].insert(0, {"type": "text", "text": "bad ordering"})
    assert adapt_request(payload).reason == "invalid_tool_pairing"
    payload = _request()
    use, result = _tool_loop()[:2]
    use["content"].append({"type": "tool_use", "id": "parallel", "name": "lookup", "input": {}})
    result["content"].append(
        {"type": "tool_result", "tool_use_id": "parallel", "content": "parallel result"}
    )
    payload["messages"] += [use, result]
    transformed = adapt_request(payload, memory_budget=500, min_history_tokens=20)
    assert transformed.transformed
    assert transformed.payload["messages"][-2:] == [use, result]


def test_no_reduction_short_input_and_invalid_budget_pass_through():
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    assert adapt_request(payload).reason == "insufficient_old_history"
    assert adapt_request(_request(), memory_budget=False).reason == "invalid_adapter_options"
    assert adapt_request(_request(), recent_messages=0).reason == "invalid_adapter_options"
    assert adapt_request(_request(), min_history_tokens=10**9).reason == "history_below_threshold"
    assert not adapt_request(_request(), memory_budget=1, min_history_tokens=20).transformed


def test_session_identity_only_uses_verified_fields_and_rejects_conflicts():
    assert extract_session_id({}, {"X-Claude-Code-Session-Id": "session-a"}) == "session-a"
    payload = {
        "metadata": {"user_id": json.dumps({"session_id": "session-a", "account_uuid": "not-read"})}
    }
    assert extract_session_id(payload, {}) == "session-a"
    assert extract_session_id(payload, {"x-claude-code-session-id": "session-a"}) == "session-a"
    assert extract_session_id(payload, {"x-claude-code-session-id": "session-b"}) is None
    assert extract_session_id(payload, {"x-claude-code-session-id": "bad\nheader"}) is None
    assert extract_session_id({}, {"x-session-id": "unverified"}) is None
    assert extract_session_id({"session_id": "unverified"}, {}) is None
    assert extract_session_id({"metadata": {"user_id": "user_x_account_y_session_z"}}, {}) is None
    assert (
        extract_session_id({}, {"x-claude-code-session-id": "a", "X-Claude-Code-Session-Id": "b"})
        is None
    )


def test_complete_old_thinking_turns_can_be_removed_without_changing_thinking_config():
    payload = _request()
    payload["thinking"] = {
        "type": "adaptive",
        "block_binding": {"prefix_mismatch_behavior": "error"},
    }
    payload["context_management"] = {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]}
    for message in payload["messages"]:
        if message["role"] == "assistant":
            message["content"] = [
                {"type": "thinking", "thinking": "private reasoning marker", "signature": "opaque"},
                {"type": "text", "text": message["content"]},
            ]
    before = copy.deepcopy(payload)
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert result.transformed
    assert result.payload["messages"][-1] == before["messages"][-1]
    assert result.payload["thinking"] == before["thinking"]
    assert result.payload["context_management"] == before["context_management"]
    assert "private reasoning marker" not in json.dumps(result.payload)
    assert "private reasoning marker" not in result.prepared.prompt
    assert payload == before


def test_current_tool_turn_signed_thinking_stays_untouched():
    payload = _request()
    payload["messages"] += _tool_loop()[:2]
    payload["messages"][-2]["content"].insert(
        0, {"type": "thinking", "thinking": "opaque", "signature": "sig"}
    )
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert not result.transformed
    assert result.payload == payload
    assert result.reason == "retained_thinking_requires_original_prefix"


HEADERS = {"X-Claude-Code-Session-Id": "session-a", "x-claude-code-request-class": "main"}


def _stateful(adapter, payload, **kwargs):
    return adapter.adapt(
        payload, HEADERS, memory_budget=500, recent_messages=1, min_history_tokens=20, **kwargs
    )


def _signed_tool_loop():
    result = _tool_loop()[:2]
    result[0]["content"].insert(
        0, {"type": "thinking", "thinking": "opaque", "signature": "signed against compiled prefix"}
    )
    return result


def test_stateful_replay_survives_restart_and_preserves_signed_tool_turn(tmp_path):
    path = tmp_path / "shared.sqlite3"
    payload = _request()
    first = _stateful(AnthropicAdapter(path), payload)
    assert first.transformed and first.prepared is not None
    payload["messages"] += _signed_tool_loop()
    # A moving explicit cache breakpoint must not prevent equivalent replay.
    payload["messages"][-3]["content"][0].pop("cache_control")
    result = _stateful(AnthropicAdapter(path), payload)
    assert result.transformed and result.reason == "replayed_prefix"
    assert result.prepared is None
    assert result.payload["messages"][0] == first.payload["messages"][0]
    assert result.payload["messages"][-2:] == payload["messages"][-2:]


def test_disabling_replays_current_tool_turn_and_new_turn_without_thinking_is_raw(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    first = _stateful(adapter, payload)
    payload["messages"] += _tool_loop()[:2]
    result = _stateful(adapter, payload, enabled=False)
    assert result.reason == "disabled_compatible_replay"
    assert result.payload["messages"][0] == first.payload["messages"][0]
    payload["messages"] += [
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "A new task."},
    ]
    new_turn = _stateful(adapter, payload, enabled=False)
    assert not new_turn.transformed and new_turn.reason == "session_disabled"
    assert new_turn.payload == payload


def test_new_turn_with_bound_thinking_requires_compatibility_replay_even_when_disabled(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    first = _stateful(adapter, payload)
    payload["messages"] += _signed_tool_loop()
    payload["messages"] += [
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "A new task."},
    ]
    result = _stateful(adapter, payload, enabled=False)
    assert result.reason == "disabled_compatible_replay"
    assert result.payload["messages"][0] == first.payload["messages"][0]
    assert result.payload["messages"][-4:] == payload["messages"][-4:]


def test_enabled_new_turn_can_replace_all_completed_old_thinking_turns(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    first = _stateful(adapter, payload)
    payload["messages"] += _signed_tool_loop()
    payload["messages"] += [
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "Which capacity is current now?"},
    ]
    result = _stateful(adapter, payload)
    assert result.prepared is not None and result.transformed
    assert result.task != first.task
    assert result.payload["messages"][-1] == payload["messages"][-1]
    assert "signed against compiled prefix" not in json.dumps(result.payload)


def test_direct_caller_new_user_turn_compiles_after_same_turn_replay(tmp_path):
    path = tmp_path / "state.sqlite3"
    payload = _request()
    first = _stateful(AnthropicAdapter(path), payload)
    assert first.prepared is not None
    payload["messages"] += _direct_tool_loop()
    replay = _stateful(AnthropicAdapter(path), payload)
    assert replay.reason == "replayed_prefix" and replay.prepared is None
    assert replay.payload["messages"][-4:] == payload["messages"][-4:]
    payload["messages"] += [
        {"role": "assistant", "content": "Finished the direct tool calls."},
        {"role": "user", "content": "What capacity was found by the lookup tools?"},
    ]
    original = copy.deepcopy(payload)
    compiled = _stateful(AnthropicAdapter(path), payload)
    assert compiled.transformed and compiled.prepared is not None
    assert compiled.reason == "old_history_compiled_cache_may_change"
    assert compiled.payload["messages"][-1] == original["messages"][-1]
    assert payload == original


def test_changed_prefix_is_not_rewritten_using_stale_mapping(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    _stateful(adapter, payload)
    payload["messages"][0]["content"] += "\nDifferent authoritative history."
    result = _stateful(adapter, payload)
    assert not result.transformed and result.reason == "original_prefix_changed"
    assert result.payload == payload


def test_native_compaction_reset_and_other_sessions_never_borrow_prefix(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    _stateful(adapter, payload)
    other = copy.deepcopy(payload)
    other["metadata"]["user_id"] = json.dumps({"session_id": "other"})
    result = adapter.adapt(other, {"X-Claude-Code-Session-Id": "other"}, enabled=False)
    assert result.reason == "session_disabled" and not result.transformed
    compacted = {**HEADERS, "x-claude-code-context-compacted": "auto"}
    reset = adapter.adapt(payload, compacted)
    assert reset.reason == "native_compaction_reset" and reset.payload == payload
    assert _stateful(adapter, payload, enabled=False).reason == "session_disabled"


def test_state_store_contains_compiled_prefix_and_hashes_not_raw_history(tmp_path):
    import sqlite3

    path = tmp_path / "state.sqlite3"
    payload = _request()
    result = _stateful(AnthropicAdapter(path), payload)
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT prefix_hash,prefix_count,replacement_json,task FROM tomc_anthropic_prefixes"
        ).fetchone()
        columns = [r[1] for r in db.execute("PRAGMA table_info(tomc_anthropic_prefixes)")]
    assert len(row[0]) == 64 and row[1] > 0
    stored = json.loads(row[2])
    assert stored["compiled_messages"] == result.payload["messages"][:1]
    assert stored["anchor_count"] == 0
    assert row[3] == result.task
    assert not any("original" in col or "raw" in col for col in columns)
    assert payload["messages"][0]["content"] not in row[2]


def test_store_error_never_sends_unreplayable_transformation(tmp_path):
    invalid_parent = tmp_path / "file"
    invalid_parent.write_text("not a directory")
    result = _stateful(AnthropicAdapter(invalid_parent / "state.sqlite3"), _request())
    assert not result.transformed and result.reason == "prefix_store_unavailable"


def test_live_claude_empty_system_effort_controls_preserved_and_replayed(tmp_path):
    payload = _request()
    control = {"role": "system", "content": [], "output_config": {"effort": "high"}}
    payload["messages"].insert(0, control)
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    first = _stateful(adapter, payload)
    assert first.transformed
    assert first.payload["messages"][0] == control
    assert first.payload["messages"][1]["role"] == "user"
    payload["messages"] += _signed_tool_loop()
    second = _stateful(AnthropicAdapter(adapter.path), payload)
    assert second.reason == "replayed_prefix"
    assert second.payload["messages"][:2] == first.payload["messages"][:2]


def test_system_text_and_unknown_control_are_complete_protected_boundaries():
    payload = _request()
    control = {
        "role": "system",
        "content": [{"type": "text", "text": "Operator notice."}],
        "output_config": {"effort": "high"},
    }
    payload["messages"].insert(1, control)
    result = adapt_request(payload, memory_budget=150, recent_messages=1, min_history_tokens=20)
    assert result.transformed
    assert result.payload["messages"][:3] == payload["messages"][:3]
    assert result.payload["messages"][1] == control
    payload["messages"][1]["output_config"] = {"unknown": "keep"}
    result = adapt_request(payload, memory_budget=150, recent_messages=1, min_history_tokens=20)
    assert result.transformed
    assert result.payload["messages"][:3] == payload["messages"][:3]


def test_short_first_turn_long_middle_preserves_anchor_thinking_and_replays(tmp_path):
    import sqlite3

    payload = _request()
    payload["messages"][:0] = [
        {"role": "user", "content": "Short initial user turn ANCHOR_PRIVATE_SENTINEL."},
        {
            "role": "system",
            "content": [{"type": "text", "text": "Operator instruction must remain."}],
            "output_config": {"effort": "high"},
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Anchor reasoning.",
                    "signature": "anchor signature",
                },
                {"type": "text", "text": "Ready."},
            ],
        },
    ]
    path = tmp_path / "state.sqlite3"
    result = _stateful(AnthropicAdapter(path), payload)
    assert result.transformed and result.anchor_count == 3
    assert result.prefix_count > result.anchor_count
    assert result.replacement_count == 4
    assert result.payload["messages"][:3] == payload["messages"][:3]
    assert result.payload["messages"][-1] == payload["messages"][-1]
    with sqlite3.connect(path) as db:
        stored = db.execute("SELECT replacement_json FROM tomc_anthropic_prefixes").fetchone()[0]
    assert "ANCHOR_PRIVATE_SENTINEL" not in stored
    assert "anchor signature" not in stored
    assert json.loads(stored)["anchor_count"] == 3
    payload["messages"] += _signed_tool_loop()
    replay = _stateful(AnthropicAdapter(path), payload)
    assert replay.reason == "replayed_prefix"
    assert replay.payload["messages"][:4] == result.payload["messages"][:4]
    assert replay.payload["messages"][-2:] == payload["messages"][-2:]


def test_prompt_id_replays_same_tool_turn_when_host_augments_current_user(tmp_path):
    path = tmp_path / "state.sqlite3"
    payload = _request()
    headers = {**HEADERS, "x-claude-code-prompt-id": "f4d960aa-d48e-42f2-b532-9eb4b3328111"}
    first = AnthropicAdapter(path).adapt(
        payload, headers, memory_budget=500, recent_messages=1, min_history_tokens=20
    )
    payload["messages"][-1]["content"].append(
        {"type": "text", "text": "Host reminder added during the tool loop."}
    )
    payload["messages"] += _tool_loop()[:2]
    replay = AnthropicAdapter(path).adapt(
        payload, headers, memory_budget=500, recent_messages=1, min_history_tokens=20
    )
    assert replay.reason == "replayed_prefix" and replay.prepared is None
    assert replay.payload["messages"][0] == first.payload["messages"][0]
    assert replay.payload["messages"][-3:] == payload["messages"][-3:]


def test_different_prompt_id_does_not_reuse_same_text_as_same_turn(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    for prompt_id in (
        "f4d960aa-d48e-42f2-b532-9eb4b3328111",
        "f4d960aa-d48e-42f2-b532-9eb4b3328222",
    ):
        result = adapter.adapt(
            payload,
            {**HEADERS, "x-claude-code-prompt-id": prompt_id},
            memory_budget=500,
            recent_messages=1,
            min_history_tokens=20,
        )
        assert result.prepared is not None


def test_cache_control_business_key_changes_are_real_prefix_changes(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    loop = _tool_loop()[:2]
    loop[0]["content"][0]["input"]["cache_control"] = {"business_setting": "before"}
    payload["messages"][2:2] = loop
    assert _stateful(adapter, payload).transformed
    payload["messages"][2]["content"][0]["input"]["cache_control"] = {"business_setting": "after"}
    result = _stateful(adapter, payload)
    assert not result.transformed and result.reason == "original_prefix_changed"


def test_new_anchor_cannot_restore_raw_prefix_under_previously_compiled_thinking(tmp_path):
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    payload = _request()
    first = _stateful(adapter, payload)
    payload["messages"] += [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Thinking against the compiled prefix",
                    "signature": "bound",
                },
                {"type": "text", "text": "Answer."},
            ],
        },
        {"role": "user", "content": "New task with an operator instruction."},
        {
            "role": "system",
            "content": "New operator instruction.",
            "output_config": {"effort": "high"},
        },
        {"role": "assistant", "content": "Understood."},
        {
            "role": "user",
            "content": "\n".join(f"Updated capacity {i} is {20 + i}." for i in range(100)),
        },
        {"role": "assistant", "content": "Recorded."},
        {"role": "user", "content": "What is the updated capacity?"},
    ]
    independent = adapt_request(
        payload, memory_budget=500, recent_messages=1, min_history_tokens=20
    )
    assert independent.transformed and independent.anchor_count > first.prefix_count
    result = _stateful(adapter, payload)
    assert result.reason == "replayed_prefix" and result.prepared is None
    assert result.payload["messages"][0] == first.payload["messages"][0]
    assert result.payload["messages"][1:] == payload["messages"][first.prefix_count :]


def test_live_system_tool_additions_keep_complete_anchor_and_definitions(tmp_path):
    payload = _request()
    control = {
        "role": "system",
        "content": [
            {"type": "text", "text": "Operator instructions."},
            {
                "type": "tool_addition",
                "tool": {
                    "type": "tool_definition",
                    "definition": {
                        "name": "fixture",
                        "input_schema": {
                            "type": "object",
                            "properties": {"cache_control": {"type": "string"}},
                        },
                    },
                },
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "output_config": {"effort": "high"},
    }
    payload["messages"][:0] = [
        {"role": "user", "content": "Short first task."},
        control,
        {
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Anchor", "signature": "original"},
                {"type": "text", "text": "Done."},
            ],
        },
    ]
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    result = _stateful(adapter, payload)
    assert result.transformed and result.anchor_count == 3
    assert result.payload["messages"][:3] == payload["messages"][:3]
    payload["messages"][1]["content"][1]["tool"]["definition"]["input_schema"]["properties"][
        "cache_control"
    ]["type"] = "number"
    assert _stateful(adapter, payload).reason == "original_prefix_changed"


def test_opaque_system_without_a_later_complete_turn_never_rewrites_earlier_prefix():
    payload = _request()
    control = {
        "role": "system",
        "content": {"future_control": {"mode": "preserve"}},
        "provider_field": True,
    }
    payload["messages"][-1:-1] = [control]
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert not result.transformed and result.reason == "protected_system_history"
    assert result.payload == payload


def test_unknown_empty_system_control_stays_in_anchor_without_relocation():
    payload = _request()
    control = {"role": "system", "content": [], "unknown_operator_policy": {"preserve": True}}
    payload["messages"].insert(1, control)
    result = adapt_request(payload, memory_budget=500, recent_messages=1, min_history_tokens=20)
    assert result.transformed and result.anchor_count == 3
    assert result.payload["messages"][:3] == payload["messages"][:3]


@pytest.mark.parametrize("effort", [{"future": True}, ["high"]])
def test_structured_unknown_system_effort_is_preserved_without_hash_type_errors(tmp_path, effort):
    payload = _request()
    payload["messages"].insert(
        1,
        {
            "role": "system",
            "content": "Keep this operator control.",
            "output_config": {"effort": effort},
        },
    )
    adapter = AnthropicAdapter(tmp_path / "state.sqlite3")
    first = _stateful(adapter, payload)
    assert first.transformed and first.anchor_count == 3
    assert first.payload["messages"][:3] == payload["messages"][:3]
    payload["messages"] += _tool_loop()[:2]
    assert _stateful(adapter, payload).reason == "replayed_prefix"


def test_conversation_compression_keeps_the_full_budget_selection(monkeypatch):
    import tomc.anthropic_request as module

    calls = []
    prepare = module.prepare_context

    def recording(*args, **kwargs):
        calls.append(kwargs.get("adaptive"))
        return prepare(*args, **kwargs)

    monkeypatch.setattr(module, "prepare_context", recording)
    assert adapt_request(_request(), memory_budget=500, min_history_tokens=20).transformed
    assert calls and set(calls) == {False}
