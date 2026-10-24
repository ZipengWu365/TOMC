from __future__ import annotations

import copy
import json

import pytest

from tomc.responses_request import adapt_request, classify_request, extract_session_id
from tomc.tokenization import get_counter


def message(role, text, **extras):
    return {
        "type": "message",
        "role": role,
        "content": [{"type": "output_text" if role == "assistant" else "input_text", "text": text}],
        **extras,
    }


def request():
    items = [message("developer", "Keep developer rules exactly.")]
    for i in range(8):
        items.extend(
            [
                message("user", f"Record project {i}. " + "The primary color is teal. " * 80),
                {
                    "type": "reasoning",
                    "id": f"rs_{i}",
                    "summary": [],
                    "encrypted_content": f"opaque-cipher-{i}",
                },
                {
                    "type": "function_call",
                    "id": f"fc_{i}",
                    "call_id": f"call_{i}",
                    "name": "inspect",
                    "arguments": '{"file":"settings.json"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": f"call_{i}",
                    "output": "Primary color: teal. " + "Historical observation. " * 80,
                },
                message("assistant", f"Project {i} uses teal. " + "Confirmed setting. " * 40),
            ]
        )
    items.append(message("user", "What is the project's primary color?"))
    return {
        "model": "gpt-6-astra",
        "store": False,
        "stream": True,
        "reasoning": {"effort": "high", "context": "all_turns"},
        "input": items,
        "tools": [{"type": "function", "name": "inspect"}],
        "client_metadata": {"thread_id": "thread-123"},
        "future_option": {"preserve": [1, 2, 3]},
    }


def adapt(payload, **options):
    return adapt_request(payload, memory_budget=300, min_history_tokens=100, **options)


def test_real_compiler_reduces_whole_request_and_preserves_current_tail_and_opaque():
    payload = request()
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert result.prepared is not None
    assert (
        result.prepared.compilation.compiled_memory
        in result.payload["input"][1]["content"][0]["text"]
    )
    assert result.after_tokens < result.before_tokens
    assert result.payload["input"][-6:] == original["input"][-6:]
    assert result.payload["input"][0] == original["input"][0]
    # Old reasoning and its corresponding response are removed together;
    # retained recent reasoning stays byte-for-byte at the JSON data level.
    assert [i for i in result.payload["input"] if i.get("type") == "reasoning"] == [
        i for i in original["input"][-6:] if i.get("type") == "reasoning"
    ]
    for index, item in enumerate(result.payload["input"]):
        if item.get("type") == "reasoning":
            assert result.payload["input"][index + 1]["type"] == "function_call"
    assert {k: v for k, v in result.payload.items() if k != "input"} == {
        k: v for k, v in original.items() if k != "input"
    }
    assert payload == original
    counter = get_counter("regex")
    for value, count in [(original, result.before_tokens), (result.payload, result.after_tokens)]:
        assert (
            counter.count(
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            == count
        )
    calls = {i["call_id"] for i in result.payload["input"] if i.get("type") == "function_call"}
    outputs = {
        i["call_id"] for i in result.payload["input"] if i.get("type") == "function_call_output"
    }
    assert calls == outputs


def test_all_items_after_latest_user_including_reasoning_are_unchanged():
    payload = request()
    suffix = [
        payload["input"][-1],
        {"type": "reasoning", "encrypted_content": "latest-opaque", "summary": []},
        {"type": "function_call", "call_id": "latest", "name": "read", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "latest", "output": "result"},
    ]
    payload["input"][-1:] = suffix
    result = adapt(payload, recent_messages=1)
    assert result.transformed
    assert result.payload["input"][-len(suffix) :] == suffix


def test_installed_codex_metadata_and_custom_tool_schema_support_complete_old_turns():
    payload = request()
    for item in payload["input"]:
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


def codex_context(cwd="/fixture/project"):
    """Codex 0.163 sends AGENTS.md and environment details as one user-role message."""
    return {
        "type": "message",
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": f"# AGENTS.md instructions for {cwd}\n\n<INSTRUCTIONS>\n"
                + "Always run the fixture tests before answering. " * 300
                + "\n</INSTRUCTIONS>",
            },
            {
                "type": "input_text",
                "text": f"<environment_context>\n  <cwd>{cwd}</cwd>\n</environment_context>",
            },
        ],
    }


