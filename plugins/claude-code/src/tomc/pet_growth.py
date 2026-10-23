"""Cosmetic companion progression from estimated context reduction, not model power."""

STAGES = (
    (0, "TOMC", "tomc-expression-1.png"),
    (10_000, "TOMC", "tomc-expression-2.png"),
    (100_000, "TOMC", "tomc-expression-3.png"),
    (1_000_000, "TOMC", "tomc-expression-4.png"),
)


def growth_state(summary: dict) -> dict:
    groups = summary.get("growth", [])
    if len(groups) > 1:
        return {"level": 1, "name": "TOMC", "asset": STAGES[0][2],
                "progress": 0, "hint": "不同计数器不合并成长值", "mixed": True,
                "opacity": 0.35, "notes": 2}
    group = groups[0] if groups else {}
    peak = max(0, group.get("peak_net_tokens", 0))
    net = group.get("net_tokens", 0)
    index = max(i for i, stage in enumerate(STAGES) if peak >= stage[0])
    floor, name, asset = STAGES[index]
    target = STAGES[index + 1][0] if index + 1 < len(STAGES) else None
    progress = 1 if target is None else max(0, min(1, (net - floor) / (target - floor)))
    # Materialization never flickers or reverses; text is rendered separately at full opacity.
    solid = (0.35, 0.58, 0.82, 1.0)
    opacity = solid[index] if target is None else (
        solid[index] + (solid[index+1]-solid[index]) * (peak-floor)/(target-floor)
    )
    milestones = (1000, 3000, 6000, 10000, 18000, 30000, 50000, 70000, 100000,
                  150000, 220000, 320000, 450000, 600000, 800000, 1000000)
    notes = 2 + sum(peak >= point for point in milestones)
    hint = "最终形态已解锁" if target is None else f"再积累 {max(0, target-net):,} 可进化"
    return {"level": index + 1, "name": name, "asset": asset,
            "progress": progress, "hint": hint, "mixed": False,
            "net_tokens": net, "peak_net_tokens": peak, "next_at": target,
            "opacity": round(opacity, 5), "notes": notes}
