"""Traffic badges must remain dated aggregates, not invented users or lifetime totals."""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("traffic", ROOT / "scripts/update_traffic.py")
traffic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(traffic)
NOW = datetime(2026, 10, 16, 6, 23, tzinfo=timezone.utc)


@pytest.fixture
def site(tmp_path):
    for name in ("README.md", "README_zh.md"):
        (tmp_path / name).write_text(
            "<!-- traffic-status:start -->old<!-- traffic-status:end -->\n", encoding="utf-8"
        )
    return tmp_path


def payload():
    return {
        "count": 8,
        "uniques": 3,
        "clones": [
            {"timestamp": "2026-10-14T00:00:00Z", "count": 4, "uniques": 3},
            {"timestamp": "2026-10-15T00:00:00Z", "count": 4, "uniques": 3},
        ],
    }


def test_window_uniques_are_not_sum_of_daily_uniques(site):
    snapshot = traffic.api_snapshot(payload(), NOW)
    assert snapshot["uniques"] == 3
    traffic.write_snapshot(snapshot, site)
    badge = (site / "assets/traffic/unique-cloners.svg").read_text()
    assert "Unique cloners | 14d: 3" in badge
    ElementTree.fromstring(badge)
    assert "updated 2026-10-16 UTC" in (site / "README.md").read_text()


def test_same_day_refresh_replaces_snapshot_without_adding_counts(site):
    snapshot = traffic.api_snapshot(payload(), NOW)
    traffic.write_snapshot(snapshot, site)
    traffic.write_snapshot(snapshot, site)
    assert len(list((site / "metrics/traffic/snapshots").glob("*.json"))) == 1
    assert json.loads((site / "metrics/traffic/latest.json").read_text())["count"] == 8


def test_empty_api_window_is_a_valid_zero(site):
    snapshot = traffic.api_snapshot({"count": 0, "uniques": 0, "clones": []}, NOW)
    traffic.write_snapshot(snapshot, site)
    assert json.loads((site / "metrics/traffic/latest.json").read_text())["count"] == 0


@pytest.mark.parametrize("value", [-1, True, "8", 1.5])
def test_invalid_counts_rejected_before_writing(value, site):
    data = payload()
    data["count"] = value
    with pytest.raises(ValueError):
        traffic.api_snapshot(data, NOW)
    assert not (site / "metrics").exists()


def test_mismatched_total_and_duplicate_days_rejected():
    data = payload()
    data["count"] = 10
    with pytest.raises(ValueError):
        traffic.api_snapshot(data, NOW)
    data = payload()
    data["clones"][1]["timestamp"] = data["clones"][0]["timestamp"]
    with pytest.raises(ValueError):
        traffic.api_snapshot(data, NOW)


def test_http_failure_preserves_snapshot_and_does_not_log_credentials(site, monkeypatch, capsys):
    traffic.write_snapshot(traffic.api_snapshot(payload(), NOW), site)
    before = (site / "metrics/traffic/latest.json").read_bytes()
    monkeypatch.setattr(traffic, "ROOT", site)
    monkeypatch.setenv("GH_TRAFFIC_TOKEN", "private-test-value")

    def denied(*args):
        raise HTTPError("https://api.github.com", 403, "private-test-value", {}, None)

    monkeypatch.setattr(traffic, "fetch_snapshot", denied)
    assert traffic.main([]) == 1
    assert (site / "metrics/traffic/latest.json").read_bytes() == before
    assert "private-test-value" not in capsys.readouterr().out


def test_missing_token_reports_unconfigured(site, monkeypatch):
    monkeypatch.setattr(traffic, "ROOT", site)
    monkeypatch.delenv("GH_TRAFFIC_TOKEN", raising=False)
    assert traffic.main([]) == 2
    assert not (site / "metrics").exists()


def test_screenshot_render_retains_original_date_and_source(site):
    snapshot = {
        "repository": traffic.REPOSITORY,
        "source": "owner_screenshot",
        "observed_at": "2026-10-16",
        "count": 648,
        "uniques": 194,
    }
    traffic.write_snapshot(snapshot, site)
    assert "2026-10-16 (owner screenshot)" in (site / "README.md").read_text()
    assert "截图记录" in (site / "README_zh.md").read_text(encoding="utf-8")


def cumulative(site):
    return json.loads((site / "metrics/traffic/cumulative.json").read_text())


def test_overlapping_windows_replace_days_and_keep_expired_days(site):
    traffic.write_snapshot(traffic.api_snapshot(payload(), NOW), site)
    newer = {
        "count": 11,
        "uniques": 3,
        "clones": [
            {"timestamp": "2026-10-15T00:00:00Z", "count": 6, "uniques": 3},
            {"timestamp": "2026-10-16T00:00:00Z", "count": 5, "uniques": 2},
        ],
    }
    snapshot = traffic.api_snapshot(newer, datetime(2026, 10, 17, tzinfo=timezone.utc))
    traffic.write_snapshot(snapshot, site)
    assert cumulative(site)["count"] == 15  # 4 + revised 6 + new 5; not 8 + 11.
    traffic.write_snapshot(snapshot, site)
    assert cumulative(site)["count"] == 15
    assert "Clones (total): 15" in (site / "assets/traffic/clones.svg").read_text()
    # Re-rendering an older snapshot cannot roll back a newer daily observation.
    traffic.write_snapshot(traffic.api_snapshot(payload(), NOW), site)
    assert cumulative(site)["count"] == 15


def test_api_correction_can_lower_count_without_double_counting_screenshot(site):
    traffic.write_snapshot(
        {
            "repository": traffic.REPOSITORY,
            "source": "owner_screenshot",
            "observed_at": "2026-10-16",
            "count": 648,
            "uniques": 194,
        },
        site,
    )
    traffic.write_snapshot(traffic.api_snapshot(payload(), NOW), site)
    assert cumulative(site)["count"] == 8
    revised = payload()
    revised["count"] = 7
    revised["clones"][0]["count"] = 3
    traffic.write_snapshot(traffic.api_snapshot(revised, NOW), site)
    assert cumulative(site)["count"] == 7


def test_empty_later_window_preserves_archived_total(site):
    traffic.write_snapshot(traffic.api_snapshot(payload(), NOW), site)
    traffic.write_snapshot(
        traffic.api_snapshot(
            {"count": 0, "uniques": 0, "clones": []}, datetime(2026, 11, 10, tzinfo=timezone.utc)
        ),
        site,
    )
    assert cumulative(site)["count"] == 8
    assert len(cumulative(site)["daily"]) == 2
