"""Reference input value, not observed billing or environmental savings."""

import json
import math
import re
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


def is_english(language=None):
    return getattr(language, "code", language) == "en"


def reference_note(value, language=None):
    """Translate known stored display notes; label any unrecognized original text."""
    value = str(value or "")
    if not is_english(language):
        return value
    replacements = {
        "手选参考模型；未读取实际调用的模型、缓存和档位": "Manually selected reference; actual request model, cache and tier are unverified",
        "用户选定的参考模型；不代表每次实际调用": "User-selected reference model; not the model used for every request",
        "Codex config.toml 的默认模型；可能被当前会话覆盖": "Default model in Codex config.toml; a session may override it",
        "未读取到 Codex 默认模型": "Codex default model was not found",
        "运行中的 Claude Code 会话最近一条 assistant 的模型元数据；不代表下一次调用": "Model metadata from the latest assistant entry in an active Claude Code session; not a prediction of the next request",
        "Claude Code 当前模型未确认（无活动记录或多个模型）": "Current Claude Code model is unconfirmed (no active record or multiple models)",
        "未接入 Cursor 的逐请求模型记录；Auto 不猜测，需手选参考模型": "Per-request Cursor model data is unavailable; select a reference model for Auto",
        "未缓存、标准服务、基础上下文档位；未读取实际请求缓存/档位": "Uncached input, standard service, base context tier; actual cache and tier are unverified",
        "按所选档位折算；未确认实际发送量、缓存命中或账单": "Calculated at the selected tier; actual transmitted input, cache hits and billing are unverified",
        "手选计价条件，不代表实际请求计费": "Manually selected pricing assumptions, not actual request charges",
        "手选参考模型": "Manually selected reference model", "其他 / API": "Other / API",
        "Cursor 公布基础价": "Cursor listed base rate", "第三方模型；基础上下文档位，长上下文需另核费率": "Third-party model; base context tier; check long-context rates separately",
        "额外用量": "Additional usage", "全球基础价": "Global base rate", "峰时": "Peak hours", "谷时": "Off-peak hours",
        "输入": "input", " 按选择的时段折算历史，不自动回溯。": " Historical estimates use the selected period; no automatic historical rate lookup.",
        " · 检查于 ": " · Checked at ",
    }
    for before, after in replacements.items():
        value = value.replace(before, after)
    if re.search(r"[\u3400-\u9fff]", value):
        return "Original stored note (not translated): " + value
    return value


def explanation(pricing, language=None):
    if is_english(language):
        if not pricing:
            return ("Model or rate is unconfirmed; no monetary estimate is shown. Choose a reference model in Models & estimates. "
                    "Auto does not borrow another model's rate.")
        originals = []

        def note(field, fallback):
            value = reference_note(pricing.get(field, fallback), language)
            if value.startswith("Original stored note (not translated): "):
                originals.append(f"{field}: {pricing.get(field, fallback)}")
                return f"{field.capitalize()}: see original stored note below."
            return value

        kind = "cache read" if pricing["mode"] == "cached" else "uncached input"
        freshness = "last sync succeeded" if pricing.get("sync_status") == "live" else "offline or older snapshot; check the date"
        body = (f"{reference_note(pricing.get('host', 'Reference'), language)} · {pricing['model']}\n"
                f"{note('evidence', 'Manually selected reference model')}\n"
                f"{note('condition', 'Standard')} · {kind} ${pricing['rate']:g}/million tokens\n"
                f"Verified {pricing.get('verified_at', 'unknown')} · {freshness}\n"
                f"{note('assumption', '')}\n{note('schedule', '')}\n"
                "Reference value = estimated input-token reduction × selected rate, assuming the text would otherwise be sent once at that rate. "
                "Totals apply this rate to all preparation records; they are not actual charges summed across requests. "
                "Input sizes are text estimates, not confirmed transmitted amounts. Repeated preparations count separately. "
                "Tool/request overhead, output and repeated sends are excluded. Changes in caching can erase the benefit or increase cost. "
                "Cursor uses base reference rates without team fees, legacy Max markups, regional premiums or plan discounts. "
                "Subscription fees do not fall directly as a result.\n" + pricing.get("source", ""))
        if originals:
            body += "\n\nOriginal stored notes (not translated)\n" + "\n".join(originals)
        return body
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
