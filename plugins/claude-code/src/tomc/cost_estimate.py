"""Reference input value, not observed billing or environmental savings."""

import json
import math
from pathlib import Path

from .pricing_catalog import all_rates

SETTINGS = Path.home() / ".tomc/pricing.json"


def load_pricing(path=None, catalog=None):
    try:
        settings = json.loads((path or SETTINGS).read_text("utf-8"))
        model = settings.get("model")
        mode = settings.get("input_mode", "input")
        provider = settings.get("provider", "anthropic")
        variant = settings.get("variant", "standard")
        row = next((r for r in all_rates(catalog) if r["model"] == model and
                    r["provider"] == provider and r["variant"] == variant), None)
        if not row or mode not in ("input", "cached") or row.get(mode) is None:
            return None
        rate = row[mode]
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 0:
            return None
        return {**row, "mode": mode, "rate": rate, "host": settings.get("host", "claude"),
                "evidence": settings.get("evidence", "手选参考模型"),
                "assumption": settings.get("assumption", "手选计价条件，不代表实际请求计费")}
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None


def input_value(delta, pricing):
    if pricing is None or isinstance(delta, bool) or not isinstance(delta, (int, float)):
        return None
    rate = pricing.get("rate")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate < 0:
        return None
    value = delta*rate/1_000_000
    return value if math.isfinite(value) else None


def dollars(value):
    if value is None:
        return "—"
    magnitude = abs(value)
    if 0 < magnitude < 0.0001:
        return "<$0.0001"
    return f"${magnitude:,.4f}" if magnitude < 1 else f"${magnitude:,.2f}"


def explanation(pricing):
    if not pricing:
        return "模型或费率未确认，暂不估算金额。请在「模型与估价」选择参考模型。Auto 不套用其他模型单价。"
    kind = "缓存读取" if pricing["mode"] == "cached" else "未缓存输入"
    freshness = "上次同步成功" if pricing.get("sync_status") == "live" else "离线/旧快照，请核对日期"
    return (f"{pricing.get('host', '参考')} · {pricing['model']}\n"
            f"{pricing.get('evidence', '手选参考模型')}\n"
            f"{pricing.get('condition', 'Standard')} · {kind} ${pricing['rate']:g}/百万 tokens\n"
            f"核验 {pricing.get('verified_at', '未知')} · {freshness}\n"
            f"{pricing.get('assumption', '')}\n{pricing.get('schedule', '')}\n"
            "金额=估算减少的输入 tokens × 所选单价；假设这些文本原本会按该单价发送一次。"
            "累计是全部准备记录按此单价折算，不是各次调用的实付合计。"
            "输入量来自文本估算，未确认真正发送。重复准备会分别累计。"
            "不含工具/请求开销、输出或重复发送；缓存改变也可能抵消收益。"
            "Cursor 为基础参考价，不含团队附加费、旧版 Max 加价、地区溢价或套餐折扣。"
            "订阅月费不会因此直接降低。\n" + pricing.get("source", ""))
