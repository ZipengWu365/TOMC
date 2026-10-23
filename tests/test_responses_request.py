from __future__ import annotations

import copy
import json

import pytest

from tomc.responses_request import adapt_request, extract_session_id
from tomc.tokenization import get_counter


def message(role, text, **extras):
    return {"type": "message", "role": role,
            "content": [{"type": "output_text" if role == "assistant" else "input_text",
                         "text": text}], **extras}


def request():
    items = [message("developer", "Keep developer rules exactly.")]
    for i in range(8):
        items.extend([
            message("user", f"Record project {i}. " + "The primary color is teal. " * 80),
            {"type": "reasoning", "id": f"rs_{i}", "summary": [],
             "encrypted_content": f"opaque-cipher-{i}"},
            {"type": "function_call", "id": f"fc_{i}", "call_id": f"call_{i}",
             "name": "inspect", "arguments": '{"file":"settings.json"}'},
            {"type": "function_call_output", "call_id": f"call_{i}",
             "output": "Primary color: teal. " + "Historical observation. " * 80},
            message("assistant", f"Project {i} uses teal. " + "Confirmed setting. " * 40),
        ])
    items.append(message("user", "What is the project's primary color?"))
    return {"model": "gpt-6-astra", "store": False, "stream": True,
            "reasoning": {"effort": "high", "context": "all_turns"},
            "input": items, "tools": [{"type": "function", "name": "inspect"}],
            "client_metadata": {"thread_id": "thread-123"},
            "future_option": {"preserve": [1, 2, 3]}}


def adapt(payload, **options):
    return adapt_request(payload, memory_budget=300, min_history_tokens=100, **options)


def test_real_compiler_reduces_whole_request_and_preserves_current_tail_and_opaque():
    payload = request()
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert result.prepared is not None
    assert result.prepared.compilation.compiled_memory in result.payload["input"][1]["content"][0]["text"]
    assert result.after_tokens < result.before_tokens
    assert result.payload["input"][-6:] == original["input"][-6:]
    assert result.payload["input"][0] == original["input"][0]
    # Old reasoning and its corresponding response are removed together;
    # retained recent reasoning stays byte-for-byte at the JSON data level.
    assert [i for i in result.payload["input"] if i.get("type") == "reasoning"] == [
        i for i in original["input"][-6:] if i.get("type") == "reasoning"]
    for index, item in enumerate(result.payload["input"]):
        if item.get("type") == "reasoning":
            assert result.payload["input"][index + 1]["type"] == "function_call"
    assert {k: v for k, v in result.payload.items() if k != "input"} == {
        k: v for k, v in original.items() if k != "input"}
    assert payload == original
    counter = get_counter("regex")
    for value, count in [(original, result.before_tokens), (result.payload, result.after_tokens)]:
        assert counter.count(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":"))) == count
    calls = {i["call_id"] for i in result.payload["input"] if i.get("type") == "function_call"}
    outputs = {i["call_id"] for i in result.payload["input"]
               if i.get("type") == "function_call_output"}
    assert calls == outputs


def test_all_items_after_latest_user_including_reasoning_are_unchanged():
    payload = request()
    suffix = [payload["input"][-1],
              {"type": "reasoning", "encrypted_content": "latest-opaque", "summary": []},
              {"type": "function_call", "call_id": "latest", "name": "read", "arguments": "{}"},
              {"type": "function_call_output", "call_id": "latest", "output": "result"}]
    payload["input"][-1:] = suffix
    result = adapt(payload, recent_messages=1)
    assert result.transformed
    assert result.payload["input"][-len(suffix):] == suffix


def test_installed_codex_metadata_and_custom_tool_schema_support_complete_old_turns():
    payload = request()
    for item in payload["input"]:
        if item.get("type") != "reasoning":
            item["internal_chat_message_metadata_passthrough"] = {"test": "fixture metadata"}
        if item.get("role") == "assistant":
            item["content"][0].update(annotations=[], logprobs=[])
        if item.get("type") == "function_call":
            item["type"] = "custom_tool_call"
            item["input"] = item.pop("arguments")
        elif item.get("type") == "function_call_output":
            item["type"] = "custom_tool_call_output"
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert result.payload["input"][-6:] == original["input"][-6:]
    assert result.payload["input"][0] == original["input"][0]
    assert payload == original


def test_unknown_fields_multimodal_and_encrypted_output_pairs_remain_identical():
    payload = request()
    protected = [
        message("assistant", "signed old message", encrypted_content="opaque"),
        message("user", "unknown", future_field={"key": "value"}),
        {"type": "configuration_update", "reasoning": {"effort": "high"}},
        {"type": "message", "role": "user", "content": [
            {"type": "input_image", "image_url": "https://example.com/image.png"}]},
        {"type": "additional_tools", "role": "developer", "tools": []},
    ]
    payload["input"][3]["encrypted_function_args"] = "opaque-call"
    pair = copy.deepcopy(payload["input"][3:5])
    payload["input"][6:6] = protected
    result = adapt(payload)
    assert result.transformed
    for item in [*protected, *pair]:
        assert item in result.payload["input"]


