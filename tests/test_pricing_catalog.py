import json
from pathlib import Path

import pytest

from tomc.cost_estimate import input_value, load_pricing
from tomc.model_detection import detect
from tomc.pricing_catalog import SOURCES, all_rates, parse, sync

FIXTURES = Path(__file__).parent / "fixtures/pricing"


def fixture(url):
    name = next(k for k, v in SOURCES.items() if v == url)
    return (FIXTURES / f"{name}.txt").read_text("utf-8")


def test_live_rates_distinguish_cache_tier_band_and_cursor(tmp_path):
    catalog = sync(tmp_path / "prices.json", fixture)
    assert all(p["status"] == "live" for p in catalog["providers"].values())
    rates = {r["key"]: r for r in all_rates(catalog)}
    assert rates["openai:gpt-6-astra:standard-short"]["input"] == 10
    assert rates["openai:gpt-6-astra:standard-long"]["input"] == 20
    assert rates["openai:gpt-6-astra:batch-short"]["input"] == 5
    assert rates["anthropic:claude-haiku-5-5:standard"]["input"] == 0.1
    assert rates["anthropic:claude-haiku-5-5:standard-long"]["input"] == 0.5
    assert rates["deepseek:deepseek-flash:peak"]["cached"] == 0.006
    assert rates["deepseek:deepseek-flash:off-peak"]["input"] == 0.15
    assert rates["cursor:composer-2-5:listed"]["input"] == 0.5
    assert rates["cursor:composer-2-5-fast:listed"]["input"] == 3
    config = tmp_path / "settings.json"
    config.write_text(
        json.dumps({"provider": "cursor", "model": "composer-2-5", "variant": "listed"})
    )
    assert input_value(100_000, load_pricing(config, catalog)) == 0.05
    config.write_text(json.dumps({"provider": "cursor", "model": "auto", "variant": "listed"}))
    assert load_pricing(config, catalog) is None


def test_failure_retains_verification_and_rates_per_provider(tmp_path):
    path = tmp_path / "prices.json"
    before = sync(path, fixture)

    def failure(url):
        if url == SOURCES["openai"]:
            return "Schema changed, no monetary table"
        if url == SOURCES["cursor"]:
            raise OSError("offline")
        return fixture(url)

    after = sync(path, failure)
    for name in ("openai", "cursor"):
        assert after["providers"][name]["status"] == "stale"
        assert after["providers"][name]["verified_at"] == before["providers"][name]["verified_at"]
        assert after["providers"][name]["rates"] == before["providers"][name]["rates"]
    assert after["providers"]["deepseek"]["status"] == "live"


def test_reject_changed_thresholds_and_bad_prices():
    raw = fixture(SOURCES["openai"])
    with pytest.raises(ValueError):
        parse("openai", raw.replace("≤272K input", "≤400K input"))
    with pytest.raises(ValueError):
        parse("openai", raw.replace("$10.00", "unknown", 1))
    for rate in (float("nan"), float("inf"), -1, True, "4"):
        assert input_value(1000, {"rate": rate}) is None


def test_detection_does_not_guess_aliases_or_multiple_active_models(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex/config.toml").write_text('model = "gpt-6-astra"\nmodel_provider = "custom"')
    project = tmp_path / ".claude/projects/example"
    project.mkdir(parents=True)
    ids = ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"]
    for identifier, model in zip(ids, ("claude-opus-5-5", "claude-sonnet-5-5")):
        (project / f"{identifier}.jsonl").write_text(
            json.dumps({"type": "assistant", "message": {"model": model}})
        )
    first = detect(tmp_path, ids[:1])["hosts"]
    assert first["codex"]["model"] == "gpt-6-astra"
    assert first["codex"]["provider"] == "custom"
    assert first["claude"]["model"] == "claude-opus-5-5"
    assert first["cursor"]["model"] is None
    assert detect(tmp_path, ids)["hosts"]["claude"]["model"] is None