def test_host_context_messages_stay_instructions_and_are_never_compiled():
    payload = request()
    context = codex_context()
    update = message("user", "<environment_context>\n  <cwd>/other</cwd>\n</environment_context>")
    payload["input"].insert(1, context)
    # [developer, context, turn 0 (5 items), environment update, turn 1, ...]
    payload["input"].insert(7, update)
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    memory = result.prepared.compilation.compiled_memory
    assert "AGENTS.md" not in memory and "environment_context" not in memory
    assert "fixture tests" not in memory
    assert result.payload["input"][:2] == original["input"][:2]
    assert "<tomc_history>" in result.payload["input"][2]["content"][0]["text"]
    assert update in result.payload["input"]
    assert original["input"][2] not in result.payload["input"]


def test_host_context_alone_is_not_old_history():
    payload = {
        "input": [
            message("developer", "Keep developer rules exactly."),
            codex_context(),
            message("user", "Hello."),
            message("assistant", "Hi."),
            message("user", "What changed?"),
        ]
    }
    result = adapt(payload, recent_messages=1)
    assert not result.transformed and result.reason == "history_below_threshold"


def test_user_turn_mixing_host_context_with_its_text_stays_verbatim():
    payload = request()
    environment = "<environment_context>\n  <cwd>/fixture</cwd>\n</environment_context>"
    payload["input"][1]["content"].insert(0, {"type": "input_text", "text": environment})
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert result.payload["input"][1:6] == original["input"][1:6]
    assert "environment_context" not in result.prepared.compilation.compiled_memory


def test_codex_reasoning_metadata_tool_namespace_and_agent_message_compile():
    payload = request()
    for item in payload["input"]:
        item["internal_chat_message_metadata_passthrough"] = {"turn_id": "fixture"}
        if item.get("type") == "function_call":
            item["namespace"] = "fixture_tools"
    agent = {
        "type": "agent_message",
        "id": "am_0",
        "author": "/root/worker",
        "recipient": "/root",
        "content": [{"type": "input_text", "text": "Worker confirmed the teal setting."}],
        "internal_chat_message_metadata_passthrough": {"turn_id": "fixture"},
    }
    payload["input"].insert(5, agent)
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    for item in original["input"][1:7]:
        assert item not in result.payload["input"]
    assert result.payload["input"][-6:] == original["input"][-6:]


def test_encrypted_agent_message_keeps_its_whole_turn_verbatim():
    payload = request()
    agent = {
        "type": "agent_message",
        "author": "/root/worker",
        "recipient": "/root",
        "content": [
            {"type": "input_text", "text": "Done."},
            {"type": "encrypted_content", "encrypted_content": "opaque"},
        ],
    }
    payload["input"].insert(5, agent)
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert result.payload["input"][1:7] == original["input"][1:7]


def test_configuration_update_stays_in_place_while_its_turn_compiles():
    payload = request()
    update = {"type": "configuration_update", "reasoning": {"effort": "xhigh"}}
    payload["input"].insert(3, update)
    original = copy.deepcopy(payload)
    result = adapt(payload)
    assert result.transformed
    assert update in result.payload["input"]
    assert original["input"][1] not in result.payload["input"]


def test_unknown_fields_multimodal_and_encrypted_output_pairs_remain_identical():
    payload = request()
    protected = [
        message("assistant", "signed old message", encrypted_content="opaque"),
        message("user", "unknown", future_field={"key": "value"}),
        {"type": "configuration_update", "reasoning": {"effort": "high"}},
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_image", "image_url": "https://example.com/image.png"}],
        },
        {"type": "additional_tools", "role": "developer", "tools": []},
    ]
    payload["input"][3]["encrypted_function_args"] = "opaque-call"
    pair = copy.deepcopy(payload["input"][3:5])
    payload["input"][6:6] = protected
    result = adapt(payload)
    assert result.transformed
    for item in [*protected, *pair]:
        assert item in result.payload["input"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"previous_response_id": "resp_existing"}, "server_side_or_incremental_history"),
        ({"conversation": "conv_existing"}, "server_side_or_incremental_history"),
        ({"context_management": []}, "native_context_management"),
        (
            {"input": [{"type": "compaction", "encrypted_content": "opaque"}]},
            "native_compaction_state",
        ),
        ({"input": "Short new prompt"}, "unsupported_input"),
        (
            {
                "client_metadata": {
                    "x-codex-turn-metadata": json.dumps({"request_kind": "compaction"})
                }
            },
            "host_compaction_request",
        ),
        (
            {"client_metadata": {"x-codex-turn-metadata": json.dumps({"request_kind": "memory"})}},
            "auxiliary_request",
        ),
        ({"client_metadata": {"x-codex-turn-metadata": "{not json"}}, "unknown_request_metadata"),
    ],
)
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
    monkeypatch.setattr(responses_request, "prepare_context", lambda *args, **kwargs: prepared)
    result = adapt(payload)
    assert result.reason == "no_complete_memory_fits" and result.payload is payload
    prepared.compilation.compiled_memory = "very long replacement " * 20000
    result = adapt(payload)
    assert result.reason == "no_request_size_reduction" and result.payload is payload


