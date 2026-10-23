"""Four cosmetic forms chosen by this context's input length, never lifetime growth."""

STAGES = (
    (0, "TOMC", "tomc-expression-1.png"),
    (10_000, "TOMC", "tomc-expression-2.png"),
    (100_000, "TOMC", "tomc-expression-3.png"),
    (1_000_000, "TOMC", "tomc-expression-4.png"),
)


def request_stage(input_tokens: int | None, language=None) -> dict:
    """Map one prepared-context input estimate to a form and its animation.

    These are context-text tokens before preparation, not the reduction or the
    request envelope (tools, instructions and other JSON overhead). Unknown
    lengths use a neutral first form. A shorter next input may use a lower form.
    """
    english = getattr(language, "code", language) == "en"
    known = isinstance(input_tokens, int) and not isinstance(input_tokens, bool) and input_tokens >= 0
    tokens = input_tokens if known else 0
    index = max(i for i, stage in enumerate(STAGES) if tokens >= stage[0])
    floor, name, asset = STAGES[index]
    target = STAGES[index + 1][0] if index + 1 < len(STAGES) else None
    progress = 1 if target is None else (tokens - floor) / (target - floor)
    solid = (0.35, 0.58, 0.82, 1.0)
    opacity = solid[index] if target is None else (
        solid[index] + (solid[index+1] - solid[index]) * progress
    )
    # The amount of decorative paper follows this input, not an earned reward.
    paper_points = (1000, 3000, 6000, 10000, 18000, 30000, 50000, 70000, 100000,
                    150000, 220000, 320000, 450000, 600000, 800000, 1000000)
    notes = 2 + sum(tokens >= point for point in paper_points)
    if not known:
        hint = ("This context's input length is unknown; showing the default first form. "
                "Stages start at 0 / 10,000 / 100,000 / 1,000,000 estimated input tokens."
                if english else
                "本次上下文输入长度未知，显示默认第一档；按 0 / 10,000 / 100,000 / 1,000,000 估算输入 tokens 分档。")
    elif english:
        hint = f"This context: {tokens:,} estimated input tokens · stage {index+1}. "
        hint += (f"{target-tokens:,} more input tokens in this request to reach the next stage ({target:,})."
                 if target is not None else
                 "Highest length band (1,000,000+). The form follows each request's input length.")
    else:
        hint = f"本次上下文输入 {tokens:,} 估算 tokens · 第 {index+1} 档。"
        hint += (f"本次输入距下一档（{target:,}）还差 {target-tokens:,} tokens。"
                 if target is not None else
                 "最高长度档（≥ 1,000,000）；形态随每次输入长度变化。")
    return {"level": index + 1, "name": name, "asset": asset,
            "progress": progress, "hint": hint, "mixed": False,
            "input_tokens": input_tokens if known else None, "length_known": known,
            "next_at": target, "opacity": round(opacity, 5), "notes": notes,
            "stage_basis": "request_input_length", "thresholds": [stage[0] for stage in STAGES]}


def growth_state(summary: dict, language=None) -> dict:
    """Compatibility entry point: use only the latest usable preparation input.

    Historical totals and peaks remain accounting data. They neither choose nor
    permanently unlock a form. Gateway envelope estimates cannot stand in for
    context length; ordinary preparation counters already count that context.
    """
    latest = summary.get("last_preparation")
    latest = latest if isinstance(latest, dict) and latest.get("usable") is True else {}
    length = latest.get("context_input_tokens")
    counter = str(latest.get("counter") or "")
    envelope_counter = any(marker in counter.lower() for marker in ("request-json", "entire-payload"))
    if length is None and not envelope_counter:
        length = latest.get("input_tokens")
    state = request_stage(length, language)
    return {**state, "counter": latest.get("counter") if state["length_known"] else None}
