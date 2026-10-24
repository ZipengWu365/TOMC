import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tomc.pricing_catalog import all_rates
from tomc.request_activity import RequestActivity
from tomc.savings import load_detected, model_rate, savings_report
from tomc.usage import UsageStore

VERIFIED = "2026-10-18T00:00:00+00:00"


def rate(provider, model, variant, input_rate, cached, label=None):
    return {
        "provider": provider,
        "model": model,
        "label": label or model,
        "variant": variant,
        "input": input_rate,
        "cached": cached,
        "output": input_rate * 5,
    }


CATALOG = {
    "schema": 1,
    "providers": {
        "openai": {
            "verified_at": VERIFIED,
            "rates": [
                rate("openai", "gpt-6-astra", "standard-short", 10.0, 1.0),
                rate("openai", "gpt-6-astra", "standard-long", 20.0, 2.0),
                rate("openai", "gpt-6-astra", "batch-short", 5.0, 0.5),
                rate("openai", "gpt-5.5-pro", "standard-short", 30.0, None),
            ],
        },
        "anthropic": {
            "verified_at": VERIFIED,
            "rates": [
                rate("anthropic", "claude-opus-5-5", "standard", 4.0, 0.2, "Claude Opus 5.5")
            ],
        },
        "cursor": {
            "verified_at": VERIFIED,
            "rates": [
                rate("cursor", "claude-opus-5-5", "listed", 9.0, 0.9, "Claude Opus 5.5"),
                rate("cursor", "composer-2", "listed", 1.25, 0.13, "Composer 2"),
            ],
        },
        "deepseek": {
            "verified_at": VERIFIED,
            "rates": [
                rate("deepseek", "deepseek-flash", "peak", 0.3, 0.006),
                rate("deepseek", "deepseek-flash", "off-peak", 0.15, 0.003),
            ],
        },
    },
}
RATES = list(all_rates(CATALOG))
REFERENCE = {"model": "ref-model", "label": "Reference", "rate": 3.0, "mode": "input"}


def compiled(path, request_id, host, model, before, after):
    activity = RequestActivity(path)
    activity.start(request_id, host, "session")
    activity.finish(
        request_id,
        state="prepared",
        before_tokens=before,
        after_tokens=after,
        context_input_tokens=1000,
        model=model,
    )
    UsageStore(path).record(
        {
            "request_id": request_id,
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": "regex-request-json-v1 (estimate)",
            "context_input_tokens": 1000,
        }
    )


def daily_only(path, days_ago, saved):
    """An aggregate written before per-request events existed."""
    day = str(datetime.now(timezone.utc).date() - timedelta(days=days_ago))
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO context_usage_daily VALUES (?,?,?,?,?,?,?)",
            (day, "regex-v1 (estimate)", 1, 1, 0, saved * 2, saved),
        )


@pytest.mark.parametrize(
    "model,tokens,mode,expected",
    [
        ("gpt-6-astra", 50_000, "input", ("openai", 10.0)),
        ("gpt-6-astra", 300_000, "input", ("openai", 20.0)),
        ("gpt-6-astra", 50_000, "cached", ("openai", 1.0)),
        ("openai/gpt-6-astra", None, "input", ("openai", 10.0)),
        # The model's own provider wins over a reseller listing.
        ("claude-opus-5-5[1m]", 400_000, "input", ("anthropic", 4.0)),
        ("claude-opus-5-5-20261001", None, "input", ("anthropic", 4.0)),
        ("Claude-Opus-5-5", None, "input", ("anthropic", 4.0)),
        ("composer-2", None, "input", ("cursor", 1.25)),
        ("deepseek-flash", None, "input", ("deepseek", 0.15)),
    ],
)
def test_each_model_uses_its_own_listed_rate_and_context_band(model, tokens, mode, expected):
    priced = model_rate(model, request_tokens=tokens, mode=mode, rates=RATES)
    assert (priced["provider"], priced["rate"]) == expected


@pytest.mark.parametrize("model", ["mystery-1", "", None, 42])
def test_unknown_or_invalid_models_have_no_rate(model):
    assert model_rate(model, rates=RATES) is None


def test_a_missing_cached_rate_is_not_replaced_by_another_price():
    assert model_rate("gpt-5.5-pro", mode="cached", rates=RATES) is None
    assert model_rate("gpt-5.5-pro", mode="input", rates=RATES)["rate"] == 30.0


def test_savings_are_valued_per_request_model_and_band(tmp_path):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "gpt-6-astra", 100_000, 60_000)
    compiled(path, "b", "codex", "gpt-6-astra", 400_000, 300_000)
    compiled(path, "c", "claude", "claude-opus-5-5", 50_000, 40_000)
    report = savings_report(path, "all", catalog=CATALOG, reference=REFERENCE, detected={})
    assert report["tokens_saved"] == 150_000
    assert report["preparations"] == 3
    assert report["reduction_percent"] == round(100 * 150_000 / 550_000, 2)
    # 40,000 at $10 + 100,000 at the >272K rate of $20 + 10,000 at $4, per million.
    assert report["money"] == pytest.approx(0.40 + 2.00 + 0.04)
    assert report["unpriced_tokens"] == 0
    first, second = report["models"]
    assert first["model"] == "gpt-6-astra" and first["tokens_saved"] == 140_000
    assert first["rates"] == [10.0, 20.0] and first["bases"] == ["request"]
    assert first["hosts"] == ["codex"] and first["preparations"] == 2
    assert second["label"] == "Claude Opus 5.5" and second["money"] == pytest.approx(0.04)
    assert len(report["daily"]) == 14
    assert report["daily"][-1] == {
        "day": str(datetime.now(timezone.utc).date()),
        "tokens_saved": 150_000,
    }