def test_long_old_turn_is_compiled_whole_not_truncated():
    payload = request()
    payload["input"][1]["content"][0]["text"] = "x " * 110000
    result = adapt(payload)
    assert result.transformed
    assert payload["input"][1] not in result.payload["input"]
    # The entire 110,000-token turn reached the compiler; nothing was cut to fit.
    assert result.prepared.compilation.stats.input_tokens >= 110_000


def test_overlong_tool_output_and_its_call_are_compiled_as_an_atomic_pair():
    payload = request()
    payload["input"][4]["output"] = "oversized tool result " * 12000
    result = adapt(payload)
    assert result.transformed
    assert payload["input"][3] not in result.payload["input"]
    assert payload["input"][4] not in result.payload["input"]
    calls = {i["call_id"] for i in result.payload["input"] if i.get("type") == "function_call"}
    outputs = {
        i["call_id"] for i in result.payload["input"] if i.get("type") == "function_call_output"
    }
    assert calls == outputs


def test_utf8_evidence_and_default_short_history():
    payload = {"input": [message("user", f"项目 {i}：主颜色是青色。") for i in range(100)]}
    payload["input"].append(message("user", "主颜色是什么？"))
    result = adapt(payload, recent_messages=1)
    assert result.transformed and "青色" in result.prepared.compilation.compiled_memory
    assert not adapt_request({"input": [message("user", "你好")]}).transformed


@pytest.mark.parametrize(
    "options",
    [
        {"recent_messages": 0},
        {"recent_messages": True},
        {"memory_budget": 0},
        {"min_history_tokens": -1},
        {"memory_budget": False},
    ],
)
def test_invalid_options_do_not_change_request(options):
    payload = request()
    assert adapt_request(payload, **options).reason == "invalid_adapter_options"


@pytest.mark.parametrize(
    "payload,headers,expected",
    [
        ({}, {"thread-id": "abc-123"}, "abc-123"),
        ({"client_metadata": {"thread_id": "abc-123"}}, {}, "abc-123"),
        ({"client_metadata": {"thread_id": "abc-123"}}, {"THREAD-ID": "abc-123"}, "abc-123"),
        ({"client_metadata": {"thread_id": "other"}}, {"thread-id": "abc-123"}, None),
        ({}, {"session-id": "cache-affinity", "x-client-request-id": "maybe-thread"}, None),
        ({"metadata": {"thread_id": "user-controlled"}}, {}, None),
        ({"client_metadata": {"thread_id": "bad\nvalue"}}, {"thread-id": "valid"}, None),
        ({}, {"Thread-ID": "first", "thread-id": "second"}, None),
    ],
)
def test_identity_uses_only_confirmed_nonconflicting_thread_fields(payload, headers, expected):
    assert extract_session_id(payload, headers) == expected


def codex_turn(kind="turn", window=0, agent="/root", **extra):
    """Turn metadata shaped like Codex 0.163.0-alpha.11.2 and 0.163.0 (isolated probe, 2026-10-23)."""
    return json.dumps(
        {
            "installation_id": "fixture-installation",
            "session_id": "thread-123",
            "thread_id": "thread-123",
            "agent_name": agent,
            "turn_id": "fixture-turn",
            "window_id": f"thread-123:{window}",
            "window_number": window,
            "context_window_id": "fixture-window",
            "request_kind": kind,
            "history_initialization": "new",
            "root_turn_id": "fixture-turn",
            "sandbox": "none",
            "sandbox_mode": "read-only",
            **extra,
        }
    )


def compaction_meta(trigger="manual", phase="standalone_turn", reason="user_requested"):
    return {
        "trigger": trigger,
        "reason": reason,
        "implementation": "responses_compaction_v2",
        "phase": phase,
        "strategy": "memento",
    }


