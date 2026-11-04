"""The cat grows with cumulative tokens saved and keeps a form once earned."""

import pytest

from tomc.pet_growth import (
    LENGTH_BANDS,
    context_length,
    growth_state,
    paper_notes,
    request_stage,
    saved_stage,
)
from tomc.usage import UsageStore


def report(before, after, usable=True, counter="estimate"):
    return {
        "counter": counter,
        "input_tokens": before,
        "memory_tokens": after,
        "usable": usable,
        "reduced_tokens": before - after if usable else None,
    }


def test_form_grows_with_total_saving_and_is_kept_after_an_increase(tmp_path):
    path = tmp_path / "pet.sqlite3"
    store = UsageStore(path)
    assert not growth_state(store.summary())["known"]
    store.record(report(60_000, 10_000))
    assert growth_state(store.summary())["level"] == 1
    store.record(report(60_000, 10_000))
    grown = growth_state(UsageStore(path).summary())
    assert grown["level"] == 2 and grown["saved_tokens"] == 100_000
    assert grown["stage_basis"] == "cumulative_saved_tokens"
    # A later preparation that adds context lowers the net, never the earned form.
    store.record(report(1_000, 50_000))
    kept = growth_state(store.summary())
    assert kept["level"] == 2 and kept["saved_tokens"] == 100_000
    assert growth_state(store.summary("today")) == growth_state(store.summary("7d"))


@pytest.mark.parametrize(
    "tokens,level",
    [
        (0, 1),
        (99_999, 1),
        (100_000, 2),
        (999_999, 2),
        (1_000_000, 3),
        (9_999_999, 3),
        (10_000_000, 4),
        (50_000_000, 4),
    ],
)
def test_saving_boundaries_keep_four_original_assets(tokens, level):
    state = saved_stage(tokens)
    assert state["level"] == level and state["known"]
    assert state["saved_tokens"] == tokens
    assert state["asset"] == f"tomc-expression-{level}.png"
    assert state["thresholds"] == [0, 100_000, 1_000_000, 10_000_000]
    assert 0 <= state["progress"] <= 1 and 0.35 <= state["opacity"] <= 1
    assert "累计" in state["hint"] and "估算" in state["hint"]
    assert "estimate" in saved_stage(tokens, "en")["hint"]


def test_counters_are_never_added_together_and_peaks_are_kept():
    summary = {
        "growth": [
            {"counter": "estimate", "peak_net_tokens": 900_000, "net_tokens": 400_000},
            {"counter": "tokenizer", "peak_net_tokens": 800_000, "net_tokens": 800_000},
        ],
        "last_preparation": {"counter": "estimate", "input_tokens": 5_000_000, "usable": True},
    }
    state = growth_state(summary)
    # 900K + 800K would be stage 3; the largest single counter is stage 2.
    assert state["level"] == 2 and state["saved_tokens"] == 900_000
    assert "再省 100,000 到第 3 阶段（1,000,000）" in state["hint"]
    english = growth_state(summary, "en")
    assert "100,000 more to stage 3" in english["hint"]
    assert {k: v for k, v in state.items() if k != "hint"} == {
        k: v for k, v in english.items() if k != "hint"
    }


@pytest.mark.parametrize("total", [None, -1, True, "1000000", 1.5, float("nan")])
def test_unknown_or_invalid_total_is_neutral_not_an_invented_zero(total):
    state = saved_stage(total, "en")
    assert state["level"] == 1 and state["opacity"] == 0.35
    assert state["saved_tokens"] is None and not state["known"]
    assert state["progress"] == 0 and "not available" in state["hint"]


def test_one_request_plays_the_earned_form_and_only_its_paper_follows_length():
    earned = saved_stage(2_000_000)
    long = request_stage(report(1_000_000, 999_999), earned)
    short = request_stage(report(100, 200, counter="other-counter"), earned)
    assert long["level"] == short["level"] == 3 and long["asset"] == earned["asset"]
    assert long["input_tokens"] == 1_000_000 and long["notes"] == 18
    assert short["input_tokens"] == 100 and short["notes"] == 2
    assert short["counter"] == "other-counter" and long["length_known"]
    unusable = request_stage(report(2_000_000, 0, usable=False), earned)
    assert not unusable["length_known"] and unusable["input_tokens"] is None
    assert unusable["level"] == 3 and unusable["counter"] is None
    assert request_stage(report(10_000, 1))["level"] == 1


@pytest.mark.parametrize("counter", ["regex-request-json-v1 (estimate)", "entire-payload"])
def test_gateway_envelope_length_is_never_used_as_context_length(counter):
    latest = {"counter": counter, "input_tokens": 1_000_000, "usable": True}
    assert context_length(latest) is None
    latest["context_input_tokens"] = 10_000
    assert context_length(latest) == 10_000
    latest["context_input_tokens"] = 0
    assert context_length(latest) == 0


def test_explicit_context_length_takes_priority_for_ordinary_preparations_too():
    latest = {
        "counter": "regex-v1 (estimate)",
        "input_tokens": 1_000_000,
        "context_input_tokens": 100_000,
        "usable": True,
    }
    assert context_length(latest) == 100_000
    assert paper_notes(None) == 2 and LENGTH_BANDS == (0, 10_000, 100_000, 1_000_000)


def test_numeric_animation_queue_is_ordered_paged_and_read_only(tmp_path):
    store = UsageStore(tmp_path / "events.sqlite3")
    assert store.recent_events() == [] and not store.path.exists()
    for i in range(70):
        store.record(report(100 + i, 10))
    # A burst is never silently truncated: every event can play once, in order.
    events = store.recent_events()
    assert [event["seq"] for event in events] == list(range(1, 71))
    page = store.recent_events(0, limit=64)
    assert len(page) == 64 and page[-1]["seq"] == 64
    assert [event["seq"] for event in store.recent_events(page[-1]["seq"])] == list(range(65, 71))
    assert store.recent_events(69)[0]["reduced_tokens"] == 159
    assert store.recent_events(70) == []
    assert store.summary()["preparations"] == 70