def test_older_records_fall_back_to_detected_then_reference_then_unpriced(tmp_path):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "codex-old", "codex", None, 20_000, 10_000)
    compiled(path, "claude-unknown", "claude", "mystery-1", 9_000, 8_000)
    UsageStore(path).record(
        {
            "usable": True,
            "input_tokens": 3_000,
            "memory_tokens": 1_000,
            "reduced_tokens": 2_000,
            "counter": "regex-v1 (estimate)",
        }
    )
    daily_only(path, 3, 5_000)
    detected = {"codex": "gpt-6-astra"}
    report = savings_report(path, "all", catalog=CATALOG, reference=REFERENCE, detected=detected)
    models = {model["model"]: model for model in report["models"]}
    assert models["gpt-6-astra"]["bases"] == ["detected"]
    assert models["gpt-6-astra"]["money"] == pytest.approx(0.10)
    # Unknown request model, tool-path preparation and older aggregate use the reference.
    assert models["ref-model"]["tokens_saved"] == 1_000 + 2_000 + 5_000
    assert models["ref-model"]["bases"] == ["reference"]
    assert report["tokens_saved"] == 18_000
    unpriced = savings_report(path, "all", catalog=CATALOG, reference=None, detected=detected)
    assert unpriced["money"] == pytest.approx(0.10)
    assert unpriced["unpriced_tokens"] == 8_000
    assert unpriced["models"][-1]["model"] is None
    assert unpriced["models"][-1]["money"] is None


def test_periods_and_trend_window(tmp_path):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "today", "codex", "gpt-6-astra", 2_000, 1_000)
    daily_only(path, 3, 5_000)
    daily_only(path, 30, 7_000)
    kwargs = {"catalog": CATALOG, "reference": REFERENCE, "detected": {}}
    assert savings_report(path, "today", **kwargs)["tokens_saved"] == 1_000
    assert savings_report(path, "7d", **kwargs)["tokens_saved"] == 6_000
    report = savings_report(path, "all", **kwargs)
    assert report["tokens_saved"] == 13_000
    trend = {day["day"]: day["tokens_saved"] for day in report["daily"]}
    today = datetime.now(timezone.utc).date()
    assert trend[str(today - timedelta(days=3))] == 5_000
    assert str(today - timedelta(days=30)) not in trend
    assert sum(trend.values()) == 6_000


def test_cached_mode_and_negative_savings(tmp_path):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "gpt-6-astra", 100_000, 60_000)
    compiled(path, "b", "codex", "gpt-6-astra", 1_000, 1_500)
    cached = {**REFERENCE, "mode": "cached"}
    report = savings_report(path, "all", catalog=CATALOG, reference=cached, detected={})
    assert report["mode"] == "cached"
    assert report["tokens_saved"] == 39_500
    assert report["money"] == pytest.approx(39_500 * 1.0 / 1_000_000)


def test_missing_or_legacy_databases_read_without_writing(tmp_path):
    missing = savings_report(tmp_path / "absent.sqlite3", "7d", catalog=CATALOG)
    assert missing["tokens_saved"] == 0 and missing["money"] is None
    assert len(missing["daily"]) == 14 and not missing["models"]
    legacy = tmp_path / "legacy.sqlite3"
    UsageStore(legacy).record(
        {
            "usable": True,
            "input_tokens": 300,
            "memory_tokens": 100,
            "reduced_tokens": 200,
            "counter": "regex-v1 (estimate)",
        }
    )
    with sqlite3.connect(legacy) as db:
        db.execute(
            "CREATE TABLE tomc_request_activity (request_id TEXT PRIMARY KEY, host TEXT NOT NULL)"
        )
    before = legacy.read_bytes()
    report = savings_report(legacy, "all", catalog=CATALOG, reference=REFERENCE, detected={})
    assert report["tokens_saved"] == 200
    assert report["money"] == pytest.approx(200 * 3.0 / 1_000_000)
    assert legacy.read_bytes() == before


@pytest.mark.parametrize("options", [{"period": "month"}, {"days": 0}, {"days": True}])
def test_invalid_report_options(tmp_path, options):
    with pytest.raises(ValueError):
        savings_report(tmp_path / "x.sqlite3", **{"period": "all", **options})


def test_detected_models_file(tmp_path):
    path = tmp_path / "detected_models.json"
    path.write_text(
        json.dumps(
            {
                "hosts": {
                    "codex": {"model": "gpt-6-astra"},
                    "cursor": {"model": None},
                    "broken": "x",
                }
            }
        ),
        encoding="utf-8",
    )
    assert load_detected(path) == {"codex": "gpt-6-astra"}
    path.write_text("not json", encoding="utf-8")
    assert load_detected(path) == {}
    assert load_detected(tmp_path / "absent.json") == {}
