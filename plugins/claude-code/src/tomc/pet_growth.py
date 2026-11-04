"""Four cosmetic forms earned by cumulative tokens saved; a form, once reached, is kept."""

STAGES = (
    (0, "TOMC", "tomc-expression-1.png"),
    (100_000, "TOMC", "tomc-expression-2.png"),
    (1_000_000, "TOMC", "tomc-expression-3.png"),
    (10_000_000, "TOMC", "tomc-expression-4.png"),
)

# Context-length bands for the analysis chart and the paper in one animation.
# They describe one request and never choose the cat's form.
LENGTH_BANDS = (0, 10_000, 100_000, 1_000_000)


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def paper_notes(input_tokens) -> int:
    """Decorative paper for one animation: follows that context's length, not an earned reward."""
    paper_points = (
        1000,
        3000,
        6000,
        10000,
        18000,
        30000,
        50000,
        70000,
        100000,
        150000,
        220000,
        320000,
        450000,
        600000,
        800000,
        1000000,
    )
    tokens = input_tokens if _count(input_tokens) else 0
    return 2 + sum(tokens >= point for point in paper_points)


def saved_stage(saved_tokens, language=None) -> dict:
    """Map cumulative estimated tokens saved to a form.

    The total is a context estimate, not a bill. Unknown totals use the neutral
    first form and show no level.
    """
    english = getattr(language, "code", language) == "en"
    known = _count(saved_tokens)
    tokens = saved_tokens if known else 0
    index = max(i for i, stage in enumerate(STAGES) if tokens >= stage[0])
    floor, name, asset = STAGES[index]
    target = STAGES[index + 1][0] if index + 1 < len(STAGES) else None
    progress = 1 if target is None else (tokens - floor) / (target - floor)
    solid = (0.35, 0.58, 0.82, 1.0)
    opacity = (
        solid[index]
        if target is None
        else (solid[index] + (solid[index + 1] - solid[index]) * progress)
    )
    if not known:
        hint = (
            "Total saving not available yet; showing the first form. "
            "TOMC grows at about 100K / 1M / 10M tokens saved in total."
            if english
            else "还没有累计节省记录，显示第一阶段。累计少发约 10 万 / 100 万 / 1000 万 tokens 时长大。"
        )
    elif english:
        hint = f"≈ {tokens:,} tokens saved in total (estimate) · stage {index + 1}. "
        hint += (
            f"{target - tokens:,} more to stage {index + 2} ({target:,})."
            if target is not None
            else "Fully grown (10,000,000+)."
        )
    else:
        hint = f"累计少发 ≈ {tokens:,} tokens（估算）· 第 {index + 1} 阶段。"
        hint += (
            f"再省 {target - tokens:,} 到第 {index + 2} 阶段（{target:,}）。"
            if target is not None
            else "已经长到最大（≥ 10,000,000）。"
        )
    return {
        "level": index + 1,
        "name": name,
        "asset": asset,
        "progress": progress,
        "hint": hint,
        "mixed": False,
        "saved_tokens": saved_tokens if known else None,
        "known": known,
        "next_at": target,
        "opacity": round(opacity, 5),
        "notes": 2,
        "stage_basis": "cumulative_saved_tokens",
        "thresholds": [stage[0] for stage in STAGES],
    }


def lifetime_saved(summary: dict):
    """The largest earned net saving of any one counter, or None without records.

    Counters are never added together: an estimate and a tokenizer count the
    same text differently. The stored peak keeps a form once it is reached,
    even when a later preparation adds context.
    """
    rows = [row for row in (summary or {}).get("growth") or () if isinstance(row, dict)]
    values = [
        max(0, row.get("peak_net_tokens") or 0, row.get("net_tokens") or 0)
        for row in rows
        if isinstance(row.get("peak_net_tokens") or 0, int)
        and isinstance(row.get("net_tokens") or 0, int)
    ]
    return max(values) if values else None


def growth_state(summary: dict, language=None) -> dict:
    """The cat's form for this database: cumulative saving across all time."""
    return saved_stage(lifetime_saved(summary), language)


def context_length(report):
    """This preparation's context length before compression, or None.

    Gateway envelope estimates (tools, instructions, JSON) cannot stand in for
    context length; ordinary preparation counters already count that context.
    """
    report = report if isinstance(report, dict) and report.get("usable") is True else {}
    length = report.get("context_input_tokens")
    counter = str(report.get("counter") or "").lower()
    if length is None and not any(m in counter for m in ("request-json", "entire-payload")):
        length = report.get("input_tokens")
    return length if _count(length) else None


def request_stage(report, base=None, language=None) -> dict:
    """The earned form ``base`` playing one preparation.

    The form never changes with one request; only the paper follows its length.
    """
    stage = dict(base) if base else saved_stage(None, language)
    length = context_length(report)
    stage.update(
        input_tokens=length,
        length_known=length is not None,
        notes=paper_notes(length),
        counter=report.get("counter") if length is not None and isinstance(report, dict) else None,
    )
    return stage
