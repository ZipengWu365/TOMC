"""Read-only Codex allowance display; never infer allowance savings from tokens."""

import math
import os
import shutil
from pathlib import Path


def codex_executable():
    explicit = os.environ.get("TOMC_CODEX_PATH")
    if explicit:
        path = Path(explicit)
        return str(path) if path.is_file() else None
    command = shutil.which("codex")
    if not command:
        return None
    path = Path(command)
    if os.name != "nt" or path.suffix.lower() == ".exe":
        return str(path)
    # Resolve the official npm installation's native binary, without a shell.
    package = path.parent / "node_modules" / "@openai" / "codex"
    candidates = sorted(package.glob("node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"))
    return str(candidates[0]) if candidates else None


def quota_windows(payload, language=None):
    """Missing != zero; prefer multi-bucket data and don't combine quotas."""
    if not isinstance(payload, dict):
        return []
    english = getattr(language, "code", language) == "en"
    buckets = payload.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict):
        legacy = payload.get("rateLimits")
        buckets = {legacy.get("limitId") or "codex": legacy} if isinstance(legacy, dict) else {}
    windows = []
    for key, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        for slot in ("primary", "secondary"):
            window = bucket.get(slot)
            if not isinstance(window, dict):
                continue
            used, minutes = window.get("usedPercent"), window.get("windowDurationMins")
            if isinstance(used, bool) or not isinstance(used, (float, int)) or not math.isfinite(used):
                continue
            names = {300: "5 hours", 10080: "This week", 1440: "Today"} if english else {300: "5小时", 10080: "本周", 1440: "今日"}
            duration = names.get(minutes)
            if duration is None:
                duration = ((f"{minutes} minutes" if english else f"{minutes}分钟") if isinstance(minutes, (int, float))
                            else "Current window" if english else "当前周期")
            windows.append({"bucket": key, "period": duration,
                            "remaining": max(0, min(100, 100-used)),
                            "resets_at": window.get("resetsAt")})
    return windows


def context_percent(before, after):
    """Ratio of aggregate sums, not an average of per-call percentages."""
    return 100 * (before-after) / before if before and before > 0 else None


def percent_text(percent):
    if percent is None:
        return "—"
    value = abs(percent)
    # Do not round near-total reduction into a claim of exactly 100%.
    if 99.95 <= value < 100:
        return ">99.9%"
    return f"{value:.1f}%"
