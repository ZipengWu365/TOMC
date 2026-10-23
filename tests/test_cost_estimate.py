import json

from tomc.cost_estimate import dollars, explanation, input_value, load_pricing


def test_cached_and_uncached_reference_are_not_interchangeable(tmp_path):
    config = tmp_path/"pricing.json"
    config.write_text(json.dumps({"model": "claude-opus-5-5"}), encoding="utf-8")
    base = load_pricing(config)
    assert input_value(100_000, base) == 0.4
    config.write_text(json.dumps({"model": "claude-opus-5-5", "input_mode": "cached"}), encoding="utf-8")
    assert input_value(100_000, load_pricing(config)) == 0.02
    assert input_value(-100_000, base) == -0.4
    assert dollars(input_value(1, base)) == "<$0.0001"
    assert dollars(input_value(648, base)) == "$0.0026"


def test_unknown_or_broken_model_never_fabricates_price(tmp_path):
    config = tmp_path/"pricing.json"
    for raw in ('{"model":"unknown"}', 'invalid', 'null'):
        config.write_text(raw, encoding="utf-8")
        assert load_pricing(config) is None
    assert input_value(1000, None) is None
    assert dollars(None) == "—"


def test_english_explanation_preserves_rate_and_separates_unknown_original_notes():
    from types import SimpleNamespace

    pricing = {"model": "fixture", "host": "codex", "mode": "cached", "rate": 0.2,
               "condition": "Standard · 全球基础价", "evidence": "手选参考模型",
               "assumption": "这是用户自己写的说明", "verified_at": "2026-10-22"}
    english = explanation(pricing, SimpleNamespace(code="en"))
    assert "cache read $0.2/million tokens" in english
    assert "Global base rate" in english
    assert "increase cost" in english
    standard, original = english.split("\n\nOriginal stored notes (not translated)\n")
    assert "这是用户自己写的说明" not in standard
    assert "这是用户自己写的说明" in original
    assert input_value(1000, pricing) == 0.0002
    assert "缓存读取" in explanation(pricing)
    assert "unconfirmed" in explanation(None, "en")


def test_display_helper_language_does_not_change_numeric_semantics():
    from tomc.pet_growth import growth_state
    from tomc.quota import quota_windows
    from tomc.usage_widget import display_values

    summary = {"last_preparation": {"input_tokens": 4000, "usable": True},
               "by_counter": [{"reduced_tokens": -10, "input_tokens": 20,
                               "memory_tokens": 30, "reduction_percent": -50}], "preparations": 2}
    zh, en = growth_state(summary), growth_state(summary, "en")
    assert {k: v for k, v in zh.items() if k != "hint"} == {k: v for k, v in en.items() if k != "hint"}
    assert "6,000 more" in en["hint"]
    zh, en = display_values(summary), display_values(summary, "en")
    assert {k: v for k, v in zh.items() if k != "detail"} == {k: v for k, v in en.items() if k != "detail"}
    limits = {"rateLimits": {"primary": {"usedPercent": 35, "windowDurationMins": 300}}}
    assert quota_windows(limits, "en")[0] == {**quota_windows(limits)[0], "period": "5 hours"}
