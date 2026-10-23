"""Allowance and preparation reduction have different denominators."""

from tomc.quota import context_percent, percent_text, quota_windows


def test_quota_prefers_buckets_and_never_turns_missing_into_zero():
    payload = {"rateLimits": {"primary": {"usedPercent": 1}},
               "rateLimitsByLimitId": {"codex": {"primary": {
                   "usedPercent": 32, "windowDurationMins": 10080}},
                   "another": {"primary": {"usedPercent": None}}}}
    windows = quota_windows(payload)
    assert len(windows) == 1
    assert windows[0]["remaining"] == 68 and windows[0]["period"] == "本周"
    for value in (None, {}, {"rateLimitsByLimitId": {}}, {"rateLimits": {"primary": None}}):
        assert quota_windows(value) == []
    assert quota_windows({"rateLimits": {"primary": {"usedPercent": float("nan")}}}) == []


def test_quota_windows_are_kept_separate_and_clamped():
    result = quota_windows({"rateLimits": {
        "primary": {"usedPercent": 105, "windowDurationMins": 300},
        "secondary": {"usedPercent": -4, "windowDurationMins": 10080}}})
    assert [(w["period"], w["remaining"]) for w in result] == [("5小时", 0), ("本周", 100)]


def test_percent_uses_total_input_not_average_call_reductions():
    # First call saves 60%, second expands 100%; weighted total saves 45.45%.
    assert percent_text(context_percent(100+10, 40+20)) == "45.5%"
    assert context_percent(100, 300) == -200
    assert percent_text(context_percent(0, 0)) == "—"
    assert percent_text(context_percent(100000, 1)) == ">99.9%"