@pytest.mark.parametrize("change,reason", [
    ({"previous_response_id": "resp_existing"}, "server_side_or_incremental_history"),
    ({"conversation": "conv_existing"}, "server_side_or_incremental_history"),
    ({"context_management": []}, "native_context_management"),
    ({"input": [{"type": "compaction", "encrypted_content": "opaque"}]}, "native_compaction"),
    ({"input": "Short new prompt"}, "unsupported_input"),
    ({"client_metadata": {"x-codex-turn-metadata": json.dumps({"request_kind": "compaction"})}},
     "native_compaction"),
    ({"client_metadata": {"x-codex-turn-metadata": json.dumps({"request_kind": "memory"})}},
     "auxiliary_request"),
])
def test_stateful_native_and_auxiliary_requests_pass_through(change, reason):
    payload = request()
    payload.update(change)
    result = adapt(payload)
    assert result.payload is payload
    assert not result.transformed and result.reason == reason
    assert result.before_tokens == result.after_tokens


def test_unfinished_old_tool_turn_is_protected():
    payload = request()
    # First turn has a call without output. Its entire turn and everything after
    # it must remain, even though later users otherwise create eligible history.
    del payload["input"][4]
    result = adapt(payload)
    assert not result.transformed
    assert result.payload is payload


def test_pair_crossing_user_boundary_protects_whole_turn():
    payload = request()
    old_output = payload["input"].pop(4)
    payload["input"].append(old_output)
    result = adapt(payload)
    assert not result.transformed


def test_duplicate_or_orphan_call_output_is_not_rewritten():
    payload = request()
    payload["input"].insert(4, copy.deepcopy(payload["input"][4]))
    result = adapt(payload)
    assert result.reason == "invalid_tool_pairing"
    assert result.payload is payload


def test_current_image_only_user_cannot_reuse_a_previous_text_task():
    payload = request()
    payload["input"][-1]["content"] = [{"type": "input_image", "image_url": "data:image/png,..."}]
    assert adapt(payload).reason == "no_current_user_task"


def test_empty_memory_and_nonreduction_return_original(monkeypatch):
    from tomc import responses_request
    from tomc.easy import prepare_context

    payload = request()
    prepared = prepare_context("Evidence.", "Task", 100)
    prepared.compilation.compiled_memory = ""
    monkeypatch.setattr(responses_request, "prepare_context", lambda *args: prepared)
    result = adapt(payload)
    assert result.reason == "no_complete_memory_fits" and result.payload is payload
    prepared.compilation.compiled_memory = "very long replacement " * 20000
    result = adapt(payload)
    assert result.reason == "no_request_size_reduction" and result.payload is payload


def test_long_history_does_not_truncate_to_fit_compiler_limit():
    payload = request()
    payload["input"][1]["content"][0]["text"] = "x " * 110000
    result = adapt(payload)
    assert result.transformed
    assert payload["input"][1] in result.payload["input"]


def test_overlong_tool_output_and_its_call_are_retained_as_an_atomic_pair():
    payload = request()
    payload["input"][4]["output"] = "oversized tool result " * 12000
    result = adapt(payload)
    assert result.transformed
    assert payload["input"][3] in result.payload["input"]
    assert payload["input"][4] in result.payload["input"]


def test_utf8_evidence_and_default_short_history():
    payload = {"input": [message("user", f"项目 {i}：主颜色是青色。") for i in range(100)]}
    payload["input"].append(message("user", "主颜色是什么？"))
    result = adapt(payload, recent_messages=1)
    assert result.transformed and "青色" in result.prepared.compilation.compiled_memory
    assert not adapt_request({"input": [message("user", "你好")]}).transformed


@pytest.mark.parametrize("options", [
    {"recent_messages": 0}, {"recent_messages": True}, {"memory_budget": 0},
    {"min_history_tokens": -1}, {"memory_budget": False},
])
def test_invalid_options_do_not_change_request(options):
    payload = request()
    assert adapt_request(payload, **options).reason == "invalid_adapter_options"


@pytest.mark.parametrize("payload,headers,expected", [
    ({}, {"thread-id": "abc-123"}, "abc-123"),
    ({"client_metadata": {"thread_id": "abc-123"}}, {}, "abc-123"),
    ({"client_metadata": {"thread_id": "abc-123"}}, {"THREAD-ID": "abc-123"}, "abc-123"),
    ({"client_metadata": {"thread_id": "other"}}, {"thread-id": "abc-123"}, None),
    ({}, {"session-id": "cache-affinity", "x-client-request-id": "maybe-thread"}, None),
    ({"metadata": {"thread_id": "user-controlled"}}, {}, None),
    ({"client_metadata": {"thread_id": "bad\nvalue"}}, {"thread-id": "valid"}, None),
    ({}, {"Thread-ID": "first", "thread-id": "second"}, None),
])
def test_identity_uses_only_confirmed_nonconflicting_thread_fields(payload, headers, expected):
    assert extract_session_id(payload, headers) == expected
