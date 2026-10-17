"""Independent offline checks: synthetic messages, fake SDK, no notebook/model I/O."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from tomc import automatic_chat as chat
from tomc import model_profiles as profiles
from tomc import native_events as events
from tomc import request_context as rc


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def history():
    return [
        {"role": "system", "content": "SYSTEM_EXACT", "name": "policy"},
        {"role": "developer", "content": "DEVELOPER_EXACT"},
        {"role": "user", "content": "OLD_ALPHA " * 160},
        {"role": "assistant", "content": "OLD_REPLY_ALPHA " * 160},
        {"role": "user", "content": "OLD_BETA " * 160},
        {"role": "assistant", "content": "OLD_REPLY_BETA " * 160},
        {"role": "user", "content": "RECENT_USER_EXACT"},
        {"role": "assistant", "content": "RECENT_REPLY_EXACT"},
        {"role": "user", "content": "CURRENT_EXACT", "metadata": {"labels": ["caller"]}},
    ]


@pytest.fixture
def compiler(monkeypatch):
    calls = []

    def fake(prefix, task, budget, **options):
        calls.append({"prefix": copy.deepcopy(prefix), "task": task, "budget": budget})
        return SimpleNamespace(compiled_memory=f"COMPILED_{task}_{len(calls)}", warnings=[])

    monkeypatch.setattr(rc, "compile_memory", fake)
    return calls


def manager(**options):
    return rc.RequestContextManager(memory_budget=128, recent_messages=3, **options)


def test_protected_messages_and_caller_deep_values_remain_unchanged(compiler):
    original, before = history(), history()
    plan = manager().prepare(original, "task_A", session_key="A")
    assert plan.decision == "optimized" and len(compiler) == 1
    assert plan.messages[:2] == before[:2] and plan.messages[-3:] == before[-3:]
    source = serial(compiler[0]["prefix"])
    assert "OLD_ALPHA" in source and "OLD_BETA" in source
    assert all(
        value not in source for value in ("SYSTEM_EXACT", "DEVELOPER_EXACT", "CURRENT_EXACT")
    )
    assert plan.planned_estimated_tokens < plan.original_estimated_tokens and original == before
    plan.messages[-1]["metadata"]["labels"].append("view-only")
    assert original == before


@pytest.mark.parametrize("state", [None, "unknown", "idle"])
def test_unknown_native_capability_does_not_permanently_disable_optimization(state, compiler):
    assert manager().prepare(history(), "task", native_state=state).decision == "optimized"
    assert len(compiler) == 1


def test_active_event_passes_through_and_invalidates_cached_view(compiler):
    subject = manager(refresh_every=2)
    subject.prepare(history(), "task", session_key="A")
    active = subject.prepare(history(), "task", native_state="active", session_key="A")
    assert active.messages == history() and active.skip_reason == "native_compaction_active"
    resumed = subject.prepare(history(), "task", native_state="idle", session_key="A")
    assert resumed.decision == "optimized" and not resumed.cache_reused and len(compiler) == 2


@pytest.mark.parametrize("cooldown", [1, 2])
def test_completed_only_skips_fixed_requests_then_native_summary_can_recompile(cooldown, compiler):
    subject = manager(native_cooldown_requests=cooldown)
    incoming = history()
    incoming[2] = {"role": "assistant", "content": "NATIVE_SUMMARY_CAN_RECOMPILE " * 160}
    first = subject.prepare(incoming, "task", native_state="completed", session_key="A")
    assert first.messages == incoming and first.skip_reason == "native_compaction_completed"
    assert first.logical_request_count == 1 and compiler == []
    if cooldown == 2:
        second = subject.prepare(incoming, "task", session_key="A")
        assert (
            second.skip_reason == "native_compaction_cooldown" and second.logical_request_count == 2
        )
        assert second.messages == incoming and compiler == []
    resumed = subject.prepare(incoming, "task", session_key="A")
    assert resumed.decision == "optimized" and resumed.native_cooldown_remaining == 0
    assert "NATIVE_SUMMARY_CAN_RECOMPILE" in serial(compiler[-1]["prefix"])


@pytest.mark.parametrize("state", ["active", "unsupported"])
def test_intervening_requests_consume_cooldown_without_extending_it(state, compiler):
    subject = manager(native_cooldown_requests=2)
    subject.prepare(history(), "task", native_state="completed", session_key="A")
    subject.prepare(history(), "task", native_state=state, session_key="A")
    plan = subject.prepare(history(), "task", session_key="A")
    assert plan.decision == "optimized" and plan.logical_request_count == 3 and len(compiler) == 1


def test_refresh_two_keeps_raw_delta_then_refreshes_from_original_source(compiler):
    subject = rc.RequestContextManager(memory_budget=128, refresh_every=2, recent_messages=1)
    incoming = history()[:6] + [{"role": "assistant", "content": "RAW_TAIL_ZERO"}]
    first = subject.prepare(incoming, "stable", session_key="A")
    incoming.append({"role": "assistant", "content": "RAW_TAIL_ONE"})
    second = subject.prepare(incoming, "stable", session_key="A")
    assert first.decision == "optimized" and second.cache_reused and len(compiler) == 1
    assert {"role": "assistant", "content": "RAW_TAIL_ZERO"} in second.messages
    incoming.append({"role": "assistant", "content": "RAW_TAIL_TWO"})
    third = subject.prepare(incoming, "stable", session_key="A")
    assert not third.cache_reused and len(compiler) == 2 and third.logical_request_count == 3
    assert "RAW_TAIL_ZERO" in serial(compiler[-1]["prefix"])
    assert "COMPILED_" not in serial(compiler[-1]["prefix"])


def test_changed_task_budget_or_original_prefix_forces_refresh(compiler):
    subject = manager(refresh_every=2)
    subject.prepare(history(), "task_A", session_key="A")
    second = subject.prepare(history(), "task_B", session_key="A")
    third = subject.prepare(history(), "task_B", session_key="A", memory_budget=96)
    reset = history()
    for message in reset[2:6]:
        message["content"] = message["content"].replace("OLD_", "RESET_")
    fourth = subject.prepare(reset, "task_B", session_key="A", memory_budget=96)
    assert all(
        plan.decision == "optimized" and not plan.cache_reused for plan in (second, third, fourth)
    )
    assert len(compiler) == 4 and compiler[-1]["budget"] == 96
    assert "RESET_" in serial(compiler[-1]["prefix"]) and "OLD_" not in serial(
        compiler[-1]["prefix"]
    )


def calls_pair(prefix, content=None):
    calls = [
        {
            "id": f"{prefix}_{n}",
            "type": "function",
            "function": {"name": "lookup", "arguments": "{}"},
        }
        for n in (1, 2)
    ]
    return [
        {"role": "assistant", "content": content, "tool_calls": calls},
        {"role": "tool", "tool_call_id": f"{prefix}_1", "content": "RESULT_ONE " * 30},
        {"role": "tool", "tool_call_id": f"{prefix}_2", "content": "RESULT_TWO " * 30},
    ]


def test_recent_cut_through_parallel_result_preserves_whole_group(compiler):
    original = (
        history()[:6] + calls_pair("parallel") + [{"role": "assistant", "content": "RECENT_FINAL"}]
    )
    plan = rc.RequestContextManager(memory_budget=128, recent_messages=2).prepare(original, "task")
    assert plan.messages[-4:] == original[-4:]
    assert "parallel_" not in serial(compiler[-1]["prefix"])


def test_complete_old_parallel_group_compiles_all_calls_and_results_together(compiler):
    original = history()
    original[4:4] = calls_pair("parallel")
    plan = manager().prepare(original, "task")
    assert all(
        marker in serial(compiler[-1]["prefix"])
        for marker in ("parallel_1", "parallel_2", "RESULT_ONE", "RESULT_TWO")
    )
    native_calls = {
        call["id"] for message in plan.messages for call in message.get("tool_calls", [])
    }
    native_results = {
        message["tool_call_id"] for message in plan.messages if message["role"] == "tool"
    }
    assert native_calls == native_results == set()


def test_pending_call_and_partial_sibling_results_stay_exact(compiler):
    original = (
        history()[:6] + calls_pair("pending")[:2] + [{"role": "assistant", "content": "TAIL"}]
    )
    plan = rc.RequestContextManager(memory_budget=128, recent_messages=1).prepare(original, "task")
    assert plan.messages[-3:] == original[-3:]
    if compiler:
        assert "pending_" not in serial(compiler[-1]["prefix"])


def test_real_hybrid_default_budget_one_user_many_tool_steps_preserves_latest_task_and_six_messages(
    monkeypatch,
):
    calls, real_compile = [], rc.compile_memory

    def spy(prefix, task, budget, **options):
        calls.append((copy.deepcopy(prefix), budget))
        return real_compile(prefix, task, budget, **options)

    monkeypatch.setattr(rc, "compile_memory", spy)
    task = "Report Lantern framework and unresolved booking."
    original = history()[:2] + [{"role": "user", "content": task}]
    for step in range(24):
        identifier = f"step_{step}"
        original.extend(
            [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": identifier,
                            "type": "function",
                            "function": {"name": "lookup", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": identifier,
                    "content": f"Lantern synthetic step {step}: framework FastAPI, backup Flask; room B available but not booked. "
                    * 14,
                },
                {"role": "assistant", "content": f"STEP_{step}_EXACT"},
            ]
        )
    before = copy.deepcopy(original)
    plan = rc.RequestContextManager().prepare(original, task, session_key="agent-loop")
    assert (
        plan.decision == "optimized"
        and plan.planned_estimated_tokens < plan.original_estimated_tokens
    )
    assert (
        plan.messages[:3] == before[:3] and plan.messages[-6:] == before[-6:] and original == before
    )
    assert len(calls) == 1 and all(
        message["role"] not in ("system", "developer", "user") for message in calls[0][0]
    )
    input_count = rc.RegexCounter().count(rc.normalize(calls[0][0])[0])
    assert calls[0][1] == max(1024, (input_count * 8 + 9) // 10)
    assert plan.memory_estimated_tokens <= calls[0][1]


@pytest.mark.parametrize(
    "fragment",
    [
        {"role": "tool", "tool_call_id": "orphan", "content": "ORPHAN"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            ],
        },
        {"role": "assistant", "content": "declined", "refusal": "REFUSAL"},
        {"role": "assistant", "content": "", "audio": {"id": "audio_id"}},
        {"role": "assistant", "content": "answer", "reasoning_content": "CHAIN"},
        {"role": "assistant", "content": "answer", "annotations": [{"type": "citation"}]},
        {"role": "function", "name": "legacy", "content": "LEGACY"},
    ],
)
def test_unsupported_payload_keeps_whole_original(fragment, compiler):
    original = history()
    original.insert(4, fragment)
    plan = manager().prepare(original, "task")
    assert plan.decision == "passthrough" and plan.messages == original and compiler == []


def test_prepared_view_is_not_accidentally_recompressed(compiler):
    first = manager().prepare(history(), "task")
    compiler.clear()
    second = manager().prepare(first.messages, "task")
    assert (
        second.skip_reason == "already_optimized_input"
        and second.messages == first.messages
        and compiler == []
    )


def test_nonshrinking_view_falls_back_even_when_memory_itself_fits_budget(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(compiled_memory="word " * 75, warnings=[])

    monkeypatch.setattr(rc, "compile_memory", fake)
    original = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "word " * 90},
        {"role": "assistant", "content": "recent"},
    ]
    plan = rc.RequestContextManager(memory_budget=80, recent_messages=1).prepare(original, "task")
    assert calls == [1] and plan.skip_reason == "nonshrinking" and plan.messages == original


def test_request_budget_cannot_discard_protected_instructions_or_current_task(compiler):
    original = history()
    plan = manager(request_budget=1).prepare(original, "task")
    assert plan.decision == "passthrough" and plan.messages == original and compiler == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("refresh_every", True),
        ("refresh_every", 1.0),
        ("refresh_every", 3),
        ("native_cooldown_requests", False),
        ("native_cooldown_requests", 2.0),
        ("native_cooldown_requests", 3),
    ],
)
def test_period_settings_reject_boolean_float_or_nonperiod_values(key, value):
    with pytest.raises(ValueError):
        rc.RequestContextManager(**{key: value})


def test_explicit_session_reset_discards_native_cooldown_and_counter(compiler):
    subject = manager()
    subject.prepare(history(), "task", native_state="completed", session_key="A")
    subject.clear_session("A")
    plan = subject.prepare(history(), "task", session_key="A")
    assert plan.decision == "optimized" and plan.logical_request_count == 1


def test_forced_boundary_skip_counts_as_request_and_does_not_extend_refresh_cycle(compiler):
    subject = manager(refresh_every=2)
    subject.prepare(history(), "task", session_key="A")
    skipped = subject.prepare(
        history(), "task", session_key="A", passthrough_reason="context_boundary_crossed"
    )
    assert skipped.messages == history() and skipped.skip_reason == "context_boundary_crossed"
    assert skipped.logical_request_count == 2 and len(compiler) == 1
    resumed = subject.prepare(history(), "task", session_key="A")
    assert resumed.decision == "optimized" and not resumed.cache_reused
    assert resumed.logical_request_count == 3 and len(compiler) == 2


def test_profiles_respect_combined_input_only_and_confirmed_account_capacity():
    gpt = profiles.get_model_profile("gpt-4.1", "openai")
    gemini = profiles.get_model_profile("gemini-3.8-flash", "google")
    kimi = profiles.get_model_profile("k3", "kimi-code")
    assert gpt.input_budget(output_reserve=8192, extra_prompt_tokens=100) == 1047576 - 8192 - 100
    assert gemini.input_budget(output_reserve=8192, extra_prompt_tokens=100) == 1048576 - 100
    assert kimi.input_budget(output_reserve=8192) == 262144 - 8192
    assert (
        kimi.input_budget(output_reserve=8192, deployment_context_limit=1048576) == 1048576 - 8192
    )
    assert (
        kimi.input_budget(output_reserve=8192, deployment_context_limit=2000000) == 1048576 - 8192
    )
    assert profiles.get_model_profile("unknown-1m-model") is None
    assert profiles.get_model_profile("gpt-4.1", "wrong-provider") is None


class FakeSDK:
    def __init__(self, result=None):
        self.result = object() if result is None else result
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.calls.append(request)
        return self.result


def session(**options):
    return chat.AutomaticChatSession(
        memory_budget=128, recent_messages=3, request_budget=100000, **options
    )


def test_sdk_forwards_same_model_tools_stream_and_options_with_one_call(compiler):
    stream = iter(["one", "two"])
    sdk, subject = FakeSDK(stream), session()
    original = history()
    options = {
        "model": "original-model",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
                },
            }
        ],
        "tool_choice": "auto",
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_completion_tokens": 456,
        "temperature": 0.25,
        "extra_headers": {"X-Test": "synthetic"},
    }
    before, before_options = copy.deepcopy(original), copy.deepcopy(options)
    assert subject.create(sdk, messages=original, task="task", **options) is stream
    assert len(sdk.calls) == len(compiler) == 1 and subject.last_plan.decision == "optimized"
    assert {key: value for key, value in sdk.calls[0].items() if key != "messages"} == options
    assert original == before and options == before_options
    sdk.calls[0]["messages"][-1]["metadata"]["labels"].append("SDK-view")
    assert original == before


def test_unknown_model_without_override_does_not_assume_capacity(compiler):
    sdk, subject = FakeSDK(), chat.AutomaticChatSession(memory_budget=128)
    assert subject.create(sdk, messages=history(), model="unknown-model") is sdk.result
    assert subject.last_plan.skip_reason == "model_budget_unavailable" and compiler == []
    assert len(sdk.calls) == 1 and sdk.calls[0]["messages"] == history()


def test_profile_lookup_only_happens_when_model_changes(monkeypatch, compiler):
    lookups, real_lookup = [], profiles.get_model_profile

    def spy(model, provider):
        lookups.append((model, provider))
        return real_lookup(model, provider)

    monkeypatch.setattr(chat, "get_model_profile", spy)
    subject, sdk = session(), FakeSDK()
    for model in ("gpt-4.1", "gpt-4.1", "gpt-4o"):
        subject.create(sdk, messages=history(), task="task", model=model)
    assert lookups == [("gpt-4.1", None), ("gpt-4o", None)] and len(sdk.calls) == 3


@pytest.mark.parametrize(
    "host,start,complete",
    [
        (
            "codex",
            {"method": "item/started", "params": {"item": {"type": "contextCompaction"}}},
            {"method": "item/completed", "params": {"item": {"type": "contextCompaction"}}},
        ),
        (
            "claude",
            {"hook_event_name": "PreCompact", "trigger": "auto"},
            {"hook_event_name": "PostCompact", "trigger": "auto"},
        ),
    ],
)
def test_sdk_actual_native_events_pause_then_allow_native_summary_again(
    host, start, complete, compiler
):
    subject, sdk = session(), FakeSDK()
    assert subject.on_native_event(host, start)
    subject.create(sdk, messages=history(), task="task", model="same-model")
    assert subject.last_plan.skip_reason == "native_compaction_active" and compiler == []
    assert subject.on_native_event(host, complete)
    incoming = history()
    incoming[2] = {"role": "assistant", "content": "NATIVE_SUMMARY_REELIGIBLE " * 160}
    for reason in ("native_compaction_completed", "native_compaction_cooldown"):
        subject.create(sdk, messages=incoming, task="task", model="same-model")
        assert subject.last_plan.skip_reason == reason and compiler == []
    subject.create(sdk, messages=incoming, task="task", model="same-model")
    assert subject.last_plan.decision == "optimized" and len(compiler) == 1 and len(sdk.calls) == 4
    assert "NATIVE_SUMMARY_REELIGIBLE" in serial(compiler[0]["prefix"])


def test_unavailable_budget_calls_still_consume_native_completion_cooldown(compiler):
    subject = chat.AutomaticChatSession(
        memory_budget=128, recent_messages=3, native_cooldown_requests=2
    )
    sdk = FakeSDK()
    assert subject.on_native_event(
        "codex", {"method": "item/completed", "params": {"item": {"type": "contextCompaction"}}}
    )
    for model in ("unknown-model", "unknown-model", "gpt-4.1"):
        subject.create(sdk, messages=history(), task="task", model=model)
    assert subject.last_plan.decision == "optimized" and len(compiler) == 1 and len(sdk.calls) == 3


@pytest.mark.parametrize("policy, compilations", [("stable", 1), ("cadence", 2)])
def test_model_half_and_ninety_percent_boundaries_each_back_off_only_once(
    policy, compilations, compiler
):
    # A backoff passes the original request through without editing history, so the
    # stable policy may reuse its frozen memory afterwards; cadence recompiles.
    subject, sdk = session(provider="openai", refresh_policy=policy), FakeSDK()
    expected = ["model_window_boundary_backoff", None, "model_window_boundary_backoff", None]
    for number, (tokens, reason) in enumerate(
        zip((64000, 65000, 115200, 116000), expected), start=1
    ):
        subject.create(
            sdk,
            messages=history(),
            task="task",
            model="gpt-4o",
            context_tokens=tokens,
            max_completion_tokens=1024,
        )
        assert subject.last_plan.skip_reason == reason
        assert subject.last_plan.logical_request_count == number
        assert "context_tokens" not in sdk.calls[-1]
        if reason:
            assert sdk.calls[-1]["messages"] == history()
        else:
            assert subject.last_plan.decision == "optimized"
    assert len(sdk.calls) == 4 and len(compiler) == compilations


def test_cached_provider_usage_can_back_off_once_without_consuming_stream(compiler):
    class StreamSentinel:
        def __iter__(self):
            raise AssertionError("Wrapper must not consume provider stream")

    subject = session(provider="openai")
    sdk = FakeSDK(SimpleNamespace(usage=SimpleNamespace(prompt_tokens=64000)))
    subject.create(sdk, messages=history(), task="task", model="gpt-4o")
    assert subject.last_plan.decision == "optimized"
    stream = StreamSentinel()
    sdk.result = stream
    assert (
        subject.create(sdk, messages=history(), task="task", model="gpt-4o", stream=True) is stream
    )
    assert subject.last_plan.skip_reason == "model_window_boundary_backoff"
    assert (
        subject.create(sdk, messages=history(), task="task", model="gpt-4o", stream=True) is stream
    )
    assert subject.last_plan.decision == "optimized" and len(sdk.calls) == 3


@pytest.mark.parametrize(
    "host,event",
    [
        (
            "codex",
            {
                "method": "thread/tokenUsage/updated",
                "params": {"totalTokens": 999999, "compaction": "active"},
            },
        ),
        ("codex", {"enabled": True, "type": "contextCompaction"}),
        ("codex", {"method": "item/started", "params": {"item": {"type": "agentMessage"}}}),
        ("codex", {"method": "item/started", "params": "malformed"}),
        ("claude", {"hook_event_name": "PreCompact", "trigger": "unknown"}),
        ("unknown", {"method": "item/started", "params": {"item": {"type": "contextCompaction"}}}),
    ],
)
def test_usage_capability_and_unrecognized_events_are_not_compaction(host, event, compiler):
    assert events.extract_state(host, event) is None
    subject, sdk = session(), FakeSDK()
    assert not subject.on_native_event(host, event)
    subject.create(sdk, messages=history(), task="task", model="same-model")
    assert subject.last_plan.decision == "optimized" and len(compiler) == len(sdk.calls) == 1


def _stable(**options):
    return rc.RequestContextManager(
        memory_budget=128, recent_messages=1, refresh_policy="stable", **options
    )


def _prefix_before_tail(plan):
    return [m for m in plan.messages if not str(m.get("content", "")).startswith("RAW_")]


def test_stable_policy_reuses_identical_memory_across_changing_tasks(compiler):
    subject = _stable()
    incoming = history()[:6] + [{"role": "user", "content": "RAW_Q1"}]
    first = subject.prepare(incoming, "question_one", session_key="A")
    incoming += [{"role": "assistant", "content": "RAW_A1"}, {"role": "user", "content": "RAW_Q2"}]
    second = subject.prepare(incoming, "question_two", session_key="A")
    incoming += [{"role": "assistant", "content": "RAW_A2"}, {"role": "user", "content": "RAW_Q3"}]
    third = subject.prepare(incoming, "question_three", session_key="A")
    assert first.decision == "optimized" and len(compiler) == 1
    assert second.cache_reused and third.cache_reused
    # The compiled block and everything before the new tail is byte-identical.
    head = first.messages[:-1]
    assert second.messages[: len(head)] == head and third.messages[: len(head)] == head
    assert second.messages[-3:] == incoming[-5:-2] or "RAW_Q2" in serial(second.messages)
    assert third.messages[-1] == {"role": "user", "content": "RAW_Q3"}


def test_stable_policy_rebuilds_after_growth_allowance(compiler):
    subject = _stable(stable_growth_tokens=40)
    incoming = history()[:6] + [{"role": "user", "content": "RAW_Q1"}]
    subject.prepare(incoming, "task", session_key="A")
    incoming += [
        {"role": "assistant", "content": "RAW_SMALL"},
        {"role": "user", "content": "RAW_Q2"},
    ]
    small = subject.prepare(incoming, "task", session_key="A")
    incoming += [
        {"role": "assistant", "content": "RAW_LONG " * 80},
        {"role": "user", "content": "RAW_Q3"},
    ]
    grown = subject.prepare(incoming, "task", session_key="A")
    assert small.cache_reused and not grown.cache_reused and len(compiler) == 2
    assert "RAW_LONG" in serial(compiler[-1]["prefix"])
    assert "COMPILED_" not in serial(compiler[-1]["prefix"])


def test_stable_policy_rebuilds_when_source_prefix_or_budget_changes(compiler):
    subject = _stable()
    incoming = history()[:6] + [{"role": "user", "content": "RAW_Q1"}]
    subject.prepare(incoming, "task", session_key="A")
    edited = copy.deepcopy(incoming)
    edited[2]["content"] = "EDITED " * 160
    changed = subject.prepare(edited, "task", session_key="A")
    rebudget = subject.prepare(edited, "task", session_key="A", memory_budget=96)
    assert not changed.cache_reused and not rebudget.cache_reused and len(compiler) == 3


def test_stable_policy_still_respects_request_budget(compiler):
    subject = _stable(stable_growth_tokens=100000)
    incoming = history()[:6] + [{"role": "user", "content": "RAW_Q1"}]
    subject.prepare(incoming, "task", session_key="A", request_budget=100000)
    incoming += [
        {"role": "assistant", "content": "OLD_GROWTH " * 300},
        {"role": "user", "content": "RAW_Q2"},
    ]
    plan = subject.prepare(incoming, "task", session_key="A", request_budget=700)
    # The frozen memory is only reused when the whole request still fits.
    assert plan.decision == "passthrough" or plan.planned_estimated_tokens <= 700
    tight = subject.prepare(incoming, "task", session_key="A", request_budget=500)
    assert tight.decision == "passthrough" or tight.planned_estimated_tokens <= 500


def test_invalid_refresh_policy_and_growth_are_rejected():
    with pytest.raises(ValueError):
        rc.RequestContextManager(refresh_policy="sometimes")
    with pytest.raises(ValueError):
        rc.RequestContextManager(stable_growth_tokens=0)


def test_automatic_chat_defaults_to_stable_prefix_policy():
    subject = chat.AutomaticChatSession()
    assert subject.manager.refresh_policy == "stable"
    legacy = chat.AutomaticChatSession(refresh_policy="cadence", refresh_every=1)
    assert legacy.manager.refresh_policy == "cadence" and legacy.manager.refresh_every == 1


def test_stable_policy_default_does_not_rebuild_for_growth_alone(compiler):
    subject = _stable()
    incoming = history()[:6] + [{"role": "user", "content": "RAW_Q1"}]
    subject.prepare(incoming, "task", session_key="A")
    for turn in range(5):
        incoming += [
            {"role": "assistant", "content": "RAW_LONG " * 200},
            {"role": "user", "content": f"RAW_Q{turn + 2}"},
        ]
        plan = subject.prepare(incoming, f"task_{turn}", session_key="A")
        assert plan.cache_reused
    assert len(compiler) == 1
