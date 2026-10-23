"""Local context browser and session controls; no model or host UI automation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

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


def host_label(host):
    return {"codex": "Codex", "claude_code": "Claude Code", "claude-code": "Claude Code",
            "claude": "Claude Code"}.get(host, host or "未关联会话")


def short_date(value):
    return str(value or "时间未知").replace("T", " ").replace("+00:00", "Z")[:19]


def integration_snapshot():
    try:
        from .integration_status import get_integration_status

        return get_integration_status()
    except (ImportError, OSError, ValueError):
        return {name: {"label": "状态暂不可读", "runtime_verified": False}
                for name in ("codex", "claude_code")}


class SessionNotice(QWidget):
    """Nonmodal notice bound to the session that was displayed, never UI focus."""

    changed = Signal()

    def __init__(self, sessions, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.sessions = sessions
        self.target = None
        self.target_enabled = True
        self.setObjectName("notice")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setWindowTitle("TOMC 会话状态")
        self.setStyleSheet(STYLE + "QWidget#notice { border: 1px solid #E3DED3; border-radius: 12px; }")
        self.setFixedWidth(330)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        self.heading = text_label()
        self.heading.setStyleSheet("font-weight: 600; font-size: 13px; color: #345743;")
        self.detail = text_label(muted=True)
        layout.addWidget(self.heading)
        layout.addWidget(self.detail)
        actions = QHBoxLayout()
        self.keep_button = QPushButton("保持开启")
        self.keep_button.clicked.connect(self.hide)
        self.toggle_button = QPushButton("关闭本会话")
        self.toggle_button.clicked.connect(self.toggle_session)
        actions.addWidget(self.keep_button)
        actions.addWidget(self.toggle_button)
        layout.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def present(self, session):
        self.target = (session["host"], session["session_id"])
        self.target_enabled = bool(session.get("enabled", True))
        self.heading.setText("本会话 TOMC 默认开启，要关闭吗？" if self.target_enabled
                             else "本会话 TOMC 已关闭")
        title = session.get("title") or session["session_id"]
        short_title = title if len(title) <= 72 else title[:71] + "…"
        detail = f"{host_label(session['host'])} · {short_title}"
        self.detail.setToolTip(f"最近宿主事件：{session.get('event', '未提供')}\n{title}\n"
                               "根据宿主事件显示，不表示已观测桌面焦点或已经压缩。")
        if self.target_enabled:
            detail += "\n不操作将保持开启；当前按需准备上下文。"
            if not session.get("effective_enabled", True):
                detail += "全局处理当前已暂停。"
        else:
            detail += "\n此会话保留关闭设置，可在这里重新开启。"
        self.detail.setText(detail)
        self.keep_button.setText("保持开启" if self.target_enabled else "保持关闭")
        self.toggle_button.setText("关闭本会话" if self.target_enabled else "重新开启本会话")
        self.adjustSize()
        self.show()
        self.timer.start(12000)

    def toggle_session(self):
        if not self.target:
            return
        try:
            # Bind to the displayed identity, even if a newer event is now in the DB.
            self.sessions.set_enabled(*self.target, not self.target_enabled)
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.detail.setText(f"设置未保存：{exc}")
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
                 integrations=None, pricing="load"):
        super().__init__(parent)
        if library is None:
            from .context_library import ContextLibrary

            library = ContextLibrary(path)
        if sessions is None:
            from .session_store import SessionStore

            sessions = SessionStore(path)
        self.library, self.sessions = library, sessions
        self.integrations = integrations
        self.pricing = load_pricing() if pricing == "load" else pricing
        self._load_pricing = pricing == "load"
        self.records = []
        self.selected_record = None
        self._refreshing = False
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
        self.mode = text_label("按需工具 · 自动全对话请求压缩尚未接入", muted=True)
        layout.addWidget(self.mode)
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
        controls.addWidget(text_label("新会话默认开启，可单独关闭", muted=True, wrap=False))
        layout.addLayout(controls)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.make_context_tab(), "已处理上下文")
        self.tabs.addTab(self.make_session_tab(), "已登记会话")
        layout.addWidget(self.tabs, 1)
        self.message = text_label("上下文保存在本机；复制与导出只处理你选中的版本。", muted=True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.message)
        self.refresh()

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
        self.request_status = text_label("实际请求输入 / 账单差异：未接入测量", muted=True)
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
            for host, label in self.integration_labels.items():
                item = status.get(host, {})
                runtime = "运行已验证" if item.get("runtime_verified") else "连接待验证"
                label.setText(f"{host_label(host)} · {item.get('label', '未取得状态')} · {runtime}")
                label.setToolTip(item.get("detail", "") + "\n配置可用不等于当前会话已经连接。")
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.message.setText(f"目录暂不可读：{exc}")
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
                state = "开启" if row.get("enabled", True) else "已关闭"
                if row.get("enabled", True) and not row.get("effective_enabled", True):
                    state += " · 全局暂停"
                item = QListWidgetItem(f"{title}\n{host_label(row['host'])} · {state} · 最近事件 {short_date(row.get('last_seen'))} UTC")
                item.setData(Qt.ItemDataRole.UserRole, (row["host"], row["session_id"]))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if row.get("enabled", True)
                                   else Qt.CheckState.Unchecked)
                item.setToolTip(f"会话 ID：{row['session_id']}\n项目：{row.get('project') or '未提供'}\n复选框只控制此会话，不修改宿主权限。")
                self.session_list.addItem(item)
            self.session_note.setText(
                f"{len(records)} 个已登记会话；勾选表示允许 TOMC 处理。全局暂停时，已开启会话也不会处理。"
                if records else "尚未收到会话事件。配置 hooks 后，新建、恢复或活动事件可登记会话；旧聊天不会凭空补全。")
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
            searchable = " ".join(str(row.get(k) or "") for k in (
                "title", "source", "notebook_name", "session_id", "host", "origin_host"))
            if query and query not in searchable.casefold():
                continue
            rows.append(row)
        self.context_list.blockSignals(True)
        self.context_list.clear()
        selected = None
        for row in rows:
            source_host = row.get("host") or row.get("origin_host")
            origin = host_label(source_host)
            if row.get("origin_host") and not row.get("host"):
                origin += " 来源 · 本机未关联"
            title = str(row.get("title") or "未命名上下文").replace("\n", " ")
            item = QListWidgetItem(f"{title}\n{origin} · {short_date(row.get('created_utc'))} UTC")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setToolTip(title)
            self.context_list.addItem(item)
            if row["id"] == select_id:
                selected = item
        self.context_list.blockSignals(False)
        self.count_label.setText(f"{len(rows)} 条上下文")
        if rows:
            self.context_list.setCurrentItem(selected or self.context_list.item(0))
        else:
            self.select_context(None)
            self.empty.setText("没有匹配的记录\n\n试试其他标题、来源或宿主。" if self.records
                               else "暂无处理记录\n\n成功准备并保存的上下文会出现在这里。\n旧版数字统计不含正文，无法还原历史上下文。")

    def select_context(self, current, previous=None):
        self.selected_record = None
        if current:
            try:
                self.selected_record = self.library.get(current.data(Qt.ItemDataRole.UserRole))
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                self.message.setText(f"记录暂不可读：{exc}")
        row = self.selected_record
        for button in self.record_buttons:
            button.setEnabled(bool(row))
        self.preview_stack.setCurrentIndex(1 if row else 0)
        if not row:
            self.memory.clear()
            self.task.clear()
            return
        self.record_title.setText(row.get("title") or "未命名上下文")
        self.record_meta.setText(f"{host_label(row.get('host'))} · {short_date(row.get('created_utc'))} UTC\n"
                                 f"来源：{row.get('source') or '未提供'} · 计数口径：{row.get('counter') or '未知'}")
        before, after = row["input_estimated_tokens"], row["output_estimated_tokens"]
        delta = before - after
        direction = "减少" if delta >= 0 else "增加"
        self.record_tokens.setText(f"上下文估算  {before:,} → {after:,} tokens · {direction} {abs(delta):,}")
        if self.pricing:
            value = input_value(delta, self.pricing)
            self.record_cost.setText(f"参考输入金额{direction} {dollars(value)} · {self.pricing.get('label', self.pricing.get('model', '所选模型'))}")
        else:
            self.record_cost.setText("参考金额：费率待确认；可在小猫的「模型与估价」中选择。")
        self.record_cost.setToolTip(explanation(self.pricing))
        self.memory.setPlainText(row.get("memory", ""))
        self.task.setPlainText(
            f"原任务\n{row.get('task') or '未记录'}\n\n"
            f"快照 ID：{row['id']}\n准备 ID：{row.get('preparation_id') or '未提供'}\n"
            f"预算：{row.get('budget', '未提供')} tokens\n"
            f"本机会话：{row.get('session_id') or '未关联'}\n"
            f"来源宿主：{host_label(row.get('origin_host') or row.get('host'))}\n"
            f"笔记本：{row.get('notebook_name') or '未提供'}\n\n"
            "这是为原任务准备的上下文，可能有遗漏，不是完整聊天的无损副本。\n"
            "文本数量与金额均为估算；没有证据表明已替换宿主请求，也未测量账单差异。")

    def change_setting(self, name, value):
        if self._refreshing:
            return
        try:
            self.sessions.update_settings(**{name: value})
            self.message.setText("设置已保存。处理开关与正文记录开关彼此独立。")
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.message.setText(f"设置未保存：{exc}")
        self.refresh()
        self.changed.emit()

    def change_session(self, item):
        if self._refreshing:
            return
        host, session_id = item.data(Qt.ItemDataRole.UserRole)
        enabled = item.checkState() == Qt.CheckState.Checked
        try:
            self.sessions.set_enabled(host, session_id, enabled)
            self.message.setText(f"本会话 TOMC 已{'开启' if enabled else '关闭'}；其他会话设置不变。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"设置未保存：{exc}")
        self.refresh_sessions()
        self.changed.emit()

    def copy_handoff(self):
        if not self.selected_record:
            return
        try:
            prompt = self.library.handoff_prompt(self.selected_record["id"], inline=True)
            QApplication.clipboard().setText(prompt)
            self.message.setText(f"已复制自包含接续提示词（{len(prompt):,} 字符），未截断。可粘贴到另一个 Agent。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"复制失败：{exc}")

    def export_context(self):
        if not self.selected_record:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择便携包保存目录")
        if not folder:
            return
        try:
            destination = self.library.export(self.selected_record["id"], Path(folder))
            self.message.setText(f"已导出：{destination}。包含正文、接续说明与元数据；未上传。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"导出失败：{exc}")

    def import_bundle(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含 metadata.json 的上下文包目录")
        if not folder:
            return
        try:
            row = self.library.import_bundle(Path(folder))
            self.search.clear()
            self.host_filter.setCurrentIndex(0)
            self.refresh(select_id=row["id"])
            self.message.setText("上下文已导入，未计为新的压缩，也未绑定本机会话。" if row.get("imported")
                                 else "这个上下文已经存在，未重复导入。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"导入失败：{exc}")

    def rename_context(self):
        if not self.selected_record:
            return
        title, accepted = QInputDialog.getText(self, "重命名上下文", "显示名称", text=self.selected_record.get("title", ""))
        if not accepted or not title.strip():
            return
        try:
            self.library.rename(self.selected_record["id"], title.strip())
            self.refresh()
            self.message.setText("名称已更新，快照正文与处理数据保持原样。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"重命名失败：{exc}")

    def delete_context(self):
        if not self.selected_record:
            return
        answer = QMessageBox.question(
            self, "删除本地上下文", "删除选中的本地快照？\n既有数字统计、宿主聊天和已导出的文件不受影响。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.library.delete(self.selected_record["id"])
            self.refresh()
            self.message.setText("本地快照已删除；数字统计、宿主聊天和已导出文件保留。")
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.message.setText(f"删除失败：{exc}")


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
