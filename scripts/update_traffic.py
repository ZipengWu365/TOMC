"""Archive daily GitHub traffic and render cumulative clone and Star badges."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "ZipengWu365/TOMC"


def integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("Traffic counts must be nonnegative integers")
    return value


def api_snapshot(payload: dict, now: datetime) -> dict:
    """Use API window uniques directly; never sum daily uniques or overlapping windows."""
    count, uniques = integer(payload["count"]), integer(payload["uniques"])
    if uniques > count:
        raise ValueError("Unique cloners exceed clone count")
    days = []
    seen = set()
    for row in payload["clones"]:
        timestamp = datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        if timestamp.time().isoformat() != "00:00:00" or row["timestamp"] in seen:
            raise ValueError("Expected distinct UTC day buckets")
        seen.add(row["timestamp"])
        daily_count, daily_uniques = integer(row["count"]), integer(row["uniques"])
        if daily_uniques > daily_count:
            raise ValueError("Daily unique cloners exceed count")
        days.append({"timestamp": row["timestamp"], "count": daily_count, "uniques": daily_uniques})
    if sum(day["count"] for day in days) != count:
        raise ValueError("Daily counts do not match the API total")
    return {
        "schema": "tomc-clone-snapshot-v1",
        "repository": REPOSITORY,
        "source": "github_traffic_api",
        "observed_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "window": "last_14_days_at_fetch",
        "count": count,
        "uniques": uniques,
        "daily": sorted(days, key=lambda day: day["timestamp"]),
    }


def fetch_snapshot(token: str, now: datetime) -> dict:
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/traffic/clones?per=day",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TOMC-traffic-badges",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return api_snapshot(payload, now)


def fetch_stars(token: str, now: datetime) -> dict:
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TOMC-traffic-badges",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload["full_name"] != REPOSITORY:
        raise ValueError("Unexpected repository")
    return {
        "repository": REPOSITORY,
        "source": "github_repository_api",
        "observed_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "count": integer(payload["stargazers_count"]),
    }


def cumulative_snapshot(snapshot: dict, root: Path) -> dict:
    """Each UTC date contributes once; newer observations replace earlier counts."""
    records = []
    for path in (root / "metrics/traffic/snapshots").glob("*.json"):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    records.append(snapshot)
    daily = {}
    observed_at = None
    for record in sorted(records, key=lambda item: item["observed_at"]):
        if record["source"] != "github_traffic_api":
            continue  # Screenshot totals overlap and have no daily breakdown.
        if record["repository"] != REPOSITORY:
            raise ValueError("Unexpected repository in archive")
        checked = api_snapshot(
            {"count": record["count"], "uniques": record["uniques"], "clones": record["daily"]},
            datetime.fromisoformat(record["observed_at"]),
        )
        for row in checked["daily"]:
            daily[row["timestamp"]] = row["count"]
        observed_at = checked["observed_at"]
    if observed_at is None:
        raise ValueError("Cumulative counts require daily API records")
    return {
        "schema": "tomc-cumulative-clones-v1",
        "repository": REPOSITORY,
        "source": "archived_github_traffic_api_daily_counts",
        "observed_at": observed_at,
        "first_recorded_date": min(daily)[:10] if daily else None,
        "last_recorded_date": max(daily)[:10] if daily else None,
        "count": sum(daily.values()),
        "daily": [{"date": stamp[:10], "count": count} for stamp, count in sorted(daily.items())],
        "scope": "Sum of recorded UTC dates, each counted once; unavailable history is excluded.",
    }


def badge(label: str, value: str, color: str) -> str:
    left, right = max(72, len(label) * 7 + 20), max(48, len(value) * 8 + 20)
    width = left + right
    title = escape(f"{label}: {value}", quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" '
        f'role="img" aria-label="{title}">\n<title>{title}</title>\n'
        f'<rect width="{width}" height="28" rx="4" fill="#24292f"/>\n'
        f'<path d="M{left} 0h{right - 4}q4 0 4 4v20q0 4-4 4h-{right - 4}z" '
        f'fill="{color}"/>\n'
        '<g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" '
        'font-size="11">\n'
        f'<text x="{left / 2}" y="18">{escape(label)}</text>\n'
        f'<text x="{left + right / 2}" y="18">{escape(value)}</text>\n'
        "</g>\n</svg>\n"
    )


def write_snapshot(snapshot: dict, root: Path = ROOT) -> None:
    count, uniques = integer(snapshot["count"]), integer(snapshot["uniques"])
    if uniques > count or snapshot["repository"] != REPOSITORY:
        raise ValueError("Invalid repository or clone totals")
    day = snapshot["observed_at"][:10]
    datetime.strptime(day, "%Y-%m-%d")
    source = snapshot["source"]
    if source not in {"owner_screenshot", "github_traffic_api"}:
        raise ValueError("Unknown snapshot source")
    cumulative = cumulative_snapshot(snapshot, root) if source == "github_traffic_api" else None
    assets = root / "assets" / "traffic"
    data = root / "metrics" / "traffic"
    assets.mkdir(parents=True, exist_ok=True)
    (data / "snapshots").mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    # One snapshot per UTC date and source. No addition of overlapping 14-day totals.
    (data / "snapshots" / f"{day}-{source}.json").write_text(encoded, encoding="utf-8")
    (data / "latest.json").write_text(encoded, encoding="utf-8")
    if cumulative is not None:
        (data / "cumulative.json").write_text(
            json.dumps(cumulative, indent=2) + "\n", encoding="utf-8"
        )
    stars_path = data / "stars.json"
    if stars_path.exists():
        stars = json.loads(stars_path.read_text(encoding="utf-8"))
        (assets / "stars.svg").write_text(
            badge("Stars", f"{integer(stars['count']):,}", "#946c00"), encoding="utf-8"
        )
    for name, label, value, color in (
        (
            "clones-total",
            "Clones (total)" if cumulative else "Clones | 14d snapshot",
            f"{cumulative['count'] if cumulative else count:,}",
            "#176b47",
        ),
        ("unique-cloners", "Unique cloners | 14d", f"{uniques:,}", "#0969a8"),
        ("updated", "Traffic snapshot", day, "#57606a"),
    ):
        (assets / f"{name}.svg").write_text(badge(label, value, color), encoding="utf-8")
    for filename, zh in (("README.md", False), ("README_zh.md", True)):
        path = root / filename
        text = path.read_text(encoding="utf-8")
        method = "截图记录" if zh else "owner screenshot"
        if source == "github_traffic_api":
            method = "GitHub API" if zh else "GitHub API"
        caption = (
            f"流量快照：{day}（{method}）；14 天滚动统计，不等于安装量或活跃用户数。"
            if zh
            else f"Traffic snapshot: {day} ({method}); rolling 14-day counts, "
            "not installations or active users."
        )
        if cumulative is not None:
            since = cumulative["first_recorded_date"] or day
            caption = (
                f"累计克隆 · 自 {since} 起记录 · 更新于 {day} UTC。"
                if zh
                else f"Cumulative clones · recorded since {since} · updated {day} UTC."
            )
        replacement = (
            "<!-- traffic-status:start -->\n"
            f'  <p>{caption} <a href="docs/traffic_metrics.md">'
            + ("统计口径与更新" if zh else "Method and updates")
            + "</a></p>\n<!-- traffic-status:end -->"
        )
        text, matches = re.subn(
            r"<!-- traffic-status:start -->.*?<!-- traffic-status:end -->",
            replacement,
            text,
            flags=re.DOTALL,
        )
        if matches != 1:
            raise ValueError(f"Expected one traffic status block in {filename}")
        path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--render-only", action="store_true", help="Render the saved dated snapshot."
    )
    args = parser.parse_args(argv)
    try:
        if args.render_only:
            snapshot = json.loads(
                (ROOT / "metrics/traffic/latest.json").read_text(encoding="utf-8")
            )
        else:
            token = os.environ.get("GH_TRAFFIC_TOKEN", "")
            if not token:
                print("Traffic collection not configured: add the TRAFFIC_TOKEN Actions secret.")
                return 2
            now = datetime.now(timezone.utc)
            snapshot = fetch_snapshot(token, now)
            stars = fetch_stars(token, now)
            (ROOT / "metrics/traffic/stars.json").write_text(
                json.dumps(stars, indent=2) + "\n", encoding="utf-8"
            )
        write_snapshot(snapshot, ROOT)
    except HTTPError as exc:
        print(f"Traffic API returned HTTP {exc.code}; existing snapshot retained.")
        return 1
    except (OSError, ValueError, KeyError, TypeError, URLError):
        print("Traffic refresh failed; no successful collection is claimed. Check saved files.")
        return 1
    print("Cumulative daily clone ledger and dated badges updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
