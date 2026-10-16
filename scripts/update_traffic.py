"""Fetch GitHub clone aggregates and render dated README badges (standard library only)."""

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
    assets = root / "assets" / "traffic"
    data = root / "metrics" / "traffic"
    assets.mkdir(parents=True, exist_ok=True)
    (data / "snapshots").mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    # One snapshot per UTC date and source. No addition of overlapping 14-day totals.
    (data / "snapshots" / f"{day}-{source}.json").write_text(encoded, encoding="utf-8")
    (data / "latest.json").write_text(encoded, encoding="utf-8")
    for name, label, value, color in (
        ("clones", "Clones | 14d snapshot", f"{count:,}", "#176b47"),
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
            snapshot = fetch_snapshot(token, datetime.now(timezone.utc))
        write_snapshot(snapshot)
    except HTTPError as exc:
        print(f"Traffic API returned HTTP {exc.code}; existing snapshot retained.")
        return 1
    except (OSError, ValueError, KeyError, TypeError, URLError):
        print("Traffic refresh failed; no successful collection is claimed. Check saved files.")
        return 1
    print("Dated traffic snapshot and badges updated; no user-level tracking collected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
