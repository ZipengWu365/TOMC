"""Plain words for request status and reason codes. Display strings only, no Qt.

Producers (the gateway, request adapters, automatic chat and the paper kernel)
record short machine codes. The desktop panels show these sentences instead,
and never the code itself: an unknown code reads "Sent unchanged" and the code
goes only into a tooltip.
"""

from __future__ import annotations

UNKNOWN = ("已原样发送", "Sent unchanged")

# Codes not listed here are shown as UNKNOWN. "助手" means Codex or Claude Code.
REASONS = {
    "session_disabled": ("本会话已关闭 TOMC", "TOMC is off for this chat"),
    "global_disabled": ("TOMC 已全部暂停", "TOMC is paused"),
    "disabled": ("TOMC 已暂停", "TOMC is paused"),
    "identity_required": ("还不知道是哪个对话", "Chat not identified yet"),
    "identity_unavailable": ("还不知道是哪个对话", "Chat not identified yet"),
    "unassociated_session": ("还不知道是哪个对话", "Chat not identified yet"),
    "no_current_user_task": ("这次没有新的提问", "No new question in this request"),
    "missing_task": ("这次没有新的提问", "No new question in this request"),
    "no_readable_old_history": ("没有能读的较早内容", "No earlier history to read"),
    "no_eligible_old_history": ("没有可压缩的较早内容", "No earlier history to compress"),
    "insufficient_old_history": ("较早的内容还不够多", "Not enough earlier history yet"),
    "empty_memory": ("没有需要保留的较早内容", "Nothing earlier worth keeping"),
    "history_not_supported_by_compiler": (
        "这段历史的格式还不支持，原样发送",
        "History format not supported yet; sent unchanged",
    ),
    "history_fits_memory_budget": ("对话还短，不需要压缩", "Short chat; no compression needed"),
    "history_below_threshold": ("对话还短，不需要压缩", "Short chat; no compression needed"),
    "short_history": ("对话还短，不需要压缩", "Short chat; no compression needed"),
    "below_char_threshold": ("内容还短，不需要压缩", "Short content; no compression needed"),
    "no_complete_memory_fits": (
        "预算放不下完整的记录，原样发送",
        "Budget too small for a complete record; sent unchanged",
    ),
    "protected_context_exceeds_budget": (
        "必须保留的内容已超出预算，原样发送",
        "Required content is over budget; sent unchanged",
    ),
    "request_budget_not_met": (
        "压缩后仍超出预算，原样发送",
        "Still over budget after compression; sent unchanged",
    ),
    "invalid_adapter_options": (
        "处理设置不可用，原样发送",
        "Processing settings unavailable; sent unchanged",
    ),
    "unsupported_prompt_options": (
        "这次请求带有特殊设置，原样发送",
        "Request has special settings; sent unchanged",
    ),
    "model_budget_unavailable": (
        "不知道这个模型的上下文上限，原样发送",
        "Model's context limit unknown; sent unchanged",
    ),
    "model_window_boundary_backoff": (
        "接近模型的上下文上限，这次先不压缩",
        "Near the model's context limit; skipped this time",
    ),
    "native_context_management": ("由助手自己管理上下文", "The assistant manages this context"),
    "auxiliary_request": ("助手的辅助请求", "Assistant's helper request"),
    "non_main_request": ("助手的辅助请求", "Assistant's helper request"),
    "subagent_request": ("子代理的请求，原样发送", "Subagent request; sent unchanged"),
    "missing_messages": ("请求里没有对话消息", "No chat messages in the request"),
    "stored_prefix_unreadable": (
        "之前的上下文暂时读不到，原样发送",
        "Saved context unreadable; sent unchanged",
    ),
    "original_prefix_changed": (
        "较早的内容有改动，原样发送",
        "Earlier content changed; sent unchanged",
    ),
    "prefix_store_unavailable": (
        "上下文存储暂时不可用，原样发送",
        "Context storage unavailable; sent unchanged",
    ),
    "unsupported_endpoint": ("这类请求原样发送", "This request type is sent unchanged"),
    "unsupported_input": ("保留原来的输入格式", "Original input format kept"),
    "unsupported_non_json_payload": (
        "请求不是 JSON，原样发送",
        "Request is not JSON; sent unchanged",
    ),
    "unsupported_request_encoding_or_json": (
        "保留原来的编码和内容",
        "Original encoding and content kept",
    ),
    "invalid_tool_pairing": ("工具调用和结果要保持成对", "Tool calls and results stay together"),
    "incomplete_tool_pairing": (
        "工具调用还没有结果，原样发送",
        "A tool call has no result yet; sent unchanged",
    ),
    "unsupported_tool_protocol": ("保留原来的工具格式", "Original tool format kept"),
    "unsupported_message_fields": ("保留原来的消息字段", "Original message fields kept"),
    "unsupported_message_role": ("保留原来的消息角色", "Original message roles kept"),
    "unsupported_content": ("保留原来的内容格式", "Original content format kept"),
    "unsupported_content_type": ("保留原来的内容类型", "Original content types kept"),
    "unsupported_thinking_fields": (
        "保留原来的推理内容和签名",
        "Original reasoning and signatures kept",
    ),
    "unsupported_text_fields": ("保留原来的文本字段", "Original text fields kept"),
    "unsupported_tool_use": ("保留原来的工具调用", "Original tool calls kept"),
    "unsupported_tool_result": ("保留原来的工具结果", "Original tool results kept"),
    "unsupported_tool_result_content": (
        "保留原来的工具结果内容",
        "Original tool result content kept",
    ),
    "unsupported_message_content": ("保留原来的内容格式", "Original content format kept"),
    "unsupported_message_schema": ("保留原来的消息格式", "Original message format kept"),
    "unsupported_native_state": (
        "含有助手自己的上下文状态，原样发送",
        "Contains the assistant's own context state; sent unchanged",
    ),
    "nonshrinking": ("处理后没有变短", "Not shorter after processing"),
    "no_request_size_reduction": ("处理后没有变短", "Not shorter after processing"),
    "already_optimized_input": ("已经是 TOMC 整理过的内容", "Already prepared by TOMC"),
    "compilation_failed": ("准备失败，原样发送", "Preparation failed; sent unchanged"),
    "preparation_failed": ("准备失败，原样发送", "Preparation failed; sent unchanged"),
    "native_compaction_active": ("助手正在整理上下文", "The assistant is compacting context"),
    "native_compaction_completed": ("助手刚整理完上下文", "The assistant just compacted context"),
    "native_compaction_cooldown": (
        "助手刚整理过上下文，先观察一下",
        "Waiting after the assistant's own compaction",
    ),
    "native_compaction": ("保留助手自己的上下文整理", "The assistant's own compaction kept"),
    "native_compaction_reset": (
        "助手已整理上下文，旧记录已清除",
        "The assistant compacted context; old mapping cleared",
    ),
    "native_compaction_state": (
        "助手自己管理（含不透明的整理状态），TOMC 本次未压缩",
        "Managed by the assistant (opaque compaction state); TOMC did not compress this request",
    ),
    "host_compaction_request": (
        "助手自己的压缩请求，TOMC 不参与",
        "The assistant's own compaction request; TOMC not involved",
    ),
    "native_or_unknown_request": (
        "助手的整理或辅助请求，原样发送",
        "Assistant compaction or helper request; sent unchanged",
    ),
    "unknown_request_metadata": (
        "看不懂这次请求的附加信息，原样发送",
        "Unrecognized request metadata; sent unchanged",
    ),
    "explicit_cache_control": ("保留缓存边界", "Cache boundaries kept"),
    "cache_control": ("保留缓存边界", "Cache boundaries kept"),
    "previous_response_id": ("保留服务端的对话上下文", "Server-side conversation kept"),
    "server_side_or_incremental_history": (
        "保留服务端的对话上下文",
        "Server-side conversation kept",
    ),
    "protected_system_history": (
        "保留助手的系统指令和工具定义",
        "Assistant instructions and tool definitions kept",
    ),
    "retained_thinking_requires_original_prefix": (
        "推理签名需要原文，原样发送",
        "Signed reasoning needs the original; sent unchanged",
    ),
    "upstream_failed": ("模型服务返回失败", "The model service returned an error"),
    "upstream_unavailable": ("连不上模型服务", "Could not reach the model service"),
    "transport_failed": ("连接中断", "Connection interrupted"),
    "upstream_transport_failed": (
        "和模型服务的连接中断",
        "Connection to the model service dropped",
    ),
    "client_disconnected": (
        "助手取消了请求或断开了连接",
        "The assistant cancelled or disconnected",
    ),
}


def _t(language, zh, en, **values):
    if hasattr(language, "tr"):
        return language.tr(zh, en, **values)
    text = en if getattr(language, "code", language) == "en" else zh
    return text.format(**values) if values else text


def reason_text(code, language=None):
    """Plain words for a reason code; None when the code is unknown or empty."""
    pair = REASONS.get(code) if isinstance(code, str) else None
    return _t(language, *pair) if pair else None


def reason_or_unchanged(code, language=None):
    """Plain words, or "Sent unchanged" for a code nobody mapped yet."""
    return reason_text(code, language) or _t(language, *UNKNOWN)


def code_tooltip(code, language=None):
    """The raw code, for a tooltip only. Empty when there is none."""
    if not isinstance(code, str) or not code:
        return ""
    return _t(language, "状态代码：{code}", "Status code: {code}", code=code)
