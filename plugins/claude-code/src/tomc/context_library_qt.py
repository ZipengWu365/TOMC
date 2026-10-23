"""Local context browser and session controls; no model or host UI automation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .cost_estimate import dollars, explanation, input_value, load_pricing
from .request_activity import RequestActivity
from .ui_language import UiLanguage

_STATIC_TEXT = {
    "TOMC 会话状态": "TOMC session status",
    "TOMC · 上下文与接续": "TOMC · Context and handoff",
    "上下文与接续": "Context and handoff", "刷新": "Refresh",
    "TOMC · 请求接入状态待读取": "TOMC · Loading request integration status",
    "自动请求：尚未观察到代理请求": "Automatic requests: no gateway request observed yet",
    "TOMC 处理": "TOMC processing", "保存上下文记录": "Save context records",
    "全局暂停后，新准备请求停止；已有上下文仍可浏览和导出。":
        "Pausing stops new preparation. Existing contexts remain available to browse and export.",
    "只控制之后的正文保存；不删除已有记录，不关闭 TOMC 处理。":
        "Controls future content storage. Existing records and TOMC processing are unaffected.",
    "新会话默认开启，可单独关闭": "New sessions start enabled; each can be turned off",
    "上下文保存在本机；复制与导出只处理你选中的版本。":
        "Contexts stay on this device. Copy and export use only the selected version.",
    "搜索标题、来源或会话": "Search titles, sources or sessions",
    "导入上下文包": "Import context bundle", "已处理上下文列表": "Prepared context list",
    "暂无处理记录\n\n成功准备并保存的上下文会出现在这里。\n旧版数字统计不含正文，无法还原历史上下文。":
        "No prepared contexts yet\n\nSaved contexts will appear here after preparation.\nOlder numeric statistics contain no text and cannot restore past contexts.",
    "此快照的请求用量 / 账单差异：未关联测量":
        "Request usage / billing difference for this snapshot: no linked measurement",
    "选中上下文正文，只读": "Selected context content, read-only",
    "原任务与记录信息，只读": "Original task and record details, read-only",
    "重命名": "Rename", "删除": "Delete", "导出便携包": "Export bundle",
    "复制接续提示词": "Copy handoff prompt",
    "仅显示已收到宿主事件的会话；登记不代表已压缩。纯界面焦点切换无法可靠观测。":
        "Only sessions with host events appear here. Registration does not prove compression. UI focus changes cannot be observed reliably.",
    "已登记会话及本会话开关": "Registered sessions and individual switches",
    "存在关闭会话时，身份未关联的准备会暂停，需重新加载宿主接入。":
        "When a session is disabled, preparation without a session identity pauses until the host integration is reloaded.",
    "保持开启": "Keep enabled", "关闭本会话": "Disable session",
}


def _tr(language, zh, en, **values):
    if hasattr(language, "tr"):
        return language.tr(zh, en, **values)
    return (en if language == "en" else zh).format(**values)


def _static_translations(owner):
    """Capture only authored UI labels at construction, never saved user text."""
    bindings = []
    for widget in [owner, *owner.findChildren(QWidget)]:
        for getter, setter in (("text", "setText"), ("placeholderText", "setPlaceholderText"),
                               ("toolTip", "setToolTip"), ("accessibleName", "setAccessibleName"),
                               ("windowTitle", "setWindowTitle")):
            if hasattr(widget, getter) and hasattr(widget, setter):
                value = getattr(widget, getter)()
                if isinstance(value, str) and value in _STATIC_TEXT:
                    bindings.append((getattr(widget, setter), value, _STATIC_TEXT[value]))
    return bindings

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
    return {"codex": "Codex", "claude_code": "Claude Code", "claude-code": "Claude Code",
            "claude": "Claude Code"}.get(host, host or _tr(language, "未关联会话", "Unlinked session"))


def short_date(value, language=None):
    return str(value or _tr(language, "时间未知", "Unknown time")).replace("T", " ").replace("+00:00", "Z")[:19]


def request_activity_text(record, language=None):
    """Describe observed request work without claiming unmeasured cost savings."""
    def t(zh, en, **values):
        return _tr(language, zh, en, **values)
    if not record:
        return t("自动请求：尚未观察到代理请求", "Automatic requests: no gateway request observed yet")
    reasons = {
        "session_disabled": ("本会话已关闭 TOMC", "TOMC is disabled for this session"),
        "global_disabled": ("全局处理已暂停", "Processing is paused globally"),
        "disabled": ("TOMC 已暂停", "TOMC is paused"),
        "identity_required": ("会话身份待关联", "Session identity is not linked"),
        "no_current_user_task": ("本次请求没有新的用户任务", "This request has no new user task"),
        "no_readable_old_history": ("没有可读取的较早历史", "No readable earlier history"),
        "history_not_supported_by_compiler": ("保留暂不支持处理的历史内容", "History format retained without compression"),
        "no_complete_memory_fits": ("预算不足以保留完整上下文记录", "The budget cannot fit a complete context record"),
        "invalid_adapter_options": ("处理设置不可用，保留原文", "Processing settings unavailable; original content retained"),
        "native_context_management": ("由宿主管理上下文", "Context is managed by the host"),
        "auxiliary_request": ("宿主辅助请求", "Host auxiliary request"),
        "subagent_request": ("子代理请求，保留原文", "Subagent request; original content retained"),
        "unassociated_session": ("会话身份待关联", "Session identity is not linked"),
        "missing_messages": ("请求中没有对话消息", "The request contains no conversation messages"),
        "stored_prefix_unreadable": ("已有上下文暂时无法读取，保留原文", "Saved context unavailable; original content retained"),
        "original_prefix_changed": ("较早上下文已变化，保留原文", "Earlier context changed; original content retained"),
        "prefix_store_unavailable": ("上下文存储暂时不可用，保留原文", "Context storage unavailable; original content retained"),
        "unsupported_endpoint": ("此类请求保持原样", "This request type is forwarded unchanged"),
        "unsupported_input": ("保留原有输入格式", "Original input format retained"),
        "invalid_tool_pairing": ("工具调用与结果需保持完整", "Tool calls and results must remain together"),
        "unsupported_tool_protocol": ("保留原有工具协议", "Original tool protocol retained"),
        "unsupported_message_fields": ("保留原有消息字段", "Original message fields retained"),
        "unsupported_message_role": ("保留原有消息角色", "Original message roles retained"),
        "unsupported_content": ("保留原有内容格式", "Original content format retained"),
        "unsupported_content_type": ("保留原有内容类型", "Original content types retained"),
        "unsupported_thinking_fields": ("保留原有推理内容与签名", "Original reasoning content and signatures retained"),
        "unsupported_text_fields": ("保留原有文本字段", "Original text fields retained"),
        "unsupported_tool_use": ("保留原有工具调用", "Original tool calls retained"),
        "unsupported_tool_result": ("保留原有工具结果", "Original tool results retained"),
        "unsupported_tool_result_content": ("保留原有工具结果内容", "Original tool result content retained"),
        "no_eligible_old_history": ("没有可处理的较早历史", "No eligible earlier history"),
        "history_fits_memory_budget": ("短上下文无需压缩", "Short context needs no compression"),
        "nonshrinking": ("处理后未变短", "Processing did not shorten the request"),
        "already_optimized_input": ("已是 TOMC 上下文", "The input is already TOMC context"),
        "compilation_failed": ("准备失败，保留原文", "Preparation failed; original content retained"),
        "native_compaction_active": ("宿主正在整理上下文", "The host is compacting context"),
        "native_compaction_completed": ("宿主刚完成整理", "The host just completed compaction"),
        "native_compaction_cooldown": ("宿主整理后的观察期", "Observation period after host compaction"),
        "unsupported_message_content": ("保留原有内容协议", "Original content protocol retained"),
        "unsupported_message_schema": ("保留原有消息协议", "Original message protocol retained"),
        "explicit_cache_control": ("保留缓存边界", "Cache boundaries retained"),
        "cache_control": ("保留缓存边界", "Cache boundaries retained"),
        "previous_response_id": ("保留服务端会话上下文", "Server-side conversation context retained"),
        "identity_unavailable": ("会话身份待关联", "Session identity is not linked"),
        "non_main_request": ("宿主辅助请求", "Host auxiliary request"),
        "native_compaction": ("保留宿主原生上下文整理", "Host native compaction retained"),
        "preparation_failed": ("准备失败，保留原文", "Preparation failed; original content retained"),
        "upstream_failed": ("上游返回失败", "Upstream request failed"),
        "transport_failed": ("连接或响应传输中断", "Connection or response stream interrupted"),
        "unsupported_request_encoding_or_json": ("保留原有编码与内容", "Original encoding and content retained"),
        "history_below_threshold": ("短上下文无需压缩", "Short context needs no compression"),
        "insufficient_old_history": ("没有足够的较早历史", "Not enough earlier history"),
        "protected_system_history": ("保留宿主系统指令与工具定义", "Host system instructions and tool definitions retained"),
        "retained_thinking_requires_original_prefix": ("保留推理签名所需的原始前缀", "Original prefix retained for signed reasoning"),
        "no_request_size_reduction": ("处理后未变短", "Processing did not shorten the request"),
        "server_side_or_incremental_history": ("保留服务端会话上下文", "Server-side conversation context retained"),
        "native_or_unknown_request": ("宿主整理或辅助请求，保留原文", "Host compaction or auxiliary request; original content retained"),
        "native_compaction_reset": ("宿主已整理上下文，旧映射已清除", "Host context compacted; old prefix mapping cleared"),
        "host_compaction_request": ("宿主自身的压缩请求，TOMC 不参与", "The host's own compaction request; TOMC not involved"),
        "native_compaction_state": ("宿主原生管理：含不透明压缩状态，TOMC 本次未压缩",
                                    "Host-managed: opaque compaction state present; TOMC did not compress this request"),
        "unknown_request_metadata": ("宿主请求元数据无法识别，保留原文", "Unrecognized host request metadata; original content retained"),
        "upstream_transport_failed": ("上游连接或响应中断", "Upstream connection or response interrupted"),
    }
    state = record.get("state")
    if record.get("stale"):
        return t("自动请求：准备状态已中断，等待新的请求事件", "Automatic requests: preparation interrupted; waiting for a new request")
    if state == "preparing":
        return t("正在检查 / 准备请求上下文", "Checking / preparing request context")
    if state == "prepared":
        return t("上下文已准备，等待上游转发", "Context prepared; waiting for upstream forwarding")
    if state == "forwarded":
        if record.get("reason") == "disabled_compatible_replay":
            return t("已转发已有签名兼容上下文 · 本会话关闭，不进行新的压缩",
                     "Existing context forwarded to preserve signatures · Session disabled; no new compression")
        if record.get("reason") == "replayed_prefix":
            return t("已复用并转发已有上下文", "Existing context reused and forwarded")
        return t("已观察到处理后请求转发", "A processed request was observed being forwarded")
    reason = record.get("reason")
    if reason == "client_disconnected":
        return t("请求已由宿主取消或断开", "Request cancelled or disconnected by the host")
    detail = t(*reasons[reason]) if reason in reasons else (reason or t("未提供原因", "No reason provided"))
    facts = protocol_detail_text(record.get("protocol_detail"), language)
    if facts:
        detail = f"{detail} · {facts}"
    if state == "passthrough":
        status = t("请求已原样转发", "Request forwarded unchanged") if record.get("sent") else t("请求将原样转发", "Request will be forwarded unchanged")
        return f"{status} · {detail}"
    return t("请求失败 · {detail}", "Request failed · {detail}", detail=detail)


def protocol_detail_text(detail, language=None):
    """Short structural facts the host declared; never request content."""
    if not isinstance(detail, dict):
        return ""
    parts = []
    trigger = {"manual": ("手动", "manual"), "auto": ("自动", "automatic"),
               "reactive": ("超长后触发", "after an overlong request")}.get(detail.get("compaction_trigger"))
    if trigger:
        parts.append(_tr(language, *trigger))
    phase = {"pre_turn": ("回合开始前", "before the turn"), "mid_turn": ("回合进行中", "mid-turn"),
             "standalone_turn": ("单独整理", "standalone")}.get(detail.get("compaction_phase"))
    if phase:
        parts.append(_tr(language, *phase))
    if detail.get("endpoint") == "responses_compact":
        parts.append(_tr(language, "独立压缩端点", "standalone compact endpoint"))
    if type(detail.get("window")) is int:
        parts.append(_tr(language, "压缩代次 {n}", "compaction generation {n}", n=detail["window"]))
    if type(detail.get("compaction_items")) is int:
        parts.append(_tr(language, "{n} 个不透明状态项", "{n} opaque state item(s)", n=detail["compaction_items"]))
    if detail.get("agent") == "subagent":
        parts.append(_tr(language, "子代理", "subagent"))
    return _tr(language, "，", ", ").join(parts)


def integration_snapshot():
    try:
        from .integration_status import get_integration_status

        status = get_integration_status()
        mode = status.get("mode", {})
        port = mode.get("gateway_port")
        if mode.get("id") == "automatic_request_gateway" and type(port) is int and 1024 <= port <= 65535:
            mode["gateway_service"] = "offline"
            try:
                opener = build_opener(ProxyHandler({}))
                with opener.open(f"http://127.0.0.1:{port}/health", timeout=0.25) as response:
                    data = json.loads(response.read(4096))
                if isinstance(data, dict) and data.get("service") == "tomc-gateway" and data.get("ready") is True:
                    mode["gateway_service"] = "online"
            except (OSError, ValueError):
                pass
        return status
    except (ImportError, OSError, ValueError):
        return {name: {"label": "状态暂不可读", "runtime_verified": False}
                for name in ("codex", "claude_code")}


class SessionNotice(QWidget):
    """Nonmodal notice bound to the displayed session, never desktop focus."""

    changed = Signal()

    def __init__(self, sessions, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.sessions = sessions
        self.language = getattr(parent, "language", None) or UiLanguage(sessions.path, self)
        self.target = None
        self.target_enabled = True
        self._shown_session = None
        self._error = None
        self.setObjectName("notice")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(STYLE + "QWidget#notice { border: 1px solid #E3DED3; border-radius: 12px; }")
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
        self.heading.setText(self.t("本会话 TOMC 默认开启，要关闭吗？", "TOMC is enabled for this session. Turn it off?")
                             if self.target_enabled else self.t("本会话 TOMC 已关闭", "TOMC is disabled for this session"))
        self.keep_button.setText(self.t("保持开启", "Keep enabled") if self.target_enabled else self.t("保持关闭", "Keep disabled"))
        self.toggle_button.setText(self.t("关闭本会话", "Disable session") if self.target_enabled else self.t("重新开启本会话", "Re-enable session"))
        session = self._shown_session
        if session:
            title = session.get("title") or session["session_id"]
            short_title = title if len(title) <= 72 else title[:71] + "…"
            detail = f"{host_label(session['host'], self.language)} · {short_title}"
            self.detail.setToolTip(self.t(
                "最近宿主事件：{event}\n{title}\n根据宿主事件显示，不表示已观测桌面焦点或已经压缩。",
                "Latest host event: {event}\n{title}\nBased on host events; this does not prove desktop focus or compression.",
                event=session.get("event") or self.t("未提供", "Not provided"), title=title))
            if self.target_enabled:
                detail += self.t("\n不操作将保持开启；只处理实际经 TOMC 的请求。",
                                 "\nStays enabled unless changed; only requests routed through TOMC are processed.")
                if not session.get("effective_enabled", True):
                    detail += self.t("全局处理当前已暂停。", " Processing is paused globally.")
            else:
                detail += self.t("\n此会话保留关闭设置，可在这里重新开启。", "\nThis session stays disabled. You can re-enable it here.")
            self.detail.setText(detail)
        if self._error:
            self.detail.setText(self.t("设置未保存：{error}", "Settings were not saved: {error}", error=self._error))
        self.adjustSize()
        if self.isVisible() and self.screen():
            area = self.screen().availableGeometry()
            self.move(min(self.x(), area.right() - self.width()), min(self.y(), area.bottom() - self.height()))

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


class ContextLibraryDialog(QDialog):
    """Browse actual snapshots, portable handoffs, and registered session settings."""

    changed = Signal()

    def __init__(self, path, parent=None, *, library=None, sessions=None,
                 integrations=None, pricing="load", activity=None):
        super().__init__(parent)
        self.language = getattr(parent, "language", None) or UiLanguage(path, self)
        if library is None:
            from .context_library import ContextLibrary

            library = ContextLibrary(path)
        if sessions is None:
            from .session_store import SessionStore

            sessions = SessionStore(path)
        self.library, self.sessions = library, sessions
        self.activity = activity or RequestActivity(path)
        self.integrations = integrations
        self.pricing = load_pricing() if pricing == "load" else pricing
        self._load_pricing = pricing == "load"
        self.records = []
        self.selected_record = None
        self._refreshing = False
        self._message_spec = ("上下文保存在本机；复制与导出只处理你选中的版本。",
                              "Contexts stay on this device. Copy and export use only the selected version.", {})
        self.setWindowTitle("TOMC · 上下文与接续")
        self.setStyleSheet(STYLE)
        self.resize(980, 730)
        self.setMinimumSize(800, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        title = text_label("上下文与接续")
        title.setObjectName("title")
        heading.addWidget(title)
        heading.addStretch()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh)
        heading.addWidget(self.refresh_button)
        layout.addLayout(heading)
        self.mode = text_label("TOMC · 请求接入状态待读取", muted=True)
        layout.addWidget(self.mode)
        self.activity_status = text_label("自动请求：尚未观察到代理请求", muted=True)
        layout.addWidget(self.activity_status)
        status_row = QHBoxLayout()
        self.integration_labels = {}
        for host in ("codex", "claude_code"):
            label = text_label()
            label.setObjectName("status")
            status_row.addWidget(label, 1)
            self.integration_labels[host] = label
        layout.addLayout(status_row)
        controls = QHBoxLayout()
        self.enabled = QCheckBox("TOMC 处理")
        self.enabled.setToolTip("全局暂停后，新准备请求停止；已有上下文仍可浏览和导出。")
        self.save_contexts = QCheckBox("保存上下文记录")
        self.save_contexts.setToolTip("只控制之后的正文保存；不删除已有记录，不关闭 TOMC 处理。")
        self.enabled.toggled.connect(lambda value: self.change_setting("enabled", value))
        self.save_contexts.toggled.connect(lambda value: self.change_setting("save_contexts", value))
        controls.addWidget(self.enabled)
        controls.addSpacing(20)
        controls.addWidget(self.save_contexts)
        controls.addStretch()
        controls.addWidget(text_label("新会话默认开启，可单独关闭", muted=True))
        layout.addLayout(controls)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.make_context_tab(), "已处理上下文")
        self.tabs.addTab(self.make_session_tab(), "已登记会话")
        layout.addWidget(self.tabs, 1)
        self.message = text_label("上下文保存在本机；复制与导出只处理你选中的版本。", muted=True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.message)
        self._static_bindings = _static_translations(self)
        self.language.changed.connect(self.retranslate)
        self.retranslate()

    def t(self, zh, en, **values):
        return self.language.tr(zh, en, **values)

    def show_message(self, zh, en, **values):
        self._message_spec = (zh, en, values)
        self.message.setText(self.t(zh, en, **values))

    def retranslate(self, *_):
        for setter, zh, en in self._static_bindings:
            setter(self.t(zh, en))
        self.tabs.setTabText(0, self.t("已处理上下文", "Prepared contexts"))
        self.tabs.setTabText(1, self.t("已登记会话", "Registered sessions"))
        self.content_tabs.setTabText(0, self.t("上下文正文", "Context content"))
        self.content_tabs.setTabText(1, self.t("任务与来源", "Task and source"))
        self.host_filter.setItemText(0, self.t("全部宿主", "All hosts"))
        self.host_filter.setItemText(3, self.t("未关联会话", "Unlinked sessions"))
        self.refresh()
        zh, en, values = self._message_spec
        self.message.setText(self.t(zh, en, **values))

    def make_context_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索标题、来源或会话")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_records)
        self.host_filter = QComboBox()
        self.host_filter.addItem("全部宿主", "")
        self.host_filter.addItem("Codex", "codex")
        self.host_filter.addItem("Claude Code", "claude")
        self.host_filter.addItem("未关联会话", "unlinked")
        self.host_filter.currentIndexChanged.connect(self.filter_records)
        self.import_button = QPushButton("导入上下文包")
        self.import_button.clicked.connect(self.import_bundle)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.host_filter)
        filters.addWidget(self.import_button)
        layout.addLayout(filters)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.context_list = QListWidget()
        self.context_list.setWordWrap(True)
        self.context_list.setAccessibleName("已处理上下文列表")
        self.context_list.currentItemChanged.connect(self.select_context)
        split.addWidget(self.context_list)
        self.preview_stack = QStackedWidget()
        self.empty = text_label("暂无处理记录\n\n成功准备并保存的上下文会出现在这里。\n旧版数字统计不含正文，无法还原历史上下文。", muted=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_stack.addWidget(self.empty)
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(14, 0, 0, 0)
        self.record_title = text_label()
        self.record_title.setStyleSheet("font-weight: 600; font-size: 15px;")
        self.record_meta = text_label(muted=True)
        self.record_tokens = text_label()
        self.record_tokens.setStyleSheet("font-size: 14px; color: #345743;")
        self.record_cost = text_label(muted=True)
        self.request_status = text_label("此快照的请求用量 / 账单差异：未关联测量", muted=True)
        for widget in (self.record_title, self.record_meta, self.record_tokens,
                       self.record_cost, self.request_status):
            detail_layout.addWidget(widget)
        self.content_tabs = QTabWidget()
        self.memory = QPlainTextEdit()
        self.memory.setReadOnly(True)
        self.memory.setAccessibleName("选中上下文正文，只读")
        self.task = QPlainTextEdit()
        self.task.setReadOnly(True)
        self.task.setAccessibleName("原任务与记录信息，只读")
        self.content_tabs.addTab(self.memory, "上下文正文")
        self.content_tabs.addTab(self.task, "任务与来源")
        detail_layout.addWidget(self.content_tabs, 1)
        self.preview_stack.addWidget(detail)
        split.addWidget(self.preview_stack)
        split.setSizes([285, 625])
        layout.addWidget(split, 1)
        actions = QHBoxLayout()
        self.count_label = text_label(muted=True)
        actions.addWidget(self.count_label, 1)
        self.rename_button = QPushButton("重命名")
        self.rename_button.clicked.connect(self.rename_context)
        self.delete_button = QPushButton("删除")
        self.delete_button.clicked.connect(self.delete_context)
        self.export_button = QPushButton("导出便携包")
        self.export_button.clicked.connect(self.export_context)
        self.copy_button = QPushButton("复制接续提示词")
        self.copy_button.setObjectName("primary")
        self.copy_button.clicked.connect(self.copy_handoff)
        self.record_buttons = (self.rename_button, self.delete_button, self.export_button,
                               self.copy_button)
        for button in self.record_buttons:
            button.setEnabled(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        return page

    def make_session_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(text_label(
            "仅显示已收到宿主事件的会话；登记不代表已压缩。纯界面焦点切换无法可靠观测。", muted=True))
        self.session_list = QListWidget()
        self.session_list.setWordWrap(True)
        self.session_list.setAccessibleName("已登记会话及本会话开关")
        self.session_list.itemChanged.connect(self.change_session)
        layout.addWidget(self.session_list, 1)
        self.session_note = text_label(muted=True)
        layout.addWidget(self.session_note)
        layout.addWidget(text_label(
            "存在关闭会话时，身份未关联的准备会暂停，需重新加载宿主接入。", muted=True))
        return page

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
            self.refresh_sessions()
            status = self.integrations if self.integrations is not None else integration_snapshot()
            activity_summary = self.activity.summary()
            observed_hosts = {row["host"] for row in activity_summary["by_host"] if row["sent_requests"]}
            latest = self.activity.last()
            if latest and latest["state"] == "preparing" and self.activity.active() is None:
                latest = {**latest, "stale": True}
            mode = status.get("mode", {})
            configured = mode.get("id") == "automatic_request_gateway"
            if configured:
                mode_text = (self.t("自动接入已配置，重开客户端后等待请求", "Automatic routing configured; reopen the client and send a request")
                             if not activity_summary["sent_requests"] else
                             self.t("自动接入已配置 · 已观察到本地代理转发", "Automatic routing configured · Local forwarding observed"))
                service = {
                    "online": (" · 转发服务可达", " · Gateway reachable"),
                    "offline": (" · 转发服务不可达，请启动服务", " · Gateway unreachable; start the service"),
                }.get(mode.get("gateway_service"), (" · 转发服务待核验", " · Gateway status unverified"))
                mode_text += self.t(*service)
            else:
                mode_text = (self.t("按需工具可用 · 代理尚未观察到实际转发", "On-demand tools available · No gateway forwarding observed")
                             if not activity_summary["sent_requests"] else
                             self.t("已观察到本地代理转发 · 仅覆盖实际经过代理的请求", "Local forwarding observed · Only requests routed through the gateway are covered"))
            self.mode.setText(mode_text)
            self.mode.setToolTip(self.t(
                "服务可达只证明代理正在运行，当前对话接入以实际请求事件为准。短历史和不支持的请求保留原文。",
                "A reachable service proves only that the gateway is running. Actual request events establish session routing. Short or unsupported requests remain unchanged."))
            detail = request_activity_text(latest, self.language)
            if latest:
                detail += f" · {host_label(latest['host'], self.language)} · {short_date(latest['started_utc'], self.language)} UTC"
                before, after = latest.get("before_tokens"), latest.get("after_tokens")
                if before is not None and after is not None:
                    detail += self.t("\n本次请求文本估算 {before:,} → {after:,} tokens",
                                     "\nRequest text estimate {before:,} → {after:,} tokens", before=before, after=after)
                if latest.get("provider_input_tokens") is not None:
                    detail += self.t(" · 实测 provider 输入 {count:,} tokens", " · Measured provider input {count:,} tokens", count=latest["provider_input_tokens"])
                    if latest.get("provider_cached_tokens") is not None:
                        detail += self.t("（缓存 {count:,}）", " (cached {count:,})", count=latest["provider_cached_tokens"])
                else:
                    detail += self.t(" · provider 用量尚未返回", " · Provider usage not yet returned")
                detail += self.t("；实测用量不是节省差额。", "; measured usage is not the amount saved.")
            self.activity_status.setText(detail)
            for host, label in self.integration_labels.items():
                item = status.get(host, {})
                runtime = self.t("运行已验证", "Runtime verified") if item.get("runtime_verified") else self.t("连接待验证", "Connection unverified")
                if ("claude" if host == "claude_code" else host) in observed_hosts:
                    runtime = self.t("代理转发曾被观察", "Gateway forwarding observed")
                state = item.get("state") or {"已配置": "enabled", "配置已启用": "enabled", "未配置": "not_configured", "已禁用": "disabled"}.get(item.get("label"), "unknown")
                labels = {"enabled": ("配置已启用", "Configuration enabled"), "not_configured": ("未配置", "Not configured"),
                          "disabled": ("已禁用", "Disabled"), "unknown": ("未知", "Unknown")}
                configured_label = self.t(*labels.get(state, labels["unknown"]))
                if ("claude" if host == "claude_code" else host) in mode.get("configured_hosts", []):
                    configured_label = self.t("自动接入已配置", "Automatic routing configured")
                label.setText(f"{host_label(host, self.language)} · {configured_label} · {runtime}")
                label.setToolTip(self.t("仅检查用户级配置，未检查项目或会话覆盖。配置可用不等于当前会话已经连接。",
                                       "Only user-level configuration is checked, not project or session overrides. Configuration alone does not prove that this session is connected."))
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.show_message("目录暂不可读：{error}", "The library cannot be read right now: {error}", error=str(exc))
            self.records = []
        finally:
            self._refreshing = False
        self.filter_records(select_id=selected_id)

    def refresh_sessions(self):
        self.session_list.blockSignals(True)
        try:
            self.session_list.clear()
            records = self.sessions.list()
            for row in records:
                title = row.get("title") or row["session_id"]
                state = self.t("开启", "Enabled") if row.get("enabled", True) else self.t("已关闭", "Disabled")
                if row.get("enabled", True) and not row.get("effective_enabled", True):
                    state += self.t(" · 全局暂停", " · Paused globally")
                line = self.t("最近事件 {stamp} UTC", "Latest event {stamp} UTC", stamp=short_date(row.get("last_seen"), self.language))
                item = QListWidgetItem(f"{title}\n{host_label(row['host'], self.language)} · {state} · {line}")
                item.setData(Qt.ItemDataRole.UserRole, (row["host"], row["session_id"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if row.get("enabled", True) else Qt.CheckState.Unchecked)
                item.setToolTip(self.t("会话 ID：{identity}\n项目：{project}\n复选框只控制此会话，不修改宿主权限。",
                                      "Session ID: {identity}\nProject: {project}\nThis checkbox controls only this session, not host permissions.",
                                      identity=row["session_id"], project=row.get("project") or self.t("未提供", "Not provided")))
                self.session_list.addItem(item)
            self.session_note.setText(self.t(
                "{count} 个已登记会话；勾选表示允许 TOMC 处理。全局暂停时，已开启会话也不会处理。",
                "Registered sessions: {count}. Checked sessions allow TOMC processing; a global pause also stops enabled sessions.", count=len(records))
                if records else self.t("尚未收到会话事件。配置 hooks 后，新建、恢复或活动事件可登记会话；旧聊天不会凭空补全。",
                                       "No session events received yet. After hooks are configured, start, resume or activity events register sessions. Old chats are not reconstructed."))
        finally:
            self.session_list.blockSignals(False)

    def filter_records(self, *args, select_id=None):
        query = self.search.text().casefold().strip()
        host = self.host_filter.currentData()
        rows = []
        for row in self.records:
            actual_host = row.get("host") or ""
            if host == "unlinked" and row.get("session_id"):
                continue
            if host == "codex" and actual_host != "codex":
                continue
            if host == "claude" and actual_host not in ("claude", "claude_code", "claude-code"):
                continue
            searchable = " ".join(str(row.get(k) or "") for k in ("title", "source", "notebook_name", "session_id", "host", "origin_host"))
            if query and query not in searchable.casefold():
                continue
            rows.append(row)
        self.context_list.blockSignals(True)
        self.context_list.clear()
        selected = None
        for row in rows:
            source_host = row.get("host") or row.get("origin_host")
            origin = host_label(source_host, self.language)
            if row.get("origin_host") and not row.get("host"):
                origin += self.t(" 来源 · 本机未关联", " origin · Not linked locally")
            title = str(row.get("title") or self.t("未命名上下文", "Untitled context")).replace("\n", " ")
            item = QListWidgetItem(f"{title}\n{origin} · {short_date(row.get('created_utc'), self.language)} UTC")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setToolTip(title)
            self.context_list.addItem(item)
            if row["id"] == select_id:
                selected = item
        self.context_list.blockSignals(False)
        self.count_label.setText(self.t("{count} 条上下文", "Contexts: {count}", count=len(rows)))
        if rows:
            self.context_list.setCurrentItem(selected or self.context_list.item(0))
        else:
            self.select_context(None)
            self.empty.setText(self.t("没有匹配的记录\n\n试试其他标题、来源或宿主。", "No matching records\n\nTry another title, source or host.")
                               if self.records else self.t("暂无处理记录\n\n成功准备并保存的上下文会出现在这里。\n旧版数字统计不含正文，无法还原历史上下文。",
                                                          "No prepared contexts yet\n\nSaved contexts will appear here after preparation.\nOlder numeric statistics contain no text and cannot restore past contexts."))

    def select_context(self, current, previous=None):
        self.selected_record = None
        if current:
            try:
                self.selected_record = self.library.get(current.data(Qt.ItemDataRole.UserRole))
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                self.show_message("记录暂不可读：{error}", "This record cannot be read right now: {error}", error=str(exc))
        row = self.selected_record
        for button in self.record_buttons:
            button.setEnabled(bool(row))
        self.preview_stack.setCurrentIndex(1 if row else 0)
        if not row:
            self.memory.clear()
            self.task.clear()
            return
        self.record_title.setText(row.get("title") or self.t("未命名上下文", "Untitled context"))
        self.record_meta.setText(f"{host_label(row.get('host'), self.language)} · {short_date(row.get('created_utc'), self.language)} UTC\n" + self.t(
            "来源：{source} · 计数口径：{counter}", "Source: {source} · Counter: {counter}",
            source=row.get("source") or self.t("未提供", "Not provided"), counter=row.get("counter") or self.t("未知", "Unknown")))
        before, after = row["input_estimated_tokens"], row["output_estimated_tokens"]
        delta = before - after
        direction = self.t("减少", "decrease") if delta >= 0 else self.t("增加", "increase")
        self.record_tokens.setText(self.t("上下文估算  {before:,} → {after:,} tokens · {direction} {delta:,}",
                                         "Context estimate  {before:,} → {after:,} tokens · {direction} {delta:,}",
                                         before=before, after=after, direction=direction, delta=abs(delta)))
        if self.pricing:
            value = input_value(delta, self.pricing)
            model = (self.pricing.get("label") if self.language.code == "zh" else None) or self.pricing.get("model") or self.t("所选模型", "Selected model")
            self.record_cost.setText(self.t("参考输入金额{direction} {value} · {model}", "Reference input value {direction} {value} · {model}",
                                           direction=direction, value=dollars(value), model=model))
        else:
            self.record_cost.setText(self.t("参考金额：费率待确认；可在小猫的「模型与估价」中选择。",
                                           "Reference value: rate unconfirmed. Choose one in the companion's Model and pricing settings."))
        self.record_cost.setToolTip(explanation(self.pricing, self.language))
        self.memory.setPlainText(row.get("memory", ""))
        self.task.setPlainText(self.t(
            "原任务\n{task}\n\n快照 ID：{identity}\n准备 ID：{preparation}\n预算：{budget} tokens\n本机会话：{session}\n来源宿主：{host}\n笔记本：{notebook}\n\n这是为原任务准备的上下文，可能有遗漏，不是完整聊天的无损副本。\n此快照的数量与金额均为估算；请求转发与实测用量见上方请求记录。未测量账单差异。",
            "Original task\n{task}\n\nSnapshot ID: {identity}\nPreparation ID: {preparation}\nBudget: {budget} tokens\nLocal session: {session}\nSource host: {host}\nNotebook: {notebook}\n\nThis context was prepared for the original task and may omit details. It is not a lossless copy of the full conversation.\nSnapshot counts and values are estimates. Request forwarding and measured usage appear above; billing differences have not been measured.",
            task=row.get("task") or self.t("未记录", "Not recorded"), identity=row["id"],
            preparation=row.get("preparation_id") or self.t("未提供", "Not provided"),
            budget=row.get("budget", self.t("未提供", "Not provided")), session=row.get("session_id") or self.t("未关联", "Unlinked"),
            host=host_label(row.get("origin_host") or row.get("host"), self.language), notebook=row.get("notebook_name") or self.t("未提供", "Not provided")))

    def change_setting(self, name, value):
        if self._refreshing:
            return
        try:
            self.sessions.update_settings(**{name: value})
            self.show_message("设置已保存。处理开关与正文记录开关彼此独立。", "Settings saved. Processing and content storage are independent switches.")
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.show_message("设置未保存：{error}", "Settings were not saved: {error}", error=str(exc))
        self.refresh()
        self.changed.emit()

    def change_session(self, item):
        if self._refreshing:
            return
        host, session_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        try:
            self.sessions.set_enabled(host, session_id, enabled)
            if enabled:
                self.show_message("本会话 TOMC 已开启；其他会话设置不变。", "TOMC is enabled for this session; other sessions are unchanged.")
            else:
                self.show_message("本会话 TOMC 已关闭；其他会话设置不变。", "TOMC is disabled for this session; other sessions are unchanged.")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("设置未保存：{error}", "Settings were not saved: {error}", error=str(exc))
        self.refresh_sessions()
        self.changed.emit()

    def copy_handoff(self):
        if not self.selected_record:
            return
        try:
            prompt = self.library.handoff_prompt(self.selected_record["id"], inline=True, language=self.language.code)
            QApplication.clipboard().setText(prompt)
            self.show_message("已复制自包含接续提示词（{count:,} 字符），未截断。可粘贴到另一个 Agent。",
                              "Copied a complete handoff prompt ({count:,} characters), without truncation. Paste it into another agent.", count=len(prompt))
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("复制失败：{error}", "Copy failed: {error}", error=str(exc))

    def export_context(self):
        if not self.selected_record:
            return
        folder = QFileDialog.getExistingDirectory(self, self.t("选择便携包保存目录", "Choose a folder for the portable bundle"))
        if not folder:
            return
        try:
            destination = self.library.export(self.selected_record["id"], Path(folder), language=self.language.code)
            self.show_message("已导出：{path}。包含正文、接续说明与元数据；未上传。",
                              "Exported to {path}. Includes context, handoff instructions and metadata; nothing was uploaded.", path=destination)
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("导出失败：{error}", "Export failed: {error}", error=str(exc))

    def import_bundle(self):
        folder = QFileDialog.getExistingDirectory(self, self.t("选择包含 metadata.json 的上下文包目录", "Choose a context bundle folder containing metadata.json"))
        if not folder:
            return
        try:
            row = self.library.import_bundle(Path(folder))
            self.search.clear()
            self.host_filter.setCurrentIndex(0)
            self.refresh(select_id=row["id"])
            if row.get("imported"):
                self.show_message("上下文已导入，未计为新的压缩，也未绑定本机会话。", "Context imported; it is not counted as new compression or linked to a local session.")
            else:
                self.show_message("这个上下文已经存在，未重复导入。", "This context already exists; no duplicate was imported.")
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
            self.show_message("名称已更新，快照正文与处理数据保持原样。", "Name updated. Snapshot content and preparation data are unchanged.")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("重命名失败：{error}", "Rename failed: {error}", error=str(exc))

    def delete_context(self):
        if not self.selected_record:
            return
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        def translate(*_):
            dialog.setWindowTitle(self.t("删除本地上下文", "Delete local context"))
            dialog.setText(self.t("删除选中的本地快照？\n既有数字统计、宿主聊天和已导出的文件不受影响。",
                                  "Delete the selected local snapshot?\nNumeric statistics, host chats and exported files will remain unchanged."))
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
            self.show_message("本地快照已删除；数字统计、宿主聊天和已导出文件保留。",
                              "Local snapshot deleted. Numeric statistics, host chats and exported files are retained.")
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
