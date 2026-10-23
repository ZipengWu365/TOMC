"""Forms track one context input length, independently of lifetime accounting."""

import pytest

from tomc.pet_growth import growth_state, request_stage
from tomc.usage import UsageStore


def report(before, after, usable=True, counter="estimate"):
    return {"counter": counter, "input_tokens": before, "memory_tokens": after,
            "usable": usable, "reduced_tokens": before-after if usable else None}


def test_form_uses_this_input_and_can_decrease_after_restart(tmp_path):
    path = tmp_path / "pet.sqlite3"
    store = UsageStore(path)
    # A tiny reduction does not hide the length of the input being compressed.
    store.record(report(1_000_000, 999_999))
    large = growth_state(store.summary())
    assert large["level"] == 4 and large["input_tokens"] == 1_000_000
    assert large["opacity"] == 1 and large["notes"] == 18
    store.record(report(100, 200, counter="other-counter"))
    restarted = UsageStore(path)
    small = growth_state(restarted.summary())
    assert small["level"] == 1 and small["input_tokens"] == 100
    assert small["counter"] == "other-counter" and not small["mixed"]
    assert small["opacity"] < large["opacity"] and small["notes"] == 2
    assert growth_state(store.summary("today")) == growth_state(store.summary("7d"))


@pytest.mark.parametrize("tokens,level", [
    (0, 1), (5000, 1), (9999, 1), (10000, 2), (99999, 2),
    (100000, 3), (999999, 3), (1000000, 4), (2000000, 4),
])
def test_input_length_boundaries_keep_four_original_assets(tokens, level):
    state = request_stage(tokens)
    assert state["level"] == level and state["length_known"]
    assert state["input_tokens"] == tokens
    assert state["asset"] == f"tomc-expression-{level}.png"
    assert state["thresholds"] == [0, 10000, 100000, 1000000]
    assert state["stage_basis"] == "request_input_length"
    assert 0 <= state["progress"] <= 1 and 0.35 <= state["opacity"] <= 1
    assert "解锁" not in state["hint"] and "累计" not in state["hint"]


def test_totals_peaks_reduction_and_other_counters_do_not_choose_form():
    summary = {"growth": [
        {"counter": "estimate", "peak_net_tokens": 50_000_000, "net_tokens": 50_000_000},
        {"counter": "tokenizer", "peak_net_tokens": 60_000_000, "net_tokens": 60_000_000}],
        "last_preparation": {"counter": "estimate", "input_tokens": 10_000,
                             "reduced_tokens": 1, "usable": True}}
    state = growth_state(summary)
    assert state["level"] == 2 and state["input_tokens"] == 10_000
    assert state["opacity"] == 0.58 and state["progress"] == 0
    assert state["counter"] == "estimate" and not state["mixed"]
    assert "peak_net_tokens" not in state and "net_tokens" not in state
    assert "本次输入距下一档（100,000）还差 90,000" in state["hint"]
    english = growth_state(summary, "en")
    assert "90,000 more input tokens in this request" in english["hint"]
    assert {k: v for k, v in state.items() if k != "hint"} == {
        k: v for k, v in english.items() if k != "hint"}


@pytest.mark.parametrize("length", [None, -1, True, "1000000", 1.5, float("nan")])
def test_unknown_or_invalid_length_is_neutral_not_an_invented_zero(length):
    state = request_stage(length, "en")
    assert state["level"] == 1 and state["opacity"] == 0.35
    assert state["input_tokens"] is None and not state["length_known"]
    assert state["progress"] == 0 and state["notes"] == 2
    assert "unknown" in state["hint"]


def test_missing_or_unusable_latest_record_cannot_borrow_historical_length(tmp_path):
    store = UsageStore(tmp_path / "pet.sqlite3")
    assert not growth_state(store.summary())["length_known"]
    store.record(report(2_000_000, 1))
    assert growth_state(store.summary())["level"] == 4
    store.record(report(2_000_000, 0, usable=False))
    state = growth_state(store.summary())
    assert state["level"] == 1 and state["input_tokens"] is None
    assert not state["length_known"] and state["counter"] is None
    assert growth_state({"growth": [{"peak_net_tokens": 2_000_000}]})["level"] == 1


@pytest.mark.parametrize("counter", ["regex-request-json-v1 (estimate)", "entire-payload"])
def test_gateway_envelope_length_is_never_used_as_context_length(counter):
    latest = {"counter": counter, "input_tokens": 1_000_000, "usable": True}
    unknown = growth_state({"last_preparation": latest})
    assert not unknown["length_known"] and unknown["level"] == 1
    latest["context_input_tokens"] = 10_000
    known = growth_state({"last_preparation": latest})
    assert known["level"] == 2 and known["input_tokens"] == 10_000
    latest["context_input_tokens"] = 0
    assert growth_state({"last_preparation": latest})["input_tokens"] == 0


def test_explicit_context_length_takes_priority_for_ordinary_preparations_too():
    state = growth_state({"last_preparation": {
        "counter": "regex-v1 (estimate)", "input_tokens": 1_000_000,
        "context_input_tokens": 100_000, "usable": True}})
    assert state["level"] == 3 and state["input_tokens"] == 100_000


def test_numeric_animation_queue_is_ordered_paged_and_read_only(tmp_path):
    store = UsageStore(tmp_path / "events.sqlite3")
    assert store.recent_events() == [] and not store.path.exists()
    for i in range(70):
        store.record(report(100+i, 10))
    # A burst is never silently truncated: every event can play once, in order.
    events = store.recent_events()
    assert [event["seq"] for event in events] == list(range(1, 71))
    page = store.recent_events(0, limit=64)
    assert len(page) == 64 and page[-1]["seq"] == 64
    assert [event["seq"] for event in store.recent_events(page[-1]["seq"])] == list(range(65, 71))
    assert store.recent_events(69)[0]["reduced_tokens"] == 159
    assert store.recent_events(70) == []
    assert store.summary()["preparations"] == 70
