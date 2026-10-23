"""Local context browser and session controls; no model or host UI automation."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .conversation_names import clean, folder, resolve
from .conversations import group_conversations
from .cost_estimate import explanation, input_value, load_pricing
from .request_activity import RequestActivity
from .savings import request_savings, savings_report
from .savings_qt import (
    ElidedLabel,
    SavingsChart,
    compact_tokens,
    discard,
    local_time,
    money_text,
    total_tokens,
)
from .ui_language import UiLanguage


def _tr(language, zh, en, **values):
    if hasattr(language, "tr"):
        return language.tr(zh, en, **values)
    return (en if language == "en" else zh).format(**values)


STYLE = """
QWidget { color: #443B35; font-family: 'Microsoft YaHei UI'; font-size: 12px; }
QDialog, QWidget#notice { background: #FFFCF7; }
QLabel { background: transparent; }
QLabel#title { font-size: 20px; font-weight: 600; color: #345743; }
QLabel#muted { color: #796D60; font-size: 11px; }
QLabel#status { background: #EEF2EA; border-radius: 7px; padding: 9px; }
QPushButton { background: #F1EDE4; border: 1px solid #E3DED3; border-radius: 7px; padding: 7px 12px; }
QPushButton:hover { background: #E4ECE5; border-color: #AABBAE; }
QPushButton:focus { border-color: #507461; }
QPushButton:disabled { color: #A49D92; background: #F5F2EC; }
QPushButton#primary { background: #507461; color: white; border-color: #507461; }
QPushButton#primary:hover { background: #3E6250; }
QPushButton#primary:disabled { background: #F5F2EC; color: #A49D92; border-color: #E3DED3; }
QLineEdit, QComboBox, QPlainTextEdit, QListWidget {
    background: #FFFFFF; border: 1px solid #E3DED3; border-radius: 6px; padding: 7px;
    selection-background-color: #DFE9DE; selection-color: #294735;
}
QListWidget::item { padding: 10px 7px; border-bottom: 1px solid #F1EDE4; }
QListWidget::item:selected { background: #DFE9DE; color: #294735; border-radius: 5px; }
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 9px 14px; margin-bottom: 7px; color: #796D60; }
QTabBar::tab:selected { color: #345743; border-bottom: 2px solid #507461; }
QCheckBox { spacing: 7px; }
QSplitter::handle { background: #F1EDE4; width: 1px; }
"""


def text_label(text="", *, muted=False, wrap=True):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if muted:
        item.setObjectName("muted")
    return item


def host_label(host, language=None):
    return {
        "codex": "Codex",
        "claude_code": "Claude Code",
        "claude-code": "Claude Code",
        "claude": "Claude Code",
    }.get(host, host or _tr(language, "未关联会话", "Unlinked session"))


def short_date(value, language=None):
    return (
        str(value or _tr(language, "时间未知", "Unknown time"))
        .replace("T", " ")
        .replace("+00:00", "Z")[:19]
    )


def request_activity_text(record, language=None):
    """Describe observed request work without claiming unmeasured cost savings."""

    def t(zh, en, **values):
        return _tr(language, zh, en, **values)

    if not record:
        return t(
            "自动请求：尚未观察到代理请求", "Automatic requests: no gateway request observed yet"
        )
    reasons = {
        "session_disabled": ("本会话已关闭 TOMC", "TOMC is disabled for this session"),
        "global_disabled": ("全局处理已暂停", "Processing is paused globally"),
        "disabled": ("TOMC 已暂停", "TOMC is paused"),
        "identity_required": ("会话身份待关联", "Session identity is not linked"),
        "no_current_user_task": ("本次请求没有新的用户任务", "This request has no new user task"),
        "no_readable_old_history": ("没有可读取的较早历史", "No readable earlier history"),
        "history_not_supported_by_compiler": (
            "保留暂不支持处理的历史内容",
            "History format retained without compression",
        ),
        "no_complete_memory_fits": (
            "预算不足以保留完整上下文记录",
            "The budget cannot fit a complete context record",
        ),
        "invalid_adapter_options": (
            "处理设置不可用，保留原文",
            "Processing settings unavailable; original content retained",
        ),
        "native_context_management": ("由宿主管理上下文", "Context is managed by the host"),
        "auxiliary_request": ("宿主辅助请求", "Host auxiliary request"),
        "subagent_request": ("子代理请求，保留原文", "Subagent request; original content retained"),
        "unassociated_session": ("会话身份待关联", "Session identity is not linked"),
        "missing_messages": ("请求中没有对话消息", "The request contains no conversation messages"),
        "stored_prefix_unreadable": (
            "已有上下文暂时无法读取，保留原文",
            "Saved context unavailable; original content retained",
        ),
        "original_prefix_changed": (
            "较早上下文已变化，保留原文",
            "Earlier context changed; original content retained",
        ),
        "prefix_store_unavailable": (
            "上下文存储暂时不可用，保留原文",
            "Context storage unavailable; original content retained",
        ),
        "unsupported_endpoint": ("此类请求保持原样", "This request type is forwarded unchanged"),
        "unsupported_input": ("保留原有输入格式", "Original input format retained"),
        "invalid_tool_pairing": (
            "工具调用与结果需保持完整",
            "Tool calls and results must remain together",
        ),
        "unsupported_tool_protocol": ("保留原有工具协议", "Original tool protocol retained"),
        "unsupported_message_fields": ("保留原有消息字段", "Original message fields retained"),
        "unsupported_message_role": ("保留原有消息角色", "Original message roles retained"),
        "unsupported_content": ("保留原有内容格式", "Original content format retained"),
        "unsupported_content_type": ("保留原有内容类型", "Original content types retained"),
        "unsupported_thinking_fields": (
            "保留原有推理内容与签名",
            "Original reasoning content and signatures retained",
        ),
        "unsupported_text_fields": ("保留原有文本字段", "Original text fields retained"),
        "unsupported_tool_use": ("保留原有工具调用", "Original tool calls retained"),
        "unsupported_tool_result": ("保留原有工具结果", "Original tool results retained"),
        "unsupported_tool_result_content": (
            "保留原有工具结果内容",
            "Original tool result content retained",
        ),
        "no_eligible_old_history": ("没有可处理的较早历史", "No eligible earlier history"),
        "history_fits_memory_budget": ("短上下文无需压缩", "Short context needs no compression"),
        "nonshrinking": ("处理后未变短", "Processing did not shorten the request"),
        "already_optimized_input": ("已是 TOMC 上下文", "The input is already TOMC context"),
        "compilation_failed": (
            "准备失败，保留原文",
            "Preparation failed; original content retained",
        ),
        "native_compaction_active": ("宿主正在整理上下文", "The host is compacting context"),
        "native_compaction_completed": ("宿主刚完成整理", "The host just completed compaction"),
        "native_compaction_cooldown": (
            "宿主整理后的观察期",
            "Observation period after host compaction",
        ),
        "unsupported_message_content": ("保留原有内容协议", "Original content protocol retained"),
        "unsupported_message_schema": ("保留原有消息协议", "Original message protocol retained"),
        "explicit_cache_control": ("保留缓存边界", "Cache boundaries retained"),
        "cache_control": ("保留缓存边界", "Cache boundaries retained"),
        "previous_response_id": (
            "保留服务端会话上下文",
            "Server-side conversation context retained",
        ),
        "identity_unavailable": ("会话身份待关联", "Session identity is not linked"),
        "non_main_request": ("宿主辅助请求", "Host auxiliary request"),
        "native_compaction": ("保留宿主原生上下文整理", "Host native compaction retained"),
        "preparation_failed": (
            "准备失败，保留原文",
            "Preparation failed; original content retained",
        ),
        "upstream_failed": ("上游返回失败", "Upstream request failed"),
        "transport_failed": ("连接或响应传输中断", "Connection or response stream interrupted"),
        "unsupported_request_encoding_or_json": (
            "保留原有编码与内容",
            "Original encoding and content retained",
        ),
        "history_below_threshold": ("短上下文无需压缩", "Short context needs no compression"),
        "insufficient_old_history": ("没有足够的较早历史", "Not enough earlier history"),
        "protected_system_history": (
            "保留宿主系统指令与工具定义",
            "Host system instructions and tool definitions retained",
        ),
        "retained_thinking_requires_original_prefix": (
            "保留推理签名所需的原始前缀",
            "Original prefix retained for signed reasoning",
        ),
        "no_request_size_reduction": ("处理后未变短", "Processing did not shorten the request"),
        "server_side_or_incremental_history": (
            "保留服务端会话上下文",
            "Server-side conversation context retained",
        ),
        "native_or_unknown_request": (
            "宿主整理或辅助请求，保留原文",
            "Host compaction or auxiliary request; original content retained",
        ),
        "native_compaction_reset": (
            "宿主已整理上下文，旧映射已清除",
            "Host context compacted; old prefix mapping cleared",
        ),
        "host_compaction_request": (
            "宿主自身的压缩请求，TOMC 不参与",
            "The host's own compaction request; TOMC not involved",
        ),
        "native_compaction_state": (
            "宿主原生管理：含不透明压缩状态，TOMC 本次未压缩",
            "Host-managed: opaque compaction state present; TOMC did not compress this request",
        ),
        "unknown_request_metadata": (
            "宿主请求元数据无法识别，保留原文",
            "Unrecognized host request metadata; original content retained",
        ),
        "upstream_transport_failed": (
            "上游连接或响应中断",
            "Upstream connection or response interrupted",
        ),
    }
    state = record.get("state")
    if record.get("stale"):
        return t(
            "自动请求：准备状态已中断，等待新的请求事件",
            "Automatic requests: preparation interrupted; waiting for a new request",
        )
    if state == "preparing":
        return t("正在检查 / 准备请求上下文", "Checking / preparing request context")
    if state == "prepared":
        return t("上下文已准备，等待上游转发", "Context prepared; waiting for upstream forwarding")
    if state == "forwarded":
        if record.get("reason") == "disabled_compatible_replay":
            return t(
                "已转发已有签名兼容上下文 · 本会话关闭，不进行新的压缩",
                "Existing context forwarded to preserve signatures · Session disabled; no new compression",
            )
        if record.get("reason") == "replayed_prefix":
            return t("已复用并转发已有上下文", "Existing context reused and forwarded")
        return t("已观察到处理后请求转发", "A processed request was observed being forwarded")
    reason = record.get("reason")
    if reason == "client_disconnected":
        return t("请求已由宿主取消或断开", "Request cancelled or disconnected by the host")
    detail = (
        t(*reasons[reason])
        if reason in reasons
        else (reason or t("未提供原因", "No reason provided"))
    )
    facts = protocol_detail_text(record.get("protocol_detail"), language)
    if facts:
        detail = f"{detail} · {facts}"
    if state == "passthrough":
        status = (
            t("请求已原样转发", "Request forwarded unchanged")
            if record.get("sent")
            else t("请求将原样转发", "Request will be forwarded unchanged")
        )
        return f"{status} · {detail}"
    return t("请求失败 · {detail}", "Request failed · {detail}", detail=detail)


def protocol_detail_text(detail, language=None):
    """Short structural facts the host declared; never request content."""
    if not isinstance(detail, dict):
        return ""
    parts = []
    trigger = {
        "manual": ("手动", "manual"),
        "auto": ("自动", "automatic"),
        "reactive": ("超长后触发", "after an overlong request"),
    }.get(detail.get("compaction_trigger"))
    if trigger:
        parts.append(_tr(language, *trigger))
    phase = {
        "pre_turn": ("回合开始前", "before the turn"),
        "mid_turn": ("回合进行中", "mid-turn"),
        "standalone_turn": ("单独整理", "standalone"),
    }.get(detail.get("compaction_phase"))
    if phase:
        parts.append(_tr(language, *phase))
    if detail.get("endpoint") == "responses_compact":
        parts.append(_tr(language, "独立压缩端点", "standalone compact endpoint"))
    if type(detail.get("window")) is int:
        parts.append(_tr(language, "压缩代次 {n}", "compaction generation {n}", n=detail["window"]))
    if type(detail.get("compaction_items")) is int:
        parts.append(
            _tr(
                language,
                "{n} 个不透明状态项",
                "{n} opaque state item(s)",
                n=detail["compaction_items"],
            )
        )
    if detail.get("agent") == "subagent":
        parts.append(_tr(language, "子代理", "subagent"))
    return _tr(language, "，", ", ").join(parts)


def integration_snapshot():
    try:
        from .integration_status import get_integration_status

        status = get_integration_status()
        mode = status.get("mode", {})
        port = mode.get("gateway_port")
        if (
            mode.get("id") == "automatic_request_gateway"
            and type(port) is int
            and 1024 <= port <= 65535
        ):
            mode["gateway_service"] = "offline"
            try:
                opener = build_opener(ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{port}/health", timeout=0.25) as response:
                    data = json.loads(response.read(4096))
                if (
                    isinstance(data, dict)
                    and data.get("service") == "tomc-gateway"
                    and data.get("ready") is True
                ):
                    mode["gateway_service"] = "online"
            except (OSError, ValueError):
                pass
        return status
    except (ImportError, OSError, ValueError):
        return {
            name: {"label": "状态暂不可读", "runtime_verified": False}
            for name in ("codex", "claude_code")
        }


class SessionNotice(QWidget):
    """Nonmodal notice bound to the displayed session, never desktop focus."""

    changed = Signal()

    def __init__(self, sessions, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.sessions = sessions
        self.language = getattr(parent, "language", None) or UiLanguage(sessions.path, self)
        self.target = None
        self.target_enabled = True
        self._shown_session = None
        self._error = None
        self.setObjectName("notice")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            STYLE + "QWidget#notice { border: 1px solid #E3DED3; border-radius: 12px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.heading = text_label()
        self.heading.setStyleSheet("font-weight: 600; font-size: 13px; color: #345743;")
        self.detail = text_label(muted=True)
        layout.addWidget(self.heading)
        layout.addWidget(self.detail)
        actions = QHBoxLayout()
        self.keep_button = QPushButton()
        self.keep_button.clicked.connect(self.hide)
        self.toggle_button = QPushButton()
        self.toggle_button.clicked.connect(self.toggle_session)
        actions.addWidget(self.keep_button)
        actions.addWidget(self.toggle_button)
        layout.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.language.changed.connect(self.retranslate)
        self.retranslate()

    def t(self, zh, en, **values):
        return self.language.tr(zh, en, **values)

    def retranslate(self, *_):
        self.setWindowTitle(self.t("TOMC 会话状态", "TOMC session status"))
        self.setFixedWidth(390 if self.language.code == "en" else 330)
        self.heading.setText(
            self.t(
                "本会话 TOMC 默认开启，要关闭吗？", "TOMC is enabled for this session. Turn it off?"
            )
            if self.target_enabled
            else self.t("本会话 TOMC 已关闭", "TOMC is disabled for this session")
        )
        self.keep_button.setText(
            self.t("保持开启", "Keep enabled")
            if self.target_enabled
            else self.t("保持关闭", "Keep disabled")
        )
        self.toggle_button.setText(
            self.t("关闭本会话", "Disable session")
            if self.target_enabled
            else self.t("重新开启本会话", "Re-enable session")
        )
        session = self._shown_session
        if session:
            title = session.get("title") or session["session_id"]
            short_title = title if len(title) <= 72 else title[:71] + "…"
            detail = f"{host_label(session['host'], self.language)} · {short_title}"
            self.detail.setToolTip(
                self.t(
                    "最近宿主事件：{event}\n{title}\n根据宿主事件显示，不表示已观测桌面焦点或已经压缩。",
                    "Latest host event: {event}\n{title}\nBased on host events; this does not prove desktop focus or compression.",
                    event=session.get("event") or self.t("未提供", "Not provided"),
                    title=title,
                )
            )
            if self.target_enabled:
                detail += self.t(
                    "\n不操作将保持开启；只处理实际经 TOMC 的请求。",
                    "\nStays enabled unless changed; only requests routed through TOMC are processed.",
                )
                if not session.get("effective_enabled", True):
                    detail += self.t("全局处理当前已暂停。", " Processing is paused globally.")
            else:
                detail += self.t(
                    "\n此会话保留关闭设置，可在这里重新开启。",
                    "\nThis session stays disabled. You can re-enable it here.",
                )
            self.detail.setText(detail)
        if self._error:
            self.detail.setText(
                self.t("设置未保存：{error}", "Settings were not saved: {error}", error=self._error)
            )
        self.adjustSize()
        if self.isVisible() and self.screen():
            area = self.screen().availableGeometry()
            self.move(
                min(self.x(), area.right() - self.width()),
                min(self.y(), area.bottom() - self.height()),
            )

    def present(self, session):
        self._shown_session = dict(session)
        self._error = None
        self.target = (session["host"], session["session_id"])
        self.target_enabled = bool(session.get("enabled", True))
        self.retranslate()
        self.show()
        self.timer.start(12000)

    def toggle_session(self):
        if not self.target:
            return
        try:
            self.sessions.set_enabled(*self.target, not self.target_enabled)
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self._error = str(exc)
            self.retranslate()
            self.timer.stop()
            return
        self.changed.emit()
        self.hide()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)


LIBRARY_STYLE = (
    STYLE
    + """
QDialog { background: #FBF8F2; }
QFrame#card { background: #FFFFFF; border: 1px solid #ECE6DB; border-radius: 14px; }
QLabel#title { font-size: 21px; font-weight: 600; color: #2F4A3B; }
QLabel#subtitle { color: #8A7F72; font-size: 12px; }
QLabel#kpiValue { font-size: 24px; font-weight: 600; color: #2F4A3B; }
QLabel#kpiMoney { font-size: 24px; font-weight: 600; color: #3F3730; }
QLabel#kpiLabel { color: #8A7F72; font-size: 11px; }
QLabel#chip { background: #EEF2EA; color: #3F6B53; border-radius: 10px; padding: 3px 10px; font-size: 11px; }
QLabel#paused { background: #F6EBDC; color: #866239; border-radius: 10px; padding: 3px 10px; font-size: 11px; }
QLabel#modelChip { background: #F6F2EA; color: #4E453D; border-radius: 9px; padding: 4px 10px; font-size: 11px; }
QLabel#section { font-size: 12px; font-weight: 600; color: #6E655B; }
QLabel#status { background: #F3F6F0; border-radius: 8px; padding: 9px; }
QWidget#periods { background: #F0ECE4; border-radius: 8px; }
QPushButton#period { background: transparent; border: none; color: #706659; border-radius: 6px; padding: 4px 12px; font-size: 12px; }
QPushButton#period:checked { background: #FFFFFF; color: #345743; font-weight: 600; }
QPushButton#link { background: transparent; border: none; color: #3F6B53; padding: 4px 6px; }
QPushButton#link:hover { background: #E4ECE5; }
QListWidget#conversations { background: transparent; border: none; padding: 0; }
QListWidget#conversations::item { border: none; border-radius: 10px; padding: 0; margin: 1px 0; }
QListWidget#conversations::item:selected { background: #E6EFE7; color: #294735; }
QListWidget#conversations::item:hover:!selected { background: #F3EFE7; }
QListWidget#versions { background: #FFFFFF; border: 1px solid #ECE6DB; border-radius: 10px; padding: 4px; }
QListWidget#versions::item { border: none; border-radius: 8px; padding: 0; }
QListWidget#versions::item:selected { background: #E6EFE7; color: #294735; }
QListWidget#versions::item:hover:!selected { background: #F6F3EC; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; border: none; padding: 8px 14px; margin: 0 4px 6px 0; color: #796D60; }
QTabBar::tab:selected { color: #345743; border-bottom: 2px solid #507461; }
QTabBar::tab:hover:!selected { color: #4E453D; }
"""
)


def clear_cards(view):
    """Empty a list whose rows are widgets, detaching them now rather than next loop."""
    for row in range(view.count()):
        card = view.itemWidget(view.item(row))
        if card is not None:
            discard(card)
    view.clear()


def plain(text="", *, name=None, wrap=False):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if name:
        item.setObjectName(name)
    return item


class ConversationCard(QWidget):
    """One conversation in the list: its name, where it ran, and what it saved."""

    def __init__(self, title, meta, when, stats):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = ElidedLabel(title, 13, "#2F2A26", bold=True)
        self.when = plain(when)
        self.when.setStyleSheet("color: #9A8F82; font-size: 11px;")
        top.addWidget(self.title, 1)
        top.addWidget(self.when)
        layout.addLayout(top)
        self.meta = ElidedLabel(meta, 11, "#8A7F72")
        layout.addWidget(self.meta)
        self.stats = ElidedLabel(stats, 11, "#3F6B53")
        layout.addWidget(self.stats)


class VersionCard(QWidget):
    """One saved context of a conversation, newest first."""

    def __init__(self, title, meta, tokens):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = ElidedLabel(title, 12, "#2F2A26")
        self.tokens = plain(tokens)
        self.tokens.setStyleSheet("color: #3F6B53; font-size: 11px;")
        top.addWidget(self.title, 1)
        top.addWidget(self.tokens)
        layout.addLayout(top)
        self.meta = ElidedLabel(meta, 11, "#8A7F72")
        layout.addWidget(self.meta)


class ContextLibraryDialog(QDialog):
    """A savings dashboard over saved contexts grouped by their original conversations."""

    changed = Signal()

    def __init__(
        self,
        path,
        parent=None,
        *,
        library=None,
        sessions=None,
        integrations=None,
        pricing="load",
        activity=None,
    ):
        super().__init__(parent)
        self.language = getattr(parent, "language", None) or UiLanguage(path, self)
        if library is None:
            from .context_library import ContextLibrary

            library = ContextLibrary(path)
        if sessions is None:
            from .session_store import SessionStore

            sessions = SessionStore(path)
        self.path = Path(path)
        self.library, self.sessions = library, sessions
        self.activity = activity or RequestActivity(path)
        self.integrations = integrations
        self.pricing = load_pricing() if pricing == "load" else pricing
        self._load_pricing = pricing == "load"
        self.period = "all"
        self.records, self.conversations, self.visible = [], [], []
        self.names, self.report = {}, None
        self.selected_record = self.selected_conversation = None
        self._refreshing = False
        self._message_spec = (
            "上下文保存在本机；复制与导出只处理你选中的版本。",
            "Contexts stay on this device. Copy and export use only the selected version.",
            {},
        )
        self.setStyleSheet(LIBRARY_STYLE)
        self.resize(1100, 860)
        self.setMinimumSize(900, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title_label = plain(name="title")
        self.subtitle = plain(name="subtitle")
        titles.addWidget(self.title_label)
        titles.addWidget(self.subtitle)
        heading.addLayout(titles)
        heading.addStretch()
        self.status_chip = plain(name="chip")
        heading.addWidget(self.status_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        heading.addSpacing(8)
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        heading.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(heading)
        layout.addWidget(self.make_dashboard())
        self.tabs = QTabWidget()
        self.tabs.addTab(self.make_context_tab(), "")
        self.tabs.addTab(self.make_settings_tab(), "")
        layout.addWidget(self.tabs, 1)
        self.message = plain(name="muted", wrap=True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.message)
        self.language.changed.connect(self.retranslate)
        self.retranslate()

    def t(self, zh, en, **values):
        return self.language.tr(zh, en, **values)

    def show_message(self, zh, en, **values):
        self._message_spec = (zh, en, values)
        self.message.setText(self.t(zh, en, **values))

    # Construction -----------------------------------------------------------

    def make_dashboard(self):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        surface = QWidget()
        surface.setObjectName("periods")
        periods = QHBoxLayout(surface)
        periods.setContentsMargins(3, 3, 3, 3)
        periods.setSpacing(2)
        self.period_buttons = {}
        for key in ("today", "7d", "all"):
            button = QPushButton()
            button.setObjectName("period")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=key: self.set_period(value))
            self.period_buttons[key] = button
            periods.addWidget(button)
        top.addWidget(surface)
        top.addStretch()
        self.basis = plain(name="muted")
        top.addWidget(self.basis)
        self.price_button = QPushButton()
        self.price_button.setObjectName("link")
        opener = getattr(self.parent(), "open_reference", None)
        self.price_button.setVisible(opener is not None)
        if opener is not None:
            self.price_button.clicked.connect(lambda: opener())
        top.addWidget(self.price_button)
        layout.addLayout(top)
        metrics = QHBoxLayout()
        metrics.setSpacing(28)
        self.kpis = {}
        for key, style in (
            ("tokens", "kpiValue"),
            ("money", "kpiMoney"),
            ("compressions", "kpiValue"),
            ("conversations", "kpiValue"),
        ):
            column = QVBoxLayout()
            column.setSpacing(1)
            value = plain(name=style)
            caption = plain(name="kpiLabel")
            column.addWidget(caption)
            column.addWidget(value)
            column.addStretch()
            metrics.addLayout(column)
            self.kpis[key] = (value, caption)
        metrics.addStretch()
        chart = QVBoxLayout()
        chart.setSpacing(4)
        self.chart_title = plain(name="kpiLabel")
        chart.addWidget(self.chart_title)
        self.chart = SavingsChart(self.language, self)
        self.chart.setFixedHeight(46)
        self.chart.setMinimumWidth(260)
        chart.addWidget(self.chart)
        metrics.addLayout(chart, 1)
        layout.addLayout(metrics)
        self.model_chips = QHBoxLayout()
        self.model_chips.setSpacing(8)
        layout.addLayout(self.model_chips)
        return card

    def make_context_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_records)
        self.host_filter = QComboBox()
        for data in ("", "codex", "claude", "unlinked"):
            self.host_filter.addItem("", data)
        self.host_filter.currentIndexChanged.connect(self.filter_records)
        self.import_button = QPushButton()
        self.import_button.clicked.connect(self.import_bundle)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.host_filter)
        filters.addWidget(self.import_button)
        layout.addLayout(filters)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.conversation_list = QListWidget()
        self.conversation_list.setObjectName("conversations")
        self.conversation_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.conversation_list.currentRowChanged.connect(self.select_conversation)
        left_layout.addWidget(self.conversation_list, 1)
        self.count_label = plain(name="muted")
        left_layout.addWidget(self.count_label)
        split.addWidget(left)
        self.preview_stack = QStackedWidget()
        self.empty = plain(name="muted", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_stack.addWidget(self.empty)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(18, 0, 0, 0)
        detail_layout.setSpacing(6)
        self.conversation_title = ElidedLabel("", 18, "#2F2A26", bold=True)
        self.conversation_title.setFixedHeight(28)
        detail_layout.addWidget(self.conversation_title)
        self.conversation_meta = ElidedLabel("", 12, "#8A7F72")
        detail_layout.addWidget(self.conversation_meta)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.conversation_chips = [plain(name="chip") for _ in range(3)]
        for chip in self.conversation_chips:
            chips.addWidget(chip)
        chips.addStretch()
        self.conversation_enabled = QCheckBox()
        self.conversation_enabled.toggled.connect(self.change_conversation)
        chips.addWidget(self.conversation_enabled)
        detail_layout.addLayout(chips)
        detail_layout.addSpacing(6)
        self.versions_title = plain(name="section")
        detail_layout.addWidget(self.versions_title)
        self.version_list = QListWidget()
        self.version_list.setObjectName("versions")
        self.version_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.version_list.currentItemChanged.connect(self.select_context)
        detail_layout.addWidget(self.version_list)
        detail_layout.addSpacing(4)
        selected = QFrame()
        selected.setObjectName("card")
        card = QVBoxLayout(selected)
        card.setContentsMargins(14, 10, 14, 12)
        card.setSpacing(4)
        self.record_title = ElidedLabel("", 14, "#2F2A26", bold=True)
        self.record_title.setFixedHeight(22)
        card.addWidget(self.record_title)
        self.record_meta = ElidedLabel("", 11, "#8A7F72")
        card.addWidget(self.record_meta)
        self.record_tokens = plain()
        self.record_tokens.setStyleSheet("font-size: 13px; color: #345743;")
        card.addWidget(self.record_tokens)
        self.request_status = plain(name="muted", wrap=True)
        card.addWidget(self.request_status)
        self.record_cost = plain(name="muted", wrap=True)
        card.addWidget(self.record_cost)
        card.addSpacing(4)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.copy_button = QPushButton()
        self.copy_button.setObjectName("primary")
        self.copy_button.clicked.connect(self.copy_handoff)
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self.export_context)
        self.rename_button = QPushButton()
        self.rename_button.clicked.connect(self.rename_context)
        self.delete_button = QPushButton()
        self.delete_button.clicked.connect(self.delete_context)
        self.record_buttons = (
            self.copy_button,
            self.export_button,
            self.rename_button,
            self.delete_button,
        )
        for button in self.record_buttons:
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch()
        card.addLayout(actions)
        # Never squeeze the summary and buttons; the content view below absorbs space.
        selected.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        detail_layout.addWidget(selected)
        self.content_tabs = QTabWidget()
        self.content_tabs.setMinimumHeight(110)
        self.memory = QPlainTextEdit()
        self.memory.setReadOnly(True)
        self.task = QPlainTextEdit()
        self.task.setReadOnly(True)
        self.content_tabs.addTab(self.memory, "")
        self.content_tabs.addTab(self.task, "")
        detail_layout.addWidget(self.content_tabs, 1)
        if sys.platform == "darwin":
            # Keep short macOS windows from squeezing the summary and its buttons.
            # Only the selected context pane scrolls; navigation stays in place.
            detail_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            detail_scroll = QScrollArea()
            detail_scroll.setObjectName("contextDetailScroll")
            detail_scroll.setWidgetResizable(True)
            detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
            detail.setObjectName("contextDetailBody")
            detail_scroll.setStyleSheet(
                "QScrollArea#contextDetailScroll, QWidget#contextDetailBody "
                "{ background: #FBF8F2; border: none; }"
            )
            detail_scroll.setWidget(detail)
            self.preview_stack.addWidget(detail_scroll)
        else:
            self.preview_stack.addWidget(detail)
        split.addWidget(self.preview_stack)
        split.setStretchFactor(1, 1)
        split.setSizes([330, 700])
        layout.addWidget(split, 1)
        return page

    def make_settings_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)
        self.switches_title = plain(name="section")
        layout.addWidget(self.switches_title)
        controls = QHBoxLayout()
        self.enabled = QCheckBox()
        self.save_contexts = QCheckBox()
        self.enabled.toggled.connect(lambda value: self.change_setting("enabled", value))
        self.save_contexts.toggled.connect(
            lambda value: self.change_setting("save_contexts", value)
        )
        controls.addWidget(self.enabled)
        controls.addSpacing(20)
        controls.addWidget(self.save_contexts)
        controls.addStretch()
        self.default_note = plain(name="muted")
        controls.addWidget(self.default_note)
        layout.addLayout(controls)
        self.connection_title = plain(name="section")
        layout.addWidget(self.connection_title)
        self.mode = plain(name="muted", wrap=True)
        layout.addWidget(self.mode)
        status_row = QHBoxLayout()
        self.integration_labels = {}
        for host in ("codex", "claude_code"):
            label = plain(name="status", wrap=True)
            status_row.addWidget(label, 1)
            self.integration_labels[host] = label
        layout.addLayout(status_row)
        self.activity_status = plain(name="muted", wrap=True)
        layout.addWidget(self.activity_status)
        self.sessions_title = plain(name="section")
        layout.addWidget(self.sessions_title)
        self.session_note = plain(name="muted", wrap=True)
        layout.addWidget(self.session_note)
        self.session_list = QListWidget()
        self.session_list.setWordWrap(True)
        self.session_list.itemChanged.connect(self.change_session)
        layout.addWidget(self.session_list, 1)
        self.session_hint = plain(name="muted", wrap=True)
        layout.addWidget(self.session_hint)
        return page

    def retranslate(self, *_):
        t = self.t
        self.setWindowTitle(t("TOMC · 上下文与接续", "TOMC · Contexts and handoff"))
        self.title_label.setText(t("上下文与接续", "Contexts and handoff"))
        self.subtitle.setText(
            t(
                "TOMC 压缩过的上下文，按原来的对话整理",
                "Contexts TOMC compressed, organized by their original conversations",
            )
        )
        self.refresh_button.setText(t("刷新", "Refresh"))
        for key, zh, en in (
            ("today", "今天", "Today"),
            ("7d", "近七天", "7 days"),
            ("all", "累计", "All time"),
        ):
            self.period_buttons[key].setText(t(zh, en))
        self.price_button.setText(t("模型与估价 ›", "Models && pricing ›"))
        for key, zh, en in (
            ("tokens", "节省 tokens", "Tokens saved"),
            ("money", "省下的钱", "Money saved"),
            ("compressions", "压缩次数", "Compressions"),
            ("conversations", "对话", "Conversations"),
        ):
            self.kpis[key][1].setText(t(zh, en))
        self.chart_title.setText(t("每日节省 · 近 14 天", "Saved per day · last 14 days"))
        self.tabs.setTabText(0, t("对话", "Conversations"))
        self.tabs.setTabText(1, t("设置与连接", "Settings and connections"))
        self.search.setPlaceholderText(
            t("搜索对话名称、任务或文件夹", "Search conversation names, tasks or folders")
        )
        for index, (zh, en) in enumerate(
            (
                ("全部宿主", "All hosts"),
                ("Codex", "Codex"),
                ("Claude Code", "Claude Code"),
                ("未关联或导入", "Unlinked or imported"),
            )
        ):
            self.host_filter.setItemText(index, t(zh, en))
        self.import_button.setText(t("导入上下文包", "Import context bundle"))
        self.import_button.setToolTip(
            t(
                "导入在另一台电脑上导出的上下文包",
                "Import a context bundle exported on another computer",
            )
        )
        self.conversation_list.setAccessibleName(t("对话列表", "Conversation list"))
        self.version_list.setAccessibleName(
            t("这个对话的上下文版本", "Context versions of this conversation")
        )
        self.versions_title.setText(t("上下文版本", "Context versions"))
        self.conversation_enabled.setText(
            t("本对话启用 TOMC", "TOMC enabled for this conversation")
        )
        self.conversation_enabled.setToolTip(
            t(
                "只影响这个对话之后的请求；其他对话不变。",
                "Affects only later requests in this conversation; others are unchanged.",
            )
        )
        self.copy_button.setText(t("复制接续提示词", "Copy handoff prompt"))
        self.export_button.setText(t("导出便携包", "Export bundle"))
        self.rename_button.setText(t("重命名", "Rename"))
        self.delete_button.setText(t("删除", "Delete"))
        self.content_tabs.setTabText(0, t("上下文正文", "Context content"))
        self.content_tabs.setTabText(1, t("原任务", "Original task"))
        self.memory.setAccessibleName(
            t("选中上下文正文，只读", "Selected context content, read-only")
        )
        self.task.setAccessibleName(t("原任务与来源，只读", "Original task and source, read-only"))
        self.switches_title.setText(t("TOMC 开关", "TOMC switches"))
        self.enabled.setText(t("TOMC 处理", "TOMC processing"))
        self.enabled.setToolTip(
            t(
                "全局暂停后，新准备请求停止；已有上下文仍可浏览和导出。",
                "Pausing stops new preparation. Existing contexts remain available to browse and export.",
            )
        )
        self.save_contexts.setText(t("保存上下文记录", "Save context records"))
        self.save_contexts.setToolTip(
            t(
                "只控制之后的正文保存；不删除已有记录，不关闭 TOMC 处理。",
                "Controls future content storage. Existing records and TOMC processing are unaffected.",
            )
        )
        self.default_note.setText(
            t("新会话默认开启，可单独关闭", "New sessions start enabled; each can be turned off")
        )
        self.connection_title.setText(t("连接状态", "Connections"))
        self.sessions_title.setText(t("各对话开关", "Per-conversation switches"))
        self.session_list.setAccessibleName(
            t("已登记会话及本会话开关", "Registered sessions and individual switches")
        )
        self.session_hint.setText(
            t(
                "存在关闭会话时，身份未关联的准备会暂停，需重新加载宿主接入。",
                "When a session is disabled, preparation without a session identity pauses until the host integration is reloaded.",
            )
        )
        self.refresh()
        zh, en, values = self._message_spec
        self.message.setText(self.t(zh, en, **values))

    # Data -------------------------------------------------------------------

    def refresh(self, checked=False, select_id=None):
        if self._load_pricing:
            self.pricing = load_pricing()
        selected_id = select_id or (self.selected_record or {}).get("id")
        self._refreshing = True
        try:
            settings = self.sessions.settings()
            self.enabled.setChecked(settings.get("enabled", True))
            self.save_contexts.setChecked(settings.get("save_contexts", True))
            self.records = self.library.list(limit=10000)
            registered = {(row["host"], row["session_id"]): row for row in self.sessions.list()}
            pairs = set(registered) | {
                (row.get("host"), row["session_id"])
                for row in self.records
                if row.get("session_id")
            }
            self.names = resolve(pairs)
            self.conversations = group_conversations(
                self.records,
                names=self.names,
                savings=request_savings(self.path, reference=self.pricing),
                sessions=registered,
                imported=self.library.conversation_titles(),
            )
            self.refresh_sessions(registered)
            self.refresh_status(settings)
            self.report = savings_report(self.path, self.period, reference=self.pricing)
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.show_message(
                "目录暂不可读：{error}",
                "The library cannot be read right now: {error}",
                error=str(exc),
            )
            self.records, self.conversations = [], []
        finally:
            self._refreshing = False
        self.render_dashboard()
        self.filter_records(select_id=selected_id)

    def set_period(self, period):
        self.period = period
        try:
            self.report = savings_report(self.path, period, reference=self.pricing)
        except (OSError, sqlite3.Error, ValueError):
            self.report = None
        self.render_dashboard()

    def render_dashboard(self):
        t = self.t
        for key, button in self.period_buttons.items():
            button.setChecked(key == self.period)
        report = self.report
        tokens, money = self.kpis["tokens"][0], self.kpis["money"][0]
        if report is None:
            tokens.setText("—")
            money.setText("—")
            self.kpis["compressions"][0].setText("—")
            self.basis.setText(t("统计暂不可读", "Statistics unavailable"))
            self.chart.set_days([], None)
        else:
            saved = report["tokens_saved"]
            tokens.setText(total_tokens(saved))
            money.setText(money_text(report["money"]))
            self.kpis["compressions"][0].setText(f"{report['preparations']:,}")
            self.basis.setText(
                t("按各模型缓存读取价折算", "At each model's cached-read price")
                if report["mode"] == "cached"
                else t("按各模型输入价折算", "At each model's input price")
            )
            start = None
            if report["period"] != "all":
                days = 6 if report["period"] == "7d" else 0
                start = report["daily"][-1 - days]["day"]
            self.chart.set_days(report["daily"], start)
        self.kpis["conversations"][0].setText(f"{len(self.conversations):,}")
        while self.model_chips.count():
            item = self.model_chips.takeAt(0)
            if item.widget():
                discard(item.widget())
        for model in (report or {}).get("models", [])[:5]:
            chip = plain(
                f"{model['label'] or t('未定价', 'Unpriced')}  {compact_tokens(model['tokens_saved'])}"
                + (f" · {money_text(model['money'])}" if model["money"] is not None else ""),
                name="modelChip",
            )
            rates = " / ".join(f"${rate:g}" for rate in model.get("rates", []))
            chip.setToolTip(
                t(
                    "节省 {count:,} tokens · {rates} / 百万 tokens",
                    "{count:,} tokens saved · {rates} per million tokens",
                    count=model["tokens_saved"],
                    rates=rates or "—",
                )
            )
            self.model_chips.addWidget(chip)
            chip.show()
        self.model_chips.addStretch()

    def refresh_status(self, settings):
        status = self.integrations if self.integrations is not None else integration_snapshot()
        activity_summary = self.activity.summary()
        observed_hosts = {
            row["host"] for row in activity_summary["by_host"] if row["sent_requests"]
        }
        latest = self.activity.last()
        if latest and latest["state"] == "preparing" and self.activity.active() is None:
            latest = {**latest, "stale": True}
        mode = status.get("mode", {})
        configured = mode.get("id") == "automatic_request_gateway"
        if configured:
            mode_text = (
                self.t(
                    "自动接入已配置，重开客户端后等待请求",
                    "Automatic routing configured; reopen the client and send a request",
                )
                if not activity_summary["sent_requests"]
                else self.t(
                    "自动接入已配置 · 已观察到本地代理转发",
                    "Automatic routing configured · Local forwarding observed",
                )
            )
            service = {
                "online": (" · 转发服务可达", " · Gateway reachable"),
                "offline": (
                    " · 转发服务不可达，请启动服务",
                    " · Gateway unreachable; start the service",
                ),
            }.get(
                mode.get("gateway_service"),
                (" · 转发服务待核验", " · Gateway status unverified"),
            )
            mode_text += self.t(*service)
        else:
            mode_text = (
                self.t(
                    "按需工具可用 · 代理尚未观察到实际转发",
                    "On-demand tools available · No gateway forwarding observed",
                )
                if not activity_summary["sent_requests"]
                else self.t(
                    "已观察到本地代理转发 · 仅覆盖实际经过代理的请求",
                    "Local forwarding observed · Only requests routed through the gateway are covered",
                )
            )
        self.mode.setText(mode_text)
        detail = request_activity_text(latest, self.language)
        if latest:
            detail += f" · {host_label(latest['host'], self.language)} · {local_time(latest['started_utc'])}"
            if latest.get("provider_input_tokens") is not None:
                detail += self.t(
                    " · 实测 provider 输入 {count:,} tokens",
                    " · Measured provider input {count:,} tokens",
                    count=latest["provider_input_tokens"],
                )
                if latest.get("provider_cached_tokens") is not None:
                    detail += self.t(
                        "（缓存 {count:,}）",
                        " (cached {count:,})",
                        count=latest["provider_cached_tokens"],
                    )
        self.activity_status.setText(
            self.t("最近请求：{detail}", "Latest request: {detail}", detail=detail)
        )
        for host, label in self.integration_labels.items():
            item = status.get(host, {})
            runtime = (
                self.t("运行已验证", "Runtime verified")
                if item.get("runtime_verified")
                else self.t("连接待验证", "Connection unverified")
            )
            if ("claude" if host == "claude_code" else host) in observed_hosts:
                runtime = self.t("代理转发曾被观察", "Gateway forwarding observed")
            state = item.get("state") or {
                "已配置": "enabled",
                "配置已启用": "enabled",
                "未配置": "not_configured",
                "已禁用": "disabled",
            }.get(item.get("label"), "unknown")
            labels = {
                "enabled": ("配置已启用", "Configuration enabled"),
                "not_configured": ("未配置", "Not configured"),
                "disabled": ("已禁用", "Disabled"),
                "unknown": ("未知", "Unknown"),
            }
            configured_label = self.t(*labels.get(state, labels["unknown"]))
            if ("claude" if host == "claude_code" else host) in mode.get("configured_hosts", []):
                configured_label = self.t("自动接入已配置", "Automatic routing configured")
            label.setText(f"{host_label(host, self.language)} · {configured_label} · {runtime}")
        if not settings.get("enabled", True):
            self.status_chip.setObjectName("paused")
            self.status_chip.setText(self.t("● TOMC 已暂停", "● TOMC paused"))
        else:
            self.status_chip.setObjectName("chip")
            hosts = [
                host_label(host, self.language)
                for host in ("codex", "claude")
                if host in observed_hosts
            ]
            self.status_chip.setText(
                self.t("● 运行中 · {hosts}", "● Running · {hosts}", hosts=" · ".join(hosts))
                if hosts
                else self.t("● 等待第一个请求", "● Waiting for the first request")
            )
        self.status_chip.setToolTip(f"{mode_text}\n{detail}")
        # The style sheet selects on the object name; re-polish after changing it.
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)

    def contexts(self, count):
        return self.t(
            "{count} 份上下文",
            "{count} context" if count == 1 else "{count} contexts",
            count=count,
        )

    def session_name(self, host, session_id, project=None, stored=None):
        """The host's name, else TOMC's stored or first-task name; plus folder and agent."""
        name = self.names.get((host, session_id)) or {}
        place = name.get("folder") or folder(project)
        if name.get("agent"):
            place = " · ".join(
                part
                for part in (place, self.t("子代理 {name}", "Subagent {name}", name=name["agent"]))
                if part
            )
        title = (
            name.get("title")
            or clean(stored)
            or next(
                (
                    conversation["first_title"]
                    for conversation in self.conversations
                    if conversation["key"] == ("session", host, session_id)
                ),
                None,
            )
        )
        return title or self.t("未命名对话", "Untitled conversation"), place

    def refresh_sessions(self, registered=None):
        self.session_list.blockSignals(True)
        try:
            self.session_list.clear()
            rows = (
                list((registered or {}).values())
                if registered is not None
                else self.sessions.list()
            )
            rows.sort(key=lambda row: row.get("last_seen") or "", reverse=True)
            for row in rows:
                title, place = self.session_name(
                    row["host"], row["session_id"], row.get("project"), row.get("title")
                )
                state = (
                    self.t("开启", "Enabled")
                    if row.get("enabled", True)
                    else self.t("已关闭", "Disabled")
                )
                if row.get("enabled", True) and not row.get("effective_enabled", True):
                    state += self.t(" · 全局暂停", " · Paused globally")
                details = " · ".join(
                    part
                    for part in (
                        host_label(row["host"], self.language),
                        place,
                        state,
                        self.t(
                            "最近 {stamp}",
                            "Last active {stamp}",
                            stamp=local_time(row.get("last_seen")),
                        ),
                    )
                    if part
                )
                item = QListWidgetItem(f"{title}\n{details}")
                item.setData(Qt.ItemDataRole.UserRole, (row["host"], row["session_id"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if row.get("enabled", True) else Qt.CheckState.Unchecked
                )
                item.setToolTip(
                    self.t(
                        "勾选表示允许 TOMC 处理这个对话；不修改宿主权限。\n会话 ID：{identity}",
                        "Checked lets TOMC process this conversation; host permissions are unchanged.\nSession ID: {identity}",
                        identity=row["session_id"],
                    )
                )
                self.session_list.addItem(item)
            self.session_note.setText(
                self.t(
                    "{count} 个对话；勾选表示允许 TOMC 处理。全局暂停时，已开启的对话也不会处理。",
                    "Conversations: {count}. Checked ones allow TOMC processing; a global pause also stops enabled ones.",
                    count=len(rows),
                )
                if rows
                else self.t(
                    "尚未收到会话事件。配置 hooks 后，新建、恢复或活动事件可登记会话；旧聊天不会凭空补全。",
                    "No session events received yet. After hooks are configured, start, resume or activity events register sessions. Old chats are not reconstructed.",
                )
            )
        finally:
            self.session_list.blockSignals(False)

    # Conversations ----------------------------------------------------------

    def display_title(self, conversation):
        if conversation["title"]:
            return conversation["title"]
        if conversation["kind"] == "unlinked":
            return self.t("未关联对话的上下文", "Contexts without a conversation")
        return conversation["first_title"] or self.t("未命名对话", "Untitled conversation")

    def describe_conversation(self, conversation):
        parts = [host_label(conversation["host"], self.language)]
        if conversation["kind"] == "imported":
            parts = [
                self.t(
                    "导入 · 来自 {host}",
                    "Imported · from {host}",
                    host=host_label(conversation["host"], self.language),
                )
            ]
        if conversation.get("folder"):
            parts.append(conversation["folder"])
        if conversation.get("agent"):
            parts.append(self.t("子代理 {name}", "Subagent {name}", name=conversation["agent"]))
        return " · ".join(parts)

    def filter_records(self, *args, select_id=None):
        query = self.search.text().casefold().strip()
        host = self.host_filter.currentData()
        self.visible = []
        for conversation in self.conversations:
            kind, actual = conversation["kind"], conversation["host"] or ""
            if host == "unlinked" and kind == "session":
                continue
            if host == "codex" and (kind != "session" or actual != "codex"):
                continue
            if host == "claude" and (
                kind != "session" or actual not in ("claude", "claude_code", "claude-code")
            ):
                continue
            label = " ".join(
                (
                    self.display_title(conversation),
                    conversation["first_title"] or "",
                    conversation.get("folder") or "",
                    conversation.get("agent") or "",
                    host_label(conversation["host"], self.language) or "",
                )
            ).casefold()
            records = conversation["records"]
            if query and query not in label:
                records = [
                    row
                    for row in records
                    if query
                    in " ".join(
                        str(row.get(key) or "")
                        for key in ("title", "source", "notebook_name", "origin_host")
                    ).casefold()
                ]
            if records:
                self.visible.append((conversation, records))
        selected_key = (self.selected_conversation or {}).get("key")
        target = 0
        for index, (conversation, records) in enumerate(self.visible):
            if select_id and any(row["id"] == select_id for row in records):
                target = index
                break
            if conversation["key"] == selected_key:
                target = index
        self.conversation_list.blockSignals(True)
        clear_cards(self.conversation_list)
        for conversation, records in self.visible:
            stats = self.contexts(len(records)) + self.t(
                " · 节省 {tokens} tokens",
                " · {tokens} tokens saved",
                tokens=compact_tokens(conversation["tokens_saved"]),
            )
            if conversation["money"] is not None:
                stats += f" · {money_text(conversation['money'])}"
            card = ConversationCard(
                self.display_title(conversation),
                self.describe_conversation(conversation),
                local_time(records[0].get("created_utc")),
                stats,
            )
            item = QListWidgetItem()
            item.setSizeHint(card.sizeHint())
            item.setToolTip(self.display_title(conversation))
            self.conversation_list.addItem(item)
            self.conversation_list.setItemWidget(item, card)
        self.conversation_list.blockSignals(False)
        contexts = sum(len(records) for _, records in self.visible)
        self.count_label.setText(
            self.t(
                "{conversations} 个对话 · ",
                "1 conversation · "
                if len(self.visible) == 1
                else "{conversations} conversations · ",
                conversations=len(self.visible),
            )
            + self.contexts(contexts)
        )
        # Kept current even while hidden, so a language switch never leaves stale text.
        self.empty.setText(
            self.t(
                "没有匹配的对话\n\n试试其他名称、任务或文件夹。",
                "No matching conversations\n\nTry another name, task or folder.",
            )
            if self.records
            else self.t(
                "还没有保存的上下文\n\nTOMC 压缩对话后，会按对话整理在这里：\n可以复制接续提示词给另一个 Agent，或导出到另一台电脑。\n旧版数字统计不含正文，无法还原历史上下文。",
                "No saved contexts yet\n\nAfter TOMC compresses a conversation, its contexts appear here.\nCopy a handoff prompt for another agent, or export one to another computer.\nOlder numeric statistics contain no text and cannot restore past contexts.",
            )
        )
        if self.visible:
            self.conversation_list.setCurrentRow(target)
            self.select_conversation(target, select_id=select_id)
        else:
            self.select_conversation(-1)

    def select_conversation(self, row, select_id=None):
        if not 0 <= row < len(self.visible):
            self.selected_conversation = None
            self.version_list.blockSignals(True)
            clear_cards(self.version_list)
            self.version_list.blockSignals(False)
            self.select_context(None)
            return
        conversation, records = self.visible[row]
        self.selected_conversation = conversation
        self.conversation_title.setText(self.display_title(conversation))
        self.conversation_title.setToolTip(self.display_title(conversation))
        meta = self.describe_conversation(conversation)
        self.conversation_meta.setText(
            meta
            + self.t(
                " · 最近 {time}",
                " · Last active {time}",
                time=local_time(records[0]["created_utc"]),
            )
        )
        chips = [
            self.contexts(len(conversation["records"])),
            self.t(
                "节省 {tokens} tokens",
                "{tokens} tokens saved",
                tokens=compact_tokens(conversation["tokens_saved"]),
            ),
            money_text(conversation["money"]) if conversation["money"] is not None else "",
        ]
        for chip, text in zip(self.conversation_chips, chips):
            chip.setText(text)
            chip.setVisible(bool(text))
        self.conversation_chips[1].setToolTip(
            self.t(
                "这个对话所有被压缩的请求合计（含没有保存正文的请求）",
                "All compressed requests in this conversation, including ones without saved text",
            )
            if conversation["requests"]
            else self.t(
                "按保存的上下文估算",
                "Estimated from the saved contexts",
            )
        )
        self.conversation_enabled.blockSignals(True)
        self.conversation_enabled.setVisible(conversation["enabled"] is not None)
        self.conversation_enabled.setChecked(bool(conversation["enabled"]))
        self.conversation_enabled.blockSignals(False)
        self.version_list.blockSignals(True)
        clear_cards(self.version_list)
        selected = None
        for record in records:
            request = record.get("request")
            saved = request["tokens_saved"] if request else record["reduced_tokens"]
            meta = local_time(record.get("created_utc"))
            meta += self.t(
                " · 节省 {tokens} tokens", " · {tokens} tokens saved", tokens=compact_tokens(saved)
            )
            if request and request["money"] is not None:
                meta += f" · {money_text(request['money'])}"
            card = VersionCard(
                record.get("title") or self.t("未命名上下文", "Untitled context"),
                meta,
                f"{compact_tokens(record['input_estimated_tokens'])} → {compact_tokens(record['output_estimated_tokens'])}",
            )
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, record["id"])
            item.setSizeHint(card.sizeHint())
            item.setToolTip(self.t("快照 {identity}", "Snapshot {identity}", identity=record["id"]))
            self.version_list.addItem(item)
            self.version_list.setItemWidget(item, card)
            if record["id"] == select_id:
                selected = item
        self.version_list.blockSignals(False)
        # Fit up to four versions; longer histories scroll.
        rows = sum(self.version_list.sizeHintForRow(i) for i in range(min(4, len(records))))
        self.version_list.setFixedHeight(rows + 2 * self.version_list.frameWidth() + 10)
        self.version_list.setCurrentItem(selected or self.version_list.item(0))

    # Selected context -------------------------------------------------------

    def select_context(self, current, previous=None):
        self.selected_record = None
        if current:
            try:
                self.selected_record = self.library.get(current.data(Qt.ItemDataRole.UserRole))
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                self.show_message(
                    "记录暂不可读：{error}",
                    "This record cannot be read right now: {error}",
                    error=str(exc),
                )
        row = self.selected_record
        for button in self.record_buttons:
            button.setEnabled(bool(row))
        self.preview_stack.setCurrentIndex(1 if row else 0)
        if not row:
            self.memory.clear()
            self.task.clear()
            return
        conversation = self.selected_conversation or {}
        request = next(
            (
                record.get("request")
                for record in conversation.get("records", [])
                if record["id"] == row["id"]
            ),
            None,
        )
        self.record_title.setText(row.get("title") or self.t("未命名上下文", "Untitled context"))
        self.record_title.setToolTip(row.get("title") or "")
        sources = {
            "automatic_request": ("自动请求", "Automatic request"),
            "prepare": ("手动准备", "Manual preparation"),
            "recall": ("笔记本调用", "Notebook recall"),
        }
        source = sources.get(row.get("source"))
        self.record_meta.setText(
            " · ".join(
                part
                for part in (
                    local_time(row.get("created_utc")),
                    self.t(*source) if source else row.get("source"),
                    self.t(
                        "预算 {budget:,} tokens", "Budget {budget:,} tokens", budget=row["budget"]
                    )
                    if isinstance(row.get("budget"), int)
                    else "",
                )
                if part
            )
        )
        before, after = row["input_estimated_tokens"], row["output_estimated_tokens"]
        delta = before - after
        self.record_tokens.setText(
            self.t(
                "上下文 {before:,} → {after:,} tokens · {direction} {delta:,}",
                "Context {before:,} → {after:,} tokens · {direction} {delta:,}",
                before=before,
                after=after,
                direction=self.t("节省", "saved") if delta >= 0 else self.t("增加", "added"),
                delta=abs(delta),
            )
        )
        if request:
            text = self.t(
                "整个请求节省 {tokens:,} tokens",
                "The whole request saved {tokens:,} tokens",
                tokens=request["tokens_saved"],
            )
            if request["money"] is not None:
                text += self.t(
                    " · 约 {money}（{model}）",
                    " · about {money} ({model})",
                    money=money_text(request["money"]),
                    model=request["model"],
                )
            self.request_status.setText(text)
        else:
            self.request_status.setText(
                self.t("此快照的请求用量：未关联", "Request usage for this snapshot: not linked")
            )
        if self.pricing and not (request and request["money"] is not None):
            value = input_value(delta, self.pricing)
            model = (
                (self.pricing.get("label") if self.language.code == "zh" else None)
                or self.pricing.get("model")
                or self.t("所选模型", "Selected model")
            )
            self.record_cost.setText(
                self.t(
                    "参考输入金额{direction} {value} · {model}",
                    "Reference input value {direction} {value} · {model}",
                    direction=self.t("节省", "saved") if delta >= 0 else self.t("增加", "added"),
                    value=money_text(abs(value)) if value is not None else "—",
                    model=model,
                )
            )
            self.record_cost.setToolTip(explanation(self.pricing, self.language))
            self.record_cost.show()
        else:
            self.record_cost.clear()
            self.record_cost.hide()
        self.memory.setPlainText(row.get("memory", ""))
        title = self.display_title(conversation) if conversation else ""
        self.task.setPlainText(
            self.t(
                "原任务\n{task}\n\n对话：{conversation}\n时间：{time}\n来源：{host}\n\n这是为原任务准备的上下文，可能有遗漏，不是完整聊天的无损副本。",
                "Original task\n{task}\n\nConversation: {conversation}\nTime: {time}\nSource: {host}\n\nThis context was prepared for the original task and may omit details. It is not a lossless copy of the full conversation.",
                task=row.get("task") or self.t("未记录", "Not recorded"),
                conversation=title or self.t("未关联", "Not linked"),
                time=local_time(row.get("created_utc")),
                host=host_label(row.get("origin_host") or row.get("host"), self.language),
            )
        )

    # Actions ----------------------------------------------------------------

    def change_setting(self, name, value):
        if self._refreshing:
            return
        try:
            self.sessions.update_settings(**{name: value})
            self.show_message(
                "设置已保存。处理开关与正文记录开关彼此独立。",
                "Settings saved. Processing and content storage are independent switches.",
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.show_message(
                "设置未保存：{error}", "Settings were not saved: {error}", error=str(exc)
            )
        self.refresh()
        self.changed.emit()

    def set_session(self, host, session_id, enabled):
        try:
            self.sessions.set_enabled(host, session_id, enabled)
            if enabled:
                self.show_message(
                    "本会话 TOMC 已开启；其他会话设置不变。",
                    "TOMC is enabled for this session; other sessions are unchanged.",
                )
            else:
                self.show_message(
                    "本会话 TOMC 已关闭；其他会话设置不变。",
                    "TOMC is disabled for this session; other sessions are unchanged.",
                )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message(
                "设置未保存：{error}", "Settings were not saved: {error}", error=str(exc)
            )
        self.changed.emit()

    def change_session(self, item):
        if self._refreshing:
            return
        host, session_id = item.data(Qt.ItemDataRole.UserRole)
        self.set_session(host, session_id, item.checkState() == Qt.CheckState.Checked)
        self.refresh()

    def change_conversation(self, enabled):
        conversation = self.selected_conversation
        if self._refreshing or not conversation or conversation["kind"] != "session":
            return
        self.set_session(conversation["host"], conversation["session_id"], enabled)
        self.refresh()

    def copy_handoff(self):
        if not self.selected_record:
            return
        try:
            prompt = self.library.handoff_prompt(
                self.selected_record["id"], inline=True, language=self.language.code
            )
            QApplication.clipboard().setText(prompt)
            self.show_message(
                "已复制自包含接续提示词（{count:,} 字符），未截断。可粘贴到另一个 Agent。",
                "Copied a complete handoff prompt ({count:,} characters), without truncation. Paste it into another agent.",
                count=len(prompt),
            )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("复制失败：{error}", "Copy failed: {error}", error=str(exc))

    def export_context(self):
        if not self.selected_record:
            return
        folder_name = QFileDialog.getExistingDirectory(
            self, self.t("选择便携包保存目录", "Choose a folder for the portable bundle")
        )
        if not folder_name:
            return
        conversation = self.selected_conversation
        try:
            destination = self.library.export(
                self.selected_record["id"],
                Path(folder_name),
                language=self.language.code,
                conversation=self.display_title(conversation)
                if conversation and conversation["kind"] != "unlinked"
                else None,
            )
            self.show_message(
                "已导出：{path}。包含正文、接续说明与元数据；未上传。",
                "Exported to {path}. Includes context, handoff instructions and metadata; nothing was uploaded.",
                path=destination,
            )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("导出失败：{error}", "Export failed: {error}", error=str(exc))

    def import_bundle(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self.t(
                "选择包含 metadata.json 的上下文包目录",
                "Choose a context bundle folder containing metadata.json",
            ),
        )
        if not folder:
            return
        try:
            row = self.library.import_bundle(Path(folder))
            self.search.clear()
            self.host_filter.setCurrentIndex(0)
            self.refresh(select_id=row["id"])
            if row.get("imported"):
                self.show_message(
                    "上下文已导入，未计为新的压缩，也未绑定本机会话。",
                    "Context imported; it is not counted as new compression or linked to a local session.",
                )
            else:
                self.show_message(
                    "这个上下文已经存在，未重复导入。",
                    "This context already exists; no duplicate was imported.",
                )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("导入失败：{error}", "Import failed: {error}", error=str(exc))

    def rename_context(self):
        if not self.selected_record:
            return
        dialog = QInputDialog(self)
        dialog.setTextValue(self.selected_record.get("title", ""))

        def translate(*_):
            dialog.setWindowTitle(self.t("重命名上下文", "Rename context"))
            dialog.setLabelText(self.t("显示名称", "Display name"))
            dialog.setOkButtonText(self.t("保存", "Save"))
            dialog.setCancelButtonText(self.t("取消", "Cancel"))

        translate()
        self.language.changed.connect(translate)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            title = dialog.textValue()
        finally:
            self.language.changed.disconnect(translate)
            dialog.deleteLater()
        if not accepted or not title.strip():
            return
        try:
            self.library.rename(self.selected_record["id"], title.strip())
            self.refresh()
            self.show_message(
                "名称已更新，快照正文与处理数据保持原样。",
                "Name updated. Snapshot content and preparation data are unchanged.",
            )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("重命名失败：{error}", "Rename failed: {error}", error=str(exc))

    def delete_context(self):
        if not self.selected_record:
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)

        def translate(*_):
            dialog.setWindowTitle(self.t("删除本地上下文", "Delete local context"))
            dialog.setText(
                self.t(
                    "删除选中的本地快照？\n既有数字统计、宿主聊天和已导出的文件不受影响。",
                    "Delete the selected local snapshot?\nNumeric statistics, host chats and exported files will remain unchanged.",
                )
            )
            dialog.button(QMessageBox.StandardButton.Yes).setText(self.t("删除", "Delete"))
            dialog.button(QMessageBox.StandardButton.Cancel).setText(self.t("取消", "Cancel"))

        translate()
        self.language.changed.connect(translate)
        try:
            answer = dialog.exec()
        finally:
            self.language.changed.disconnect(translate)
            dialog.deleteLater()
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.library.delete(self.selected_record["id"])
            self.refresh()
            self.show_message(
                "本地快照已删除；数字统计、宿主聊天和已导出文件保留。",
                "Local snapshot deleted. Numeric statistics, host chats and exported files are retained.",
            )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("删除失败：{error}", "Delete failed: {error}", error=str(exc))


def run(path):
    """Open just the local context dialog, independently of the companion."""
    from .usage_widget_qt import load_preview_fonts

    app = QApplication.instance() or QApplication([])
    load_preview_fonts()
    dialog = ContextLibraryDialog(path)
    dialog.show()
    try:
        return app.exec()
    finally:
        dialog.close()
        dialog.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