def memento_input(task="Continue the task."):
    """History after a v2 compaction: re-injected context, kept user turns, one opaque item."""
    return [
        {"type": "additional_tools", "role": "developer", "tools": []},
        message("developer", "Keep developer rules exactly."),
        message("user", "Earlier user request retained by the host."),
        {"type": "compaction", "id": "cmp_fixture", "encrypted_content": "FIXTURE_OPAQUE_STATE"},
        message("user", task),
    ]


def test_fresh_codex_turn_is_eligible_and_detail_is_structural_only():
    payload = request()
    payload["client_metadata"]["x-codex-turn-metadata"] = codex_turn()
    reason, detail = classify_request(payload, {"x-codex-turn-metadata": codex_turn()})
    assert reason is None
    assert detail == {
        "request_kind": "turn",
        "window": 0,
        "history_initialization": "new",
        "agent": "root",
    }
    assert adapt(payload).transformed


@pytest.mark.parametrize(
    "trigger,phase,reason",
    [("manual", "standalone_turn", "user_requested"), ("auto", "pre_turn", "context_limit")],
)
def test_v2_host_compaction_turn_is_the_hosts_and_never_rewritten(trigger, phase, reason):
    payload = request()
    payload["input"].append({"type": "compaction_trigger"})
    metadata = codex_turn(
        "compaction", window=1, compaction=compaction_meta(trigger, phase, reason)
    )
    payload["client_metadata"]["x-codex-turn-metadata"] = metadata
    label, detail = classify_request(payload, {"X-Codex-Turn-Metadata": metadata})
    assert label == "host_compaction_request"
    assert detail == {
        "request_kind": "compaction",
        "compaction_trigger": trigger,
        "compaction_phase": phase,
        "compaction_reason": reason,
        "window": 1,
        "history_initialization": "new",
        "agent": "root",
        "compaction_trigger_item": True,
    }
    result = adapt(payload)
    assert (
        not result.transformed
        and result.reason == "host_compaction_request"
        and result.payload is payload
    )


def test_header_alone_identifies_compaction_when_body_metadata_is_absent():
    payload = request()
    metadata = codex_turn(
        "compaction", compaction=compaction_meta("auto", "pre_turn", "context_limit")
    )
    assert (
        classify_request(payload, {"x-codex-turn-metadata": metadata})[0]
        == "host_compaction_request"
    )


def test_ordinary_turn_carrying_opaque_state_is_host_managed_with_generation():
    payload = {
        "model": "gpt-6-astra",
        "store": False,
        "input": memento_input(),
        "client_metadata": {
            "thread_id": "thread-123",
            "x-codex-turn-metadata": codex_turn(window=2),
        },
    }
    reason, detail = classify_request(payload, {})
    assert reason == "native_compaction_state"
    assert (
        detail["compaction_items"] == 1
        and detail["window"] == 2
        and detail["request_kind"] == "turn"
    )
    serialized = json.dumps(detail)
    for private in (
        "FIXTURE_OPAQUE_STATE",
        "fixture-installation",
        "fixture-turn",
        "thread-123",
        "Earlier user request",
        "Keep developer rules",
    ):
        assert private not in serialized
    assert adapt(payload).reason == "native_compaction_state"


def test_guardian_subagent_inherits_parent_opaque_state_and_is_labelled_without_its_name():
    payload = {
        "input": memento_input("Review this action."),
        "client_metadata": {
            "thread_id": "child",
            "x-codex-turn-metadata": codex_turn(agent="/root/guardian_review"),
        },
    }
    reason, detail = classify_request(payload, {})
    assert reason == "native_compaction_state" and detail["agent"] == "subagent"
    assert "guardian" not in json.dumps(detail)


def test_unreadable_turn_metadata_header_is_unknown_not_eligible():
    payload = request()
    assert (
        classify_request(payload, {"x-codex-turn-metadata": "{broken"})[0]
        == "unknown_request_metadata"
    )


def test_conflicting_kinds_favour_the_host_owned_label():
    payload = request()
    payload["client_metadata"]["x-codex-turn-metadata"] = codex_turn("turn")
    header = codex_turn("memory")
    assert classify_request(payload, {"x-codex-turn-metadata": header})[0] == "auxiliary_request"


def test_conversation_compression_keeps_the_full_budget_selection(monkeypatch):
    import tomc.responses_request as module

    calls = []
    prepare = module.prepare_context

    def recording(*args, **kwargs):
        calls.append(kwargs.get("adaptive"))
        return prepare(*args, **kwargs)

    monkeypatch.setattr(module, "prepare_context", recording)
    assert adapt(request()).transformed
    assert calls and set(calls) == {False}
