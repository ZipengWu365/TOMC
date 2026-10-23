"""Native companion with local context/session controls; never captures the desktop."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from collections import deque
from pathlib import Path

from PySide6.QtCore import QLockFile, QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .cost_estimate import dollars, explanation, input_value, load_pricing
from .oasis_qt import OasisCelebration
from .pet_art import ACTIVE_WIDTH, IDLE_WIDTH, PetArt
from .pet_growth import growth_state
from .quota import context_percent, percent_text
from .quota_qt import QuotaReader
from .usage import UsageStore
from .usage_widget import display_values

STYLE = """
QWidget { color: #443B35; font-family: 'Microsoft YaHei UI'; font-size: 12px; }
QLabel { background: transparent; }
QPushButton { background: transparent; border: none; border-radius: 10px; padding: 6px; }
QPushButton:hover { background: #EEE9DF; }
QPushButton:focus { border: 1px solid #507461; }
QPushButton:checked { background: #E4ECE5; color: #345743; }
QProgressBar { border: none; background: #E7E1D7; border-radius: 2px; }
QProgressBar::chunk { background: #507461; border-radius: 2px; }
"""


def load_preview_fonts():
    """Qt's offscreen Windows backend has no automatic system font discovery."""
    if QApplication.platformName() == "offscreen" and sys.platform == "win32":
        for name in ("msyh.ttc", "segoeui.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / name))


def label(text="", size=12, color="#443B35", bold=False):
    item = QLabel(text)
    item.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {600 if bold else 400};")
    return item


class DismissButton(QPushButton):
    """Draw the same quiet close mark at every display scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setAccessibleName("收起统计")
        self.setToolTip("收起统计 · Esc")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#796D60"), 1.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(10, 10, 18, 18)
        painter.drawLine(18, 10, 10, 18)


class Details(QWidget):
    """Small percentage-first popover, with raw counts behind Details."""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(240)
        self.setAccessibleName("TOMC 上下文节省与账户额度")
        self.setStyleSheet(STYLE + """
            QWidget#periods { background: #EEEAE2; border-radius: 7px; }
            QPushButton#period { color: #706659; border-radius: 5px; padding: 1px; font-size: 11px; }
            QPushButton#period:checked { background: #FFFCF7; color: #354F42; font-weight: 600; }
            QPushButton#foot { font-size: 10px; color: #706659; padding: 3px 5px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 7)
        layout.setSpacing(0)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        self.portrait = PetArt(self)
        self.portrait.compact_idle = True
        self.portrait.setFixedSize(26, 29)
        self.portrait.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        heading.addWidget(self.portrait)
        heading.addWidget(label("TOMC", 13, bold=True))
        self.stage = label(size=10, color="#706659")
        heading.addWidget(self.stage)
        heading.addStretch()
        self.demo_badge = label("演示", 10, "#866239")
        self.demo_badge.setVisible(owner.test_mode)
        heading.addWidget(self.demo_badge)
        self.close_button = DismissButton()
        self.close_button.clicked.connect(self.hide)
        heading.addWidget(self.close_button)
        layout.addLayout(heading)
        layout.addSpacing(5)
        self.mode_status = label("按需工具 · 会话状态待读取", 10, "#52705D")
        self.mode_status.setWordWrap(True)
        self.mode_status.setToolTip("全局配置使工具可用；自动全对话请求压缩尚未接入。会话来自宿主事件，不代表桌面焦点。")
        layout.addWidget(self.mode_status)
        layout.addSpacing(6)
        period_surface = QWidget()
        period_surface.setObjectName("periods")
        periods = QHBoxLayout(period_surface)
        periods.setContentsMargins(2, 2, 2, 2)
        periods.setSpacing(2)
        self.buttons = {}
        for key, title in (("today", "今天"), ("7d", "近七天"), ("all", "累计")):
            button = QPushButton(title)
            button.setObjectName("period")
            button.setFixedHeight(22)
            button.setCheckable(True)
            button.setAccessibleName(f"查看{title}上下文统计")
            button.clicked.connect(lambda checked=False, p=key: owner.set_period(p))
            self.buttons[key] = button
            periods.addWidget(button)
        layout.addWidget(period_surface)
        layout.addSpacing(6)
        metric = QHBoxLayout()
        self.caption = label("上下文减少", 11, "#52705D")
        self.total = label(size=25, color="#345743", bold=True)
        self.total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        metric.addWidget(self.caption)
        metric.addWidget(self.total, 1)
        layout.addLayout(metric)
        self.latest = label(size=11)
        self.latest.setWordWrap(True)
        self.latest.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        recent = QHBoxLayout()
        recent.addWidget(label("最近一次", 10, "#706659"))
        recent.addWidget(self.latest, 1)
        layout.addLayout(recent)
        layout.addSpacing(6)
        quota_line = QHBoxLayout()
        self.quota_title = label("Codex 额度", 10, "#706659")
        self.quota_value = label("未连接", 11)
        self.quota_value.setWordWrap(True)
        self.quota_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        quota_line.addWidget(self.quota_title)
        quota_line.addWidget(self.quota_value, 1)
        layout.addLayout(quota_line)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        layout.addSpacing(6)
        self.price_note = label("上下文估算，不等于额度节省", 10, "#706659")
        layout.addWidget(self.price_note)
        self.library_button = QPushButton("上下文与接续")
        self.library_button.setStyleSheet("QPushButton { background: #E4ECE5; color: #345743; font-weight: 600; margin-top: 5px; margin-bottom: 4px; }")
        self.library_button.clicked.connect(owner.open_context_library)
        layout.addWidget(self.library_button)
        footer = QHBoxLayout()
        self.info_button = QPushButton("详情")
        self.info_button.setObjectName("foot")
        self.info_button.setCheckable(True)
        self.info_button.toggled.connect(self.toggle_scope)
        footer.addWidget(self.info_button)
        price_button = QPushButton("估价")
        price_button.setObjectName("foot")
        price_button.clicked.connect(owner.open_reference)
        footer.addWidget(price_button)
        footer.addStretch()
        quit_button = QPushButton("退出 TOMC")
        quit_button.setObjectName("foot")
        quit_button.clicked.connect(owner.close)
        footer.addWidget(quit_button)
        layout.addLayout(footer)
        self.scope = QWidget()
        detail_layout = QVBoxLayout(self.scope)
        detail_layout.setContentsMargins(0, 5, 0, 0)
        detail_layout.setSpacing(5)
        self.rows = label(size=10)
        self.rows.setWordWrap(True)
        detail_layout.addWidget(self.rows)
        self.hint = label(size=10, color="#52705D")
        self.hint.setWordWrap(True)
        detail_layout.addWidget(self.hint)
        detail_layout.addWidget(self.progress)
        explanation = label("比较 TOMC 处理前后的上下文；累计比例按总量计算。\n额度是账户当前余额，受模型、推理、工具和缓存影响，不能从压缩比例换算。日期按 UTC。", 10, "#706659")
        explanation.setWordWrap(True)
        detail_layout.addWidget(explanation)
        self.cost_detail = label("", 10, "#706659")
        self.cost_detail.setWordWrap(True)
        detail_layout.addWidget(self.cost_detail)
        self.quota_detail = label("账户额度尚未读取。", 10, "#706659")
        self.quota_detail.setWordWrap(True)
        detail_layout.addWidget(self.quota_detail)
        layout.addWidget(self.scope)
        self.scope.hide()

    def resize_to_content(self):
        self.layout().invalidate()
        self.adjustSize()
        if self.isVisible():
            self.owner.position_details()

    def toggle_scope(self, expanded):
        self.scope.setVisible(expanded)
        self.info_button.setText("收起详情" if expanded else "详情")
        self.resize_to_content()

    def set_quota(self, state):
        self.quota_state = state
        windows = state.get("windows", []) if state.get("status") == "ready" else []
        if windows:
            selected = next((w for w in windows if w["bucket"] == "codex"), windows[0])
            prefix = "Codex" if selected["bucket"] == "codex" else selected["bucket"]
            self.quota_title.setText(f"{prefix} {selected['period']}")
            self.quota_value.setText(f"剩余 {selected['remaining']:g}%")
            self.quota_detail.setText("账户额度 · 每分钟读取\n" + "\n".join(
                f"{w['bucket']} {w['period']}剩余 {w['remaining']:g}%" for w in windows))
        else:
            self.quota_title.setText("Codex 额度")
            self.quota_value.setText("读取中" if state.get("status") == "loading" else "暂不可读")
            self.quota_detail.setText("未取得当前额度，不显示为零。需要已登录的 Codex CLI。")
        self.resize_to_content()

    def set_summary(self, summary, values, growth, latest):
        self.portrait.set_state(growth)
        self.stage.setText(f"Lv.{growth['level']}" if not growth["mixed"] else "")
        self.progress.show()
        self.progress.setValue(round(growth["progress"]*1000))
        self.progress.setToolTip(growth["hint"])
        self.progress.setAccessibleName(growth["hint"])
        self.hint.setText(f"凝实度 {growth['opacity']:.0%} · {growth['hint']}")
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        groups = summary["by_counter"]
        percent = context_percent(groups[0]["input_tokens"], groups[0]["memory_tokens"]) if len(groups) == 1 else None
        negative = percent is not None and percent < 0
        self.caption.setText("上下文增加" if negative else "上下文减少")
        self.total.setText("分口径" if len(groups) > 1 else percent_text(percent))
        self.total.setStyleSheet(f"font-family: 'Segoe UI'; font-size: 25px; color: {'#866239' if negative else '#345743'}; font-weight: 600;")
        last = summary.get("last_preparation")
        if last and last["usable"]:
            recent = context_percent(last["input_tokens"], last["memory_tokens"])
            self.latest.setText(("多用 " if recent is not None and recent < 0 else "少用 ")+percent_text(recent))
        else:
            self.latest.setText("无可用输出" if last else "等你开工")
        self.latest.setToolTip(latest)
        pricing = self.owner.pricing
        if pricing:
            delta = groups[0]["reduced_tokens"] if len(groups) == 1 else None
            self.caption.setText("预计多花" if delta is not None and delta < 0 else "预计少花")
            self.total.setText("分口径" if len(groups) > 1 else dollars(input_value(delta, pricing)))
            if last and last["usable"]:
                value = input_value(last["reduced_tokens"], pricing)
                self.latest.setText(("多花 " if value < 0 else "少花 ") + dollars(value))
            name = pricing['label'].removeprefix('Claude ')
            self.price_note.setText(f"{name} · 参考估价")
        else:
            self.caption.setText("参考价值")
            self.total.setText("—")
            self.latest.setText("费率待确认" if last else "等你开工")
            self.price_note.setText("模型未确认 · 点击估价选择")
        self.price_note.setToolTip(explanation(pricing))
        self.cost_detail.setText("全部准备记录按当前参考模型折算，非账单节省。模型、费率、更新时间与绿洲故事见「估价」。")
        rows = [f"{values['calls']} 次准备 · 数量单位为 tokens"]
        for group in groups:
            percent = context_percent(group["input_tokens"], group["memory_tokens"])
            rows.append(f"{group['counter']}\n{group['input_tokens']:,} → {group['memory_tokens']:,}\n净减少 {group['reduced_tokens']:,}（{'增加' if percent is not None and percent < 0 else '减少'} {percent_text(percent)}）")
        rows.append(latest)
        self.rows.setText("\n".join(rows))
        self.resize_to_content()

    def show_error(self):
        self.stage.clear()
        self.progress.hide()
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        self.caption.setText("统计状态")
        self.total.setText("暂不可读")
        self.total.setStyleSheet("font-size: 18px; color: #866239;")
        self.latest.setText("自动重试中")
        self.rows.setText("统计读取失败，正在自动重试。")
        self.hint.setText("成长记录待恢复。")
        self.resize_to_content()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#E8E2D8"))
        painter.setBrush(QColor("#FFFCF7"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)

class Companion(QWidget):
    def __init__(self, path: Path, *, test_mode=False, state_file=None, connect_quota=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("TOMC" + (" — 测试数据" if test_mode else ""))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("TOMC；点击查看统计与上下文入口，拖动移动，右键打开菜单")
        self.setToolTip("点击看统计与上下文入口 · 拖动移动 · 右键菜单")
        self.setStyleSheet(STYLE)
        self.setFixedSize(250, 116)
        self.store = UsageStore(path)
        from .context_library_qt import SessionNotice
        from .session_store import SessionStore

        self.session_store = SessionStore(path)
        self.context_dialog = None
        self.session_notice = SessionNotice(self.session_store, self)
        self.session_notice.changed.connect(self.refresh_session_state)
        self.session_event_seq = None
        self.session_signature = None
        self.pricing = load_pricing()
        self.pending_victory = False
        self.test_mode, self.state_file = test_mode, state_file
        self.period, self.summary, self.error = "all", None, None
        self.last_signature, self.last_level = None, None
        self.drag_origin = None
        self.was_dragged = False
        self.art = PetArt(self)
        self.art.compact_idle = True
        self.art.setGeometry(0, 0, 140, 156)
        self.art.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.art.setAccessibleName("TOMC 猫头；拖动移动，点击查看成长")
        self.materialization = QGraphicsOpacityEffect(self.art)
        self.art.setGraphicsEffect(self.materialization)
        self.art.collecting.connect(lambda: self.layout_report(False))
        self.art.collected.connect(self.finish_collection)
        self.card = QPushButton(self)
        self.card.setGeometry(91, 20, 151, 68)
        self.card.setStyleSheet("QPushButton { background: #FFFCF7; border: 1px solid #E8E2D8; border-radius: 16px; } QPushButton:hover { background: #F2F5ED; } QPushButton:focus { border: 1px solid #507461; }")
        self.card.clicked.connect(self.toggle_details)
        self.caption = label("累计预计少用", 10, "#74685D")
        self.caption.setParent(self.card)
        self.caption.setGeometry(13, 8, 128, 17)
        self.number = label(size=20, bold=True)
        self.number.setParent(self.card)
        self.number.setGeometry(13, 26, 128, 30)
        for child in (self.caption, self.number):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.progress = QProgressBar(self)
        self.progress.setGeometry(105, 77, 121, 3)
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.latest = label(size=10, color="#443B35")
        self.latest.setParent(self)
        self.latest.setGeometry(102, 90, 144, 19)
        # A light backing keeps the tiny latest-call text readable on any desktop.
        self.latest.setStyleSheet("background: transparent; color: #74685D; padding-left: 4px; font-size: 10px;")
        self.close_button = QPushButton("×", self)
        self.close_button.setGeometry(223, 0, 24, 20)
        self.close_button.setAccessibleName("关闭TOMC")
        self.close_button.setStyleSheet("QPushButton { background: #FFFCF7; color: #74685D; padding: 0; border-radius: 8px; }")
        self.close_button.clicked.connect(self.close)
        self.pet_menu = QMenu(self)
        self.pet_menu.setStyleSheet("QMenu { background: #FFFCF7; color: #443B35; border: 1px solid #E8E2D8; padding: 5px; } QMenu::item { padding: 8px 20px; } QMenu::item:selected { background: #E4ECE5; color: #345743; }")
        self.pet_menu.addAction("查看统计", self.toggle_details)
        self.pet_menu.addAction("上下文与接续", self.open_context_library)
        self.pet_menu.addSeparator()
        self.quit_action = self.pet_menu.addAction("退出 TOMC", self.close)
        self.details = Details(self)
        self.oasis = OasisCelebration(self)
        self.oasis_action = self.pet_menu.addAction("重播皇冠绿洲", self.oasis.start)
        self.reference_sheet = None
        self.pet_menu.addAction("模型与估价", self.open_reference)
        self.pet_menu.addAction("绿洲的故事", lambda: self.open_reference(tab=1))
        self.quota_reader = None
        quota_enabled = connect_quota if connect_quota is not None else not test_mode
        if quota_enabled:
            self.quota_reader = QuotaReader(self)
            self.quota_reader.updated.connect(self.details.set_quota)
            self.details.set_quota({"status": "loading", "windows": []})
            QTimer.singleShot(0, self.quota_reader.start)
        self.report_timer = QTimer(self)
        self.report_timer.setSingleShot(True)
        self.report_timer.timeout.connect(self.hide_report)
        self.initialized, self.last_at = False, None
        self.event_cursor, self.active_report = 0, None
        self.pending_reports = deque()
        self.bubble_visible = False
        self.layout_report(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)

    def open_reference(self, checked=False, tab=0):
        from .pricing_qt import ReferenceSheet

        if self.reference_sheet is None:
            self.reference_sheet = ReferenceSheet(self)
        self.reference_sheet.open_tab(tab)

    def open_context_library(self, checked=False):
        from .context_library_qt import ContextLibraryDialog

        self.details.hide()
        self.session_notice.hide()
        if self.context_dialog is None:
            self.context_dialog = ContextLibraryDialog(self.store.path, self,
                                                       sessions=self.session_store)
            self.context_dialog.changed.connect(self.refresh_session_state)
        else:
            self.context_dialog.refresh()
        self.context_dialog.show()
        self.context_dialog.raise_()
        self.context_dialog.activateWindow()

    def refresh_session_state(self):
        try:
            active = self.session_store.active()
            settings = self.session_store.settings()
        except (OSError, sqlite3.Error, ValueError):
            self.details.mode_status.setText("按需工具 · 会话状态暂不可读")
            return
        enabled = settings.get("enabled", True)
        state = "处理开启" if enabled else "全局处理暂停"
        if active:
            state += " · 最近会话开启" if active.get("enabled", True) else " · 最近会话已关闭"
        else:
            state += " · 未取得会话事件"
        signature = json.dumps([settings, active], sort_keys=True)
        if signature != self.session_signature:
            self.session_signature = signature
            self.details.mode_status.setText(f"按需工具 · {state}")
            self.details.resize_to_content()
        if active and active.get("event_seq") != self.session_event_seq:
            self.session_event_seq = active.get("event_seq")
            self.session_notice.present(active)
            self.position_session_notice()

    def position_session_notice(self):
        notice = self.session_notice
        area = self.screen().availableGeometry()
        point = self.mapToGlobal(QPoint(self.width() - notice.width(), -notice.height() - 10))
        point.setX(max(area.left(), min(point.x(), area.right() - notice.width() + 1)))
        point.setY(max(area.top(), min(point.y(), area.bottom() - notice.height() + 1)))
        notice.move(point)

    def refresh(self):
        self.refresh_session_state()
        self.pricing = load_pricing()
        try:
            summary, error = self.store.summary(self.period), None
            events = self.store.recent_events(self.event_cursor)
        except (OSError, sqlite3.Error):
            summary, error = None, "read_failed"
        signature = json.dumps([summary, error, self.period, self.pricing], sort_keys=True)
        if signature == self.last_signature:
            return
        self.last_signature = signature
        self.summary, self.error = summary, error
        if error:
            self.art.animation_timer.stop()
            self.art.phase = None
            self.active_report = None
            self.pending_reports.clear()
            self.caption.setText("统计状态")
            self.number.setText("暂不可读")
            self.latest.setText("统计读取失败，自动重试")
            self.details.show_error()
            self.card.setToolTip("统计读取失败，正在自动重试。")
            self.layout_report(True)
            self.report_timer.start(6000)
        else:
            self.render_summary(summary, events)
        if self.state_file:
            self.state_file.write_text(json.dumps({
                "summary": summary, "error": error, "period": self.period,
                "test_mode": self.test_mode,
                "pricing": self.pricing,
                "growth": growth_state(summary) if summary else None,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    def render_summary(self, summary, events=()):
        values = display_values(summary)
        growth = growth_state(summary)
        self.oasis_action.setVisible(growth["level"] == 4 or self.test_mode)
        if self.last_level is not None and self.last_level < 4 and growth["level"] == 4:
            self.pending_victory = True
        self.number.setStyleSheet("font-family: 'Segoe UI'; font-size: 20px; font-weight: 600; color: #443B35;")
        self.number.setText("—")
        self.caption.setText("上下文估算")
        self.art.set_state(growth)
        self.materialization.setOpacity(growth["opacity"])
        self.progress.setValue(round(growth["progress"] * 1000))
        self.progress.setAccessibleName(growth["hint"])
        last = summary.get("last_preparation")
        latest = "等你开工 · 点击看成长"
        long_latest = "等待 TOMC 准备上下文。"
        if last and last["usable"]:
            delta = last["reduced_tokens"]
            latest = f"本次 {'多用' if delta < 0 else '少用'} {abs(delta):,}"
            long_latest = f"最近一次  {last['input_tokens']:,} → {last['memory_tokens']:,} tokens"
            self.report_text(last)
        elif last:
            latest, long_latest = "本次无可用输出", "最近一次未生成可用上下文，未计入减少量。"
        self.latest.setText(self.estimate_note() if last and last["usable"] else latest)
        self.latest.setToolTip(long_latest)
        self.card.setAccessibleName(f"{growth['name']}，{long_latest}，点击查看累计统计")
        self.card.setToolTip(f"{growth['name']} · {growth['hint']}\n仅上下文估算，非账单节省。点击展开统计。")
        self.details.set_summary(summary, values, growth, long_latest)
        at = last["recorded_at"] if last else None
        if self.initialized and at and at != self.last_at:
            ready = [event for event in events if event["recorded_at"] <= at]
            self.pending_reports.extend(ready or [last])
            if ready:
                self.event_cursor = ready[-1]["seq"]
            self.start_collection()
            if self.bubble_visible and self.report_timer.remainingTime() > 1800:
                self.report_timer.start(1800)
        elif not self.initialized and events:
            # Opening the pet must never replay historical calls.
            self.event_cursor = events[-1]["seq"]
        self.initialized, self.last_at = True, at
        if self.active_report and self.bubble_visible:
            self.report_text(self.active_report)
        # Cosmetic milestones never replace the per-call numeric report or steal focus.
        self.last_level = growth["level"]

    def start_collection(self):
        if self.active_report or not self.pending_reports:
            return
        self.active_report = self.pending_reports.popleft()
        self.layout_report(False)
        self.report_timer.stop()
        self.art.collect()

    def report_text(self, report):
        if report["usable"]:
            delta = report["reduced_tokens"]
            self.caption.setText(("演示 · " if self.test_mode else "本次") + ("上下文增加" if delta < 0 else "上下文减少"))
            self.number.setText(percent_text(context_percent(report["input_tokens"], report["memory_tokens"])))
            if self.pricing:
                self.caption.setText(("演示 · " if self.test_mode else "本次") + ("预计多花" if delta < 0 else "预计少花"))
                self.number.setText(dollars(input_value(delta, self.pricing)))
            else:
                self.caption.setText("本次参考价值")
                self.number.setText("费率待确认")
        else:
            self.caption.setText("本次准备")
            self.number.setText("无可用输出")
        self.latest.setText(self.estimate_note())

    def estimate_note(self):
        return f"{self.pricing['label'].removeprefix('Claude ')} · 参考估价" if self.pricing else "点击估价 · 选择参考模型"

    def finish_collection(self):
        if self.active_report:
            self.report_text(self.active_report)
        self.layout_report(True)
        self.report_timer.start(1800 if self.pending_reports else 6000)
        if self.pending_victory:
            self.pending_victory = False
            self.oasis.start()

    def layout_report(self, visible):
        anchor = self.mapToGlobal(self.art.geometry().center())
        self.bubble_visible = visible
        pet_width = ACTIVE_WIDTH if self.art.phase is not None else IDLE_WIDTH
        pet_height = round(pet_width*156/140)
        height = max(110, pet_height) if visible else pet_height
        pet_x, pet_y = (185 if visible else 0), (height-pet_height)//2
        self.setFixedSize(pet_x+pet_width, height)
        self.art.setGeometry(pet_x, pet_y, pet_width, pet_height)
        self.card.setGeometry(8, 8, 170, 94)
        self.caption.setGeometry(13, 8, 144, 17)
        self.number.setGeometry(13, 26, 144, 30)
        self.progress.setGeometry(23, 65, 140, 3)
        self.latest.setGeometry(12, 81, 166, 20)
        self.close_button.setGeometry(pet_x+pet_width-20, 0, 20, 20)
        self.close_button.setVisible(self.underMouse())
        for part in (self.card, self.caption, self.number, self.progress, self.latest):
            part.setVisible(visible)
        point = anchor - self.art.geometry().center()
        area = self.screen().availableGeometry()
        point.setX(max(area.left(), min(point.x(), area.right()-self.width()+1)))
        point.setY(max(area.top(), min(point.y(), area.bottom()-self.height()+1)))
        self.move(point)
        if self.session_notice.isVisible():
            self.position_session_notice()

    def hide_report(self):
        self.layout_report(False)
        self.active_report = None
        self.start_collection()

    def enterEvent(self, event):
        self.close_button.show()

    def leaveEvent(self, event):
        self.close_button.hide()

    def set_period(self, period):
        self.period = period
        self.last_signature = None
        self.refresh()
        self.details.adjustSize()

    def toggle_details(self):
        if self.details.isVisible():
            self.details.hide()
            return
        self.details.adjustSize()
        self.position_details()
        self.details.show()

    def position_details(self):
        area = self.screen().availableGeometry()
        point = self.mapToGlobal(QPoint(self.width() - self.details.width(), -self.details.height() - 8))
        point.setX(max(area.left(), min(point.x(), area.right() - self.details.width())))
        point.setY(max(area.top(), min(point.y(), area.bottom() - self.details.height())))
        self.details.move(point)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = (event.globalPosition().toPoint(), self.pos())
            self.was_dragged = False

    def contextMenuEvent(self, event):
        self.pet_menu.popup(event.globalPos())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_origin:
            start, pos = self.drag_origin
            offset = event.globalPosition().toPoint() - start
            if offset.manhattanLength() > 5:
                self.was_dragged = True
                self.details.hide()
                self.move(pos + offset)

    def mouseReleaseEvent(self, event):
        if self.drag_origin and not self.was_dragged:
            self.toggle_details()
        self.drag_origin = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.toggle_details()

    def closeEvent(self, event):
        self.session_notice.close()
        if self.context_dialog:
            self.context_dialog.close()
        if self.reference_sheet:
            self.reference_sheet.close()
        self.oasis.close()
        if self.quota_reader:
            self.quota_reader.stop()
        self.timer.stop()
        self.report_timer.stop()
        self.art.animation_timer.stop()
        self.details.close()
        super().closeEvent(event)
        QApplication.instance().quit()


def run(path, test_mode=False, state_file=None, host="codex"):
    app = QApplication(sys.argv[:1])
    load_preview_fonts()
    app.setApplicationName("TOMC")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    digest = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:24]
    lock = QLockFile(str(Path(tempfile.gettempdir()) / f"tomc-pet-{digest}.lock"))
    if not lock.tryLock(0):
        return
    widget = Companion(path, test_mode=test_mode, state_file=state_file,
                       connect_quota=host == "codex" and not test_mode)
    if host != "codex":
        widget.details.quota_title.setText(f"{host.title()} 额度")
        widget.details.quota_value.setText("未接入")
        widget.details.quota_detail.setText(f"当前显示 TOMC 统计；尚未接入 {host.title()} 账户额度。")
        widget.details.resize_to_content()
    widget.show()
    try:
        app.exec()
    finally:
        lock.unlock()

