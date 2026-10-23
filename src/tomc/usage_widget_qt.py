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
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .cost_estimate import dollars, input_value, load_pricing
from .oasis_qt import OasisCelebration
from .pet_art import ACTIVE_WIDTH, IDLE_WIDTH, PetArt
from .pet_growth import growth_state, request_stage
from .quota import context_percent, percent_text
from .quota_qt import QuotaReader
from .request_activity import RequestActivity
from .ui_language import UiLanguage, ui_font
from .usage import UsageStore
from .usage_widget import display_values

STYLE = """
QWidget { color: #443B35; font-family: 'Microsoft YaHei UI', 'Noto Sans CJK SC', 'Segoe UI'; font-size: 12px; }
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
    item.setFont(ui_font())
    item.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {600 if bold else 400};")
    return item


def growth_hint(growth, language):
    # The helper owns the current request's input-length classification.
    return growth["hint"]


def quota_period(value, language):
    periods = {
        "5小时": ("5小时", "5 hours"),
        "本周": ("本周", "This week"),
        "今日": ("今日", "Today"),
        "当前周期": ("当前周期", "Current period"),
    }
    if value in periods:
        return language.tr(*periods[value])
    if isinstance(value, str) and value.endswith("分钟"):
        return language.tr("{value}分钟", "{value} minutes", value=value[:-2])
    return str(value)


class DismissButton(QPushButton):
    """Draw the same quiet close mark at every display scale."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.setFixedSize(28, 28)
        self.retranslate()
        language.changed.connect(self.retranslate)

    def retranslate(self, _code=None):
        self.setAccessibleName(self.language.tr("收起统计", "Close statistics"))
        self.setToolTip(self.language.tr("收起统计 · Esc", "Close statistics · Esc"))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#796D60"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(10, 10, 18, 18)
        painter.drawLine(18, 10, 10, 18)


class Details(QWidget):
    """Small percentage-first popover, with raw counts behind Details."""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.owner = owner
        self.language = owner.language
        tr = self.language.tr
        self.quota_state = {"status": "unavailable", "windows": []}
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(240)
        self.setAccessibleName("TOMC 上下文节省与账户额度")
        self.setStyleSheet(
            STYLE
            + """
            QWidget#periods { background: #EEEAE2; border-radius: 7px; }
            QPushButton#period { color: #706659; border-radius: 5px; padding: 1px; font-size: 11px; }
            QPushButton#period:checked { background: #FFFCF7; color: #354F42; font-weight: 600; }
            QPushButton#foot { font-size: 10px; color: #706659; padding: 3px 5px; }
        """
        )
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
        self.close_button = DismissButton(self.language)
        self.close_button.clicked.connect(self.hide)
        heading.addWidget(self.close_button)
        layout.addLayout(heading)
        language_row = QHBoxLayout()
        language_row.setSpacing(4)
        self.language_title = label(size=10, color="#706659")
        language_row.addWidget(self.language_title)
        language_row.addStretch()
        self.language_buttons = {}
        for code, text in (("zh", "中文"), ("en", "English")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setFixedHeight(27)
            button.clicked.connect(lambda checked=False, value=code: owner.set_ui_language(value))
            self.language_buttons[code] = button
            language_row.addWidget(button)
        layout.addLayout(language_row)
        layout.addSpacing(5)
        self.mode_status = label(
            tr("TOMC · 会话状态待读取", "TOMC · Session status pending"), 10, "#52705D"
        )
        self.mode_status.setWordWrap(True)
        self.mode_status.setToolTip(
            "仅处理实际经过 TOMC 的工具或代理请求。会话来自宿主事件，不代表桌面焦点。"
        )
        layout.addWidget(self.mode_status)
        self.request_status = label(
            tr("自动请求：尚未观察到", "Automatic requests: none observed"), 10, "#706659"
        )
        self.request_status.setWordWrap(True)
        layout.addWidget(self.request_status)
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
        self.recent_title = label("最近一次", 10, "#706659")
        recent.addWidget(self.recent_title)
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
        self.price_note = label(
            tr("上下文估算，不等于额度节省", "Context estimate, not allowance savings"),
            10,
            "#706659",
        )
        self.price_note.setWordWrap(True)
        layout.addWidget(self.price_note)
        self.library_button = QPushButton("上下文与接续")
        self.library_button.setStyleSheet(
            "QPushButton { background: #E4ECE5; color: #345743; font-weight: 600; margin-top: 5px; margin-bottom: 4px; }"
        )
        self.library_button.clicked.connect(owner.open_context_library)
        layout.addWidget(self.library_button)
        footer = QHBoxLayout()
        self.info_button = QPushButton("详情")
        self.info_button.setObjectName("foot")
        self.info_button.setCheckable(True)
        self.info_button.toggled.connect(self.toggle_scope)
        footer.addWidget(self.info_button)
        self.price_button = QPushButton("估价")
        self.price_button.setObjectName("foot")
        self.price_button.clicked.connect(owner.open_reference)
        footer.addWidget(self.price_button)
        footer.addStretch()
        self.quit_button = QPushButton("退出 TOMC")
        self.quit_button.setObjectName("foot")
        self.quit_button.clicked.connect(owner.close)
        footer.addWidget(self.quit_button)
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
        self.explanation = label(size=10, color="#706659")
        self.explanation.setWordWrap(True)
        detail_layout.addWidget(self.explanation)
        self.cost_detail = label("", 10, "#706659")
        self.cost_detail.setWordWrap(True)
        detail_layout.addWidget(self.cost_detail)
        self.quota_detail = label("账户额度尚未读取。", 10, "#706659")
        self.quota_detail.setWordWrap(True)
        detail_layout.addWidget(self.quota_detail)
        self.request_usage_detail = label(
            tr(
                "尚未观察到代理请求；配置可用不代表已接管请求。",
                "No gateway request observed. Configuration alone does not prove request coverage.",
            ),
            10,
            "#706659",
        )
        self.request_usage_detail.setWordWrap(True)
        detail_layout.addWidget(self.request_usage_detail)
        self.scope_area = QScrollArea()
        self.scope_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scope_area.setWidgetResizable(True)
        self.scope_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scope_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scope_area.setWidget(self.scope)
        self.scope.setAutoFillBackground(False)
        self.scope_area.viewport().setAutoFillBackground(False)
        layout.addWidget(self.scope_area)
        self.scope_area.hide()
        self.retranslate()
        self.language.changed.connect(self.retranslate)

    def retranslate(self, _code=None):
        tr = self.language.tr
        self.setFixedWidth(280 if self.language.code == "zh" else 310)
        self.setAccessibleName(
            tr("TOMC 上下文统计与账户额度", "TOMC context statistics and account allowance")
        )
        self.language_title.setText(tr("界面语言", "Language"))
        for code, button in self.language_buttons.items():
            button.setChecked(code == self.language.code)
            button.setAccessibleName("中文" if code == "zh" else "English")
        self.demo_badge.setText(tr("演示", "Demo"))
        self.mode_status.setToolTip(
            tr(
                "仅处理实际经过 TOMC 的工具或代理请求。会话来自宿主事件，不代表桌面焦点。",
                "Only requests observed by TOMC are processed. Session events do not identify desktop focus.",
            )
        )
        for key, zh, en in (
            ("today", "今天", "Today"),
            ("7d", "近七天", "7 days"),
            ("all", "累计", "All time"),
        ):
            self.buttons[key].setText(tr(zh, en))
            self.buttons[key].setAccessibleName(
                tr("查看{period}上下文统计", "Show {period} context statistics", period=tr(zh, en))
            )
        self.recent_title.setText(tr("最近一次", "Latest"))
        self.library_button.setText(tr("上下文与接续", "Contexts && handoff"))
        self.info_button.setText(
            tr("收起详情", "Less detail") if self.info_button.isChecked() else tr("详情", "Details")
        )
        self.price_button.setText(tr("估价", "Pricing"))
        self.quit_button.setText(tr("退出 TOMC", "Quit TOMC"))
        self.explanation.setText(
            tr(
                "比较 TOMC 处理前后的上下文；累计比例按总量计算。\n额度是账户当前余额，受模型、推理、工具和缓存影响，不能从压缩比例换算。日期按 UTC。",
                "Compares context before and after TOMC; the total percentage uses summed counts.\nAccount allowance also depends on the model, reasoning, tools and cache. Context reduction does not predict allowance savings. Dates use UTC.",
            )
        )
        self.set_quota(self.quota_state)

    def resize_to_content(self):
        self.layout().invalidate()
        if self.info_button.isChecked():
            # Keep the controls above the scrollable detail body visible on
            # small/high-DPI screens without compressing or dropping count rows.
            self.scope_area.setFixedHeight(0)
            self.layout().activate()
            header = self.layout().totalHeightForWidth(self.width())
            maximum = max(120, self.screen().availableGeometry().height() - header - 24)
            margins = self.layout().contentsMargins()
            width = self.width() - margins.left() - margins.right()
            # Reserve scrollbar width before wrapping, avoiding a feedback loop
            # where a newly visible scrollbar creates another clipped line.
            width -= self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            desired = self.scope.layout().totalHeightForWidth(width)
            self.scope.setMinimumHeight(desired)
            self.scope_area.setFixedHeight(min(desired, maximum))
        # QWidget.adjustSize caps a top-level window at two thirds of the
        # screen, squeezing multiline labels. Honor their actual wrapped height.
        self.layout().activate()
        height = self.layout().totalHeightForWidth(self.width())
        self.resize(self.width(), height if height > 0 else self.sizeHint().height())
        if self.isVisible():
            self.owner.position_details()

    def toggle_scope(self, expanded):
        self.scope_area.setVisible(expanded)
        self.info_button.setText(
            self.language.tr("收起详情", "Less detail")
            if expanded
            else self.language.tr("详情", "Details")
        )
        self.resize_to_content()

    def set_quota(self, state):
        tr = self.language.tr
        self.quota_state = state
        windows = state.get("windows", []) if state.get("status") == "ready" else []
        if windows:
            selected = next((w for w in windows if w["bucket"] == "codex"), windows[0])
            prefix = "Codex" if selected["bucket"] == "codex" else selected["bucket"]
            self.quota_title.setText(f"{prefix} {quota_period(selected['period'], self.language)}")
            self.quota_value.setText(
                tr("剩余 {value:g}%", "{value:g}% left", value=selected["remaining"])
            )
            self.quota_detail.setText(
                tr("账户额度 · 每分钟读取\n", "Account allowance · refreshed every minute\n")
                + "\n".join(
                    tr(
                        "{bucket} {period}剩余 {value:g}%",
                        "{bucket} {period}: {value:g}% left",
                        bucket=w["bucket"],
                        period=quota_period(w["period"], self.language),
                        value=w["remaining"],
                    )
                    for w in windows
                )
            )
        elif state.get("status") == "unsupported_host":
            host = state.get("host", "Host")
            self.quota_title.setText(tr("{host} 额度", "{host} allowance", host=host))
            self.quota_value.setText(tr("未接入", "Not connected"))
            self.quota_detail.setText(
                tr(
                    "当前显示 TOMC 统计；尚未接入 {host} 账户额度。",
                    "Showing TOMC statistics; {host} account allowance is not connected.",
                    host=host,
                )
            )
        else:
            self.quota_title.setText(tr("Codex 额度", "Codex allowance"))
            self.quota_value.setText(
                tr("读取中", "Loading")
                if state.get("status") == "loading"
                else tr("暂不可读", "Unavailable")
            )
            self.quota_detail.setText(
                tr(
                    "未取得当前额度，不显示为零。需要已登录的 Codex CLI。",
                    "Allowance is unavailable, not zero. A signed-in Codex CLI is required.",
                )
            )
        self.resize_to_content()

    def set_summary(self, summary, values, growth, latest):
        tr = self.language.tr
        self.set_stage(growth)
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        groups = summary["by_counter"]
        percent = (
            context_percent(groups[0]["input_tokens"], groups[0]["memory_tokens"])
            if len(groups) == 1
            else None
        )
        negative = percent is not None and percent < 0
        self.caption.setText(
            tr("上下文增加", "Context increase")
            if negative
            else tr("上下文减少", "Context reduction")
        )
        mixed = len(groups) > 1
        self.total.setText(
            tr("多种计数方式", "Multiple counters") if mixed else percent_text(percent)
        )
        self.total.setStyleSheet(
            f"font-size: {13 if mixed else 25}px; color: {'#866239' if negative else '#345743'}; font-weight: 600;"
        )
        last = summary.get("last_preparation")
        if last and last["usable"]:
            recent = context_percent(last["input_tokens"], last["memory_tokens"])
            self.latest.setText(
                tr("增加 {value}", "{value} more", value=percent_text(recent))
                if recent is not None and recent < 0
                else tr("减少 {value}", "{value} less", value=percent_text(recent))
            )
        else:
            self.latest.setText(
                tr("无可用输出", "No usable output")
                if last
                else tr("等待首次记录", "No activity yet")
            )
        self.latest.setToolTip(latest)
        pricing = self.owner.pricing
        if pricing:
            delta = groups[0]["reduced_tokens"] if len(groups) == 1 else None
            name = pricing["label"].removeprefix("Claude ")
            value = input_value(delta, pricing) if delta is not None else None
            self.price_note.setText(
                tr(
                    "{model} · 参考输入差额 {value}",
                    "{model} · Reference input difference {value}",
                    model=name,
                    value=dollars(value),
                )
            )
        else:
            self.price_note.setText(
                tr("参考模型未选择 · 点击估价", "No reference model · Select Pricing")
            )
        cost_note = tr(
            "按参考输入单价折算，非账单节省。压缩可能降低缓存命中、增加实际费用。费率与更新时间见「估价」。",
            "Uses a reference input rate, not bill savings. Compression can reduce cache hits and increase actual cost. See Pricing for rates and dates.",
        )
        self.price_note.setToolTip(cost_note)
        self.cost_detail.setText(cost_note)
        rows = [
            tr(
                "{count} 次准备 · 数量单位为 tokens",
                "{count} preparations · Counts are tokens",
                count=values["calls"],
            )
        ]
        for group in groups:
            percent = context_percent(group["input_tokens"], group["memory_tokens"])
            change = (
                tr("增加", "increase")
                if percent is not None and percent < 0
                else tr("减少", "reduction")
            )
            rows.append(
                tr(
                    "{counter}\n{before:,} → {after:,}\n净减少 {delta:,}（{change} {percent}）",
                    "{counter}\n{before:,} → {after:,}\nNet reduction {delta:,} ({percent} {change})",
                    counter=group["counter"],
                    before=group["input_tokens"],
                    after=group["memory_tokens"],
                    delta=group["reduced_tokens"],
                    change=change,
                    percent=percent_text(percent),
                )
            )
        rows.append(latest)
        self.rows.setText("\n".join(rows))
        self.resize_to_content()

    def set_stage(self, stage):
        self.portrait.set_state(stage)
        self.stage.setText(
            f"Lv.{stage['level']}"
            if stage.get("length_known")
            else self.language.tr("长度待定", "Length pending")
        )
        self.progress.show()
        self.progress.setValue(round(stage["progress"] * 1000))
        self.progress.setToolTip(stage["hint"])
        self.progress.setAccessibleName(stage["hint"])
        self.hint.setText(stage["hint"])

    def show_error(self):
        tr = self.language.tr
        self.stage.clear()
        self.progress.hide()
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        self.caption.setText(tr("统计状态", "Statistics"))
        self.total.setText(tr("暂不可读", "Unavailable"))
        self.total.setStyleSheet("font-size: 18px; color: #866239;")
        self.latest.setText(tr("自动重试中", "Retrying"))
        self.latest.setToolTip("")
        self.progress.setToolTip("")
        self.progress.setAccessibleName(tr("本次长度暂不可读", "Current input length unavailable"))
        self.rows.setText(
            tr("统计读取失败，正在自动重试。", "Could not read statistics. Retrying automatically.")
        )
        self.hint.setText(
            tr("本次长度暂不可读。", "Current input length is temporarily unavailable.")
        )
        self.price_note.setText(tr("参考估价暂不可用", "Reference estimate unavailable"))
        self.price_note.setToolTip("")
        self.cost_detail.setText(
            tr(
                "统计恢复后重新显示参考估价。",
                "The reference estimate will return when statistics are available.",
            )
        )
        self.resize_to_content()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#E8E2D8"))
        painter.setBrush(QColor("#FFFCF7"))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)


class Companion(QWidget):
    def __init__(self, path: Path, *, test_mode=False, state_file=None, connect_quota=None):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.language = UiLanguage(path, self)
        self.setFont(ui_font())
        self.test_mode, self.state_file = test_mode, state_file
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, sys.platform != "darwin")
        if sys.platform == "darwin":
            # Cocoa hides Qt.Tool windows when their application loses focus by default.
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setWindowTitle("TOMC" + (" — 测试数据" if test_mode else ""))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("TOMC；点击查看统计与上下文入口，拖动移动，右键打开菜单")
        self.setToolTip("点击看统计与上下文入口 · 拖动移动 · 右键菜单")
        self.setStyleSheet(STYLE)
        self.setFixedSize(250, 116)
        self.store = UsageStore(path)
        self.request_activity = RequestActivity(path)
        self.preparing_request = None
        self.request_animation_id = None
        self.animated_request_ids = set()
        from .animation_receipts import AnimationReceipts

        # Per request ID: queued / started / completed / skipped / interrupted.
        self.receipts = AnimationReceipts(Path(path).parent, demo=test_mode)
        self.receipts.recover_interrupted()
        # Establish read cursors before constructing windows. Requests completed
        # after these reads are consumed by the first refresh, never skipped.
        self.prepared_cursor = self.event_cursor = None
        try:
            self.prepared_cursor = self.request_activity.prepared_cursor()
        except (OSError, sqlite3.Error, ValueError):
            pass
        try:
            self.event_cursor = self.store.event_cursor()
        except (OSError, sqlite3.Error, ValueError):
            pass
        self.idle_stage = request_stage(None, self.language)
        self.latest_prepared_report = None
        self.latest_prepared_at = ""
        self.activity_signature = None
        from .context_library_qt import SessionNotice
        from .session_store import SessionStore

        self.session_store = SessionStore(path)
        self.context_dialog = None
        self.session_notice = SessionNotice(self.session_store, self)
        self.session_notice.changed.connect(self.refresh_session_state)
        self.session_event_seq = None
        self.session_notice_baselined = False
        self.session_notice_event = None
        self.notified_sessions = set()
        self.session_signature = None
        self.pricing = load_pricing()
        self.test_mode, self.state_file = test_mode, state_file
        self.period, self.summary, self.error = "all", None, None
        self.last_signature = None
        self.drag_origin = None
        self.was_dragged = False
        self.art = PetArt(self)
        self.art.compact_idle = True
        self.art.setGeometry(0, 0, 140, 156)
        self.art.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.art.setAccessibleName(
            self.language.tr(
                "TOMC 小猫；拖动移动，点击查看本次上下文长度",
                "TOMC cat; drag to move, click to view this input length",
            )
        )
        self.materialization = QGraphicsOpacityEffect(self.art)
        self.art.setGraphicsEffect(self.materialization)
        self.growth_opacity = 0.35
        self.art.collecting.connect(lambda: self.layout_report(False))
        self.art.collected.connect(self.finish_collection)
        self.card = QPushButton(self)
        self.card.setGeometry(91, 20, 151, 68)
        self.card.setStyleSheet(
            "QPushButton { background: #FFFCF7; border: 1px solid #E8E2D8; border-radius: 16px; } QPushButton:hover { background: #F2F5ED; } QPushButton:focus { border: 1px solid #507461; }"
        )
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
        self.latest.setStyleSheet(
            "background: transparent; color: #74685D; padding-left: 4px; font-size: 10px;"
        )
        self.close_button = QPushButton("×", self)
        self.close_button.setGeometry(223, 0, 24, 20)
        self.close_button.setAccessibleName("关闭TOMC")
        self.close_button.setStyleSheet(
            "QPushButton { background: #FFFCF7; color: #74685D; padding: 0; border-radius: 8px; }"
        )
        self.close_button.clicked.connect(self.close)
        self.pet_menu = QMenu(self)
        self.pet_menu.setStyleSheet(
            "QMenu { background: #FFFCF7; color: #443B35; border: 1px solid #E8E2D8; padding: 5px; } QMenu::item { padding: 8px 20px; } QMenu::item:selected { background: #E4ECE5; color: #345743; }"
        )
        self.statistics_action = self.pet_menu.addAction("查看统计", self.toggle_details)
        self.library_action = self.pet_menu.addAction("上下文与接续", self.open_context_library)
        self.language_menu = self.pet_menu.addMenu("中文 / English")
        self.language_actions = {}
        for code, text in (("zh", "中文"), ("en", "English")):
            action = self.language_menu.addAction(text)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, value=code: self.set_ui_language(value))
            self.language_actions[code] = action
        self.pet_menu.addSeparator()
        self.quit_action = self.pet_menu.addAction("退出 TOMC", self.close)
        self.details = Details(self)
        self.oasis = OasisCelebration(self)
        self.oasis_action = self.pet_menu.addAction("重播皇冠绿洲", self.oasis.start)
        self.reference_sheet = None
        self.pricing_action = self.pet_menu.addAction("模型与估价", self.open_reference)
        self.story_action = self.pet_menu.addAction(
            "绿洲的故事", lambda: self.open_reference(tab=1)
        )
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
        self.active_report = None
        self.pending_reports = deque()
        self.bubble_visible = False
        self.layout_report(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.language.changed.connect(self.retranslate)
        self.retranslate()
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)

    def set_ui_language(self, code):
        try:
            self.language.set_language(code)
        except OSError:
            QMessageBox.warning(
                self,
                "TOMC",
                self.language.tr(
                    "无法保存界面语言，请检查设置目录的写入权限。",
                    "Could not save the interface language. Check write access to the settings folder.",
                ),
            )
        self.details.retranslate()
        for key, action in self.language_actions.items():
            action.setChecked(key == self.language.code)

    def retranslate(self, _code=None):
        tr = self.language.tr
        self.setWindowTitle("TOMC" + (tr(" — 测试数据", " — Test data") if self.test_mode else ""))
        self.setAccessibleName(
            tr(
                "TOMC；点击查看统计与上下文入口，拖动移动，右键打开菜单",
                "TOMC; click for statistics and contexts, drag to move, right-click for the menu",
            )
        )
        self.setToolTip(
            tr(
                "点击看统计与上下文入口 · 拖动移动 · 右键菜单",
                "Click for statistics and contexts · Drag to move · Right-click for menu",
            )
        )
        self.art.setAccessibleName(
            tr(
                "TOMC 小猫；拖动移动，点击查看本次上下文长度",
                "TOMC cat; drag to move, click to view this input length",
            )
        )
        self.close_button.setAccessibleName(tr("关闭 TOMC", "Close TOMC"))
        self.statistics_action.setText(tr("查看统计", "View statistics"))
        self.library_action.setText(tr("上下文与接续", "Contexts && handoff"))
        self.quit_action.setText(tr("退出 TOMC", "Quit TOMC"))
        self.oasis_action.setText(tr("重播皇冠绿洲", "Replay the crown oasis"))
        self.pricing_action.setText(tr("模型与估价", "Models & pricing"))
        self.story_action.setText(tr("绿洲的故事", "The oasis story"))
        for key, action in self.language_actions.items():
            action.setChecked(key == self.language.code)
        self.session_signature = self.activity_signature = self.last_signature = None
        self.refresh()

    def open_reference(self, checked=False, tab=0):
        from .pricing_qt import ReferenceSheet

        if self.reference_sheet is None:
            self.reference_sheet = ReferenceSheet(self)
        self.reference_sheet.open_tab(tab)

    def set_host(self, host):
        if host != "codex":
            self.details.set_quota(
                {"status": "unsupported_host", "host": host.title(), "windows": []}
            )

    def open_context_library(self, checked=False):
        from .context_library_qt import ContextLibraryDialog

        self.details.hide()
        self.session_notice.hide()
        if self.context_dialog is None:
            self.context_dialog = ContextLibraryDialog(
                self.store.path, self, sessions=self.session_store
            )
            self.context_dialog.changed.connect(self.refresh_session_state)
        else:
            self.context_dialog.refresh()
        self.context_dialog.show()
        self.context_dialog.raise_()
        self.context_dialog.activateWindow()

    def refresh_session_state(self):
        tr = self.language.tr
        try:
            active = self.session_store.active()
            settings = self.session_store.settings()
        except (OSError, sqlite3.Error, ValueError):
            self.details.mode_status.setText(
                tr("TOMC · 会话状态暂不可读", "TOMC · Session status unavailable")
            )
            return
        enabled = settings.get("enabled", True)
        state = (
            tr("处理开启", "Processing on")
            if enabled
            else tr("全局处理暂停", "Processing paused globally")
        )
        if active:
            state += (
                tr(" · 最近会话开启", " · Latest session on")
                if active.get("enabled", True)
                else tr(" · 最近会话已关闭", " · Latest session off")
            )
        else:
            state += tr(" · 未取得会话事件", " · No session event yet")
        signature = json.dumps([settings, active], sort_keys=True)
        if signature != self.session_signature:
            self.session_signature = signature
            self.details.mode_status.setText(f"TOMC · {state}")
            self.details.resize_to_content()
        self.session_event_seq = active.get("event_seq") if active else None
        notice_event = (
            tuple(
                active.get(key) for key in ("host", "session_id", "event", "last_seen", "event_seq")
            )
            if active
            else None
        )
        changed = notice_event != self.session_notice_event
        self.session_notice_event = notice_event
        if not self.session_notice_baselined:
            # The first successful read is a baseline, including after a read
            # failure at startup. Never replay a persisted historical notice.
            self.session_notice_baselined = True
            return
        identity = (active.get("host"), active.get("session_id")) if active else None
        if (
            changed
            and active
            and active.get("event") in {"SessionStart", "UserPromptSubmit"}
            and identity[0] in {"codex", "claude"}
            and identity[1]
            and identity not in self.notified_sessions
        ):
            # These exact events come from session_hook; model_request and
            # background tool/completion events do not establish foreground focus.
            self.notified_sessions.add(identity)
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
        tr = self.language.tr
        self.refresh_session_state()
        self.refresh_request_activity()
        self.pricing = load_pricing()
        try:
            summary, error = self.store.summary(self.period), None
            if self.event_cursor is None:
                # A failed startup read has no baseline. Establish it on the
                # first successful read instead of replaying historical rows.
                self.event_cursor = self.store.event_cursor()
            events = self.store.recent_events(self.event_cursor, limit=500)
        except (OSError, sqlite3.Error, ValueError):
            summary, error = None, "read_failed"
        signature = json.dumps(
            [
                summary,
                error,
                self.period,
                self.pricing,
                events[-1]["seq"] if not error and events else self.event_cursor,
            ],
            sort_keys=True,
        )
        if signature == self.last_signature:
            return
        self.last_signature = signature
        self.summary, self.error = summary, error
        if error:
            # A transient statistics read error must not discard real pending
            # compressions or interrupt the animation already being displayed.
            if self.active_report is not None:
                self.details.show_error()
                return
            self.caption.setText(tr("统计状态", "Statistics"))
            self.number.setText(tr("暂不可读", "Unavailable"))
            self.latest.setText(tr("统计读取失败，自动重试", "Read failed · Retrying"))
            self.latest.setToolTip("")
            self.progress.setAccessibleName(
                tr("本次长度暂不可读", "Current input length unavailable")
            )
            self.card.setAccessibleName(
                tr("TOMC 统计暂不可读，正在重试", "TOMC statistics unavailable, retrying")
            )
            self.details.show_error()
            self.card.setToolTip(
                tr(
                    "统计读取失败，正在自动重试。",
                    "Could not read statistics. Retrying automatically.",
                )
            )
            self.layout_report(True)
            self.report_timer.start(6000)
        else:
            self.render_summary(summary, events)
        if self.state_file:
            self.state_file.write_text(
                json.dumps(
                    {
                        "summary": summary,
                        "error": error,
                        "period": self.period,
                        "test_mode": self.test_mode,
                        "language": self.language.code,
                        "pricing": self.pricing,
                        "growth": growth_state(summary, self.language) if summary else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def refresh_request_activity(self):
        from .context_library_qt import request_activity_text

        tr = self.language.tr

        try:
            if self.prepared_cursor is None:
                self.prepared_cursor = self.request_activity.prepared_cursor()
            active, latest = self.request_activity.active(), self.request_activity.last()
            prepared = self.request_activity.prepared_events(self.prepared_cursor)
        except (OSError, sqlite3.Error, ValueError):
            self.preparing_request = None
            self.activity_signature = None
            self.details.request_status.setText(
                tr("自动请求状态暂不可读", "Request status unavailable")
            )
            if self.active_report is None:
                self.apply_pet_stage(request_stage(None, self.language))
                self.caption.setText(tr("自动请求", "Automatic request"))
                self.number.setText(tr("状态未知", "Status unknown"))
                self.latest.setText(tr("状态读取失败，自动重试", "Status read failed · Retrying"))
                self.layout_report(True)
                self.report_timer.start(3000)
            self.start_collection()
            self.update_materialization()
            return
        if latest and latest["state"] == "preparing" and active is None:
            latest = {**latest, "stale": True}
        signature = json.dumps([active, latest], sort_keys=True)
        if signature != self.activity_signature:
            self.activity_signature = signature
            self.details.request_status.setText(
                request_activity_text(active or latest, self.language)
            )
            detail = tr(
                "仅显示本地代理实际观察的请求；不代表其他会话已通过代理。",
                "Only requests observed by the local gateway are shown. This does not confirm coverage of other sessions.",
            )
            if latest:
                before, after = latest.get("before_tokens"), latest.get("after_tokens")
                if before is not None and after is not None:
                    detail += tr(
                        "\n请求文本估算：{before:,} → {after:,} tokens。",
                        "\nRequest text estimate: {before:,} → {after:,} tokens.",
                        before=before,
                        after=after,
                    )
                if latest.get("provider_input_tokens") is not None:
                    detail += tr(
                        "\n实测模型输入：{count:,} tokens",
                        "\nMeasured provider input: {count:,} tokens",
                        count=latest["provider_input_tokens"],
                    )
                    if latest.get("provider_cached_tokens") is not None:
                        detail += tr(
                            "；缓存：{count:,}",
                            "; cached: {count:,}",
                            count=latest["provider_cached_tokens"],
                        )
                    detail += tr(
                        "。这是使用量，不是节省差额。", ". This is usage, not measured savings."
                    )
                else:
                    detail += tr(
                        "\n模型实测用量尚未返回；未测量账单差异。",
                        "\nProvider usage is not available yet; bill differences have not been measured.",
                    )
            self.details.request_usage_detail.setText(detail)
            self.details.resize_to_content()
        previous = self.preparing_request
        self.preparing_request = active
        if active:
            if self.active_report is None:
                self.report_timer.stop()
                # Unknown length stays neutral while earlier completed work may
                # still enter the queue. Busy requests never block that queue.
                self.show_request_busy()
        elif previous:
            if self.request_animation_id and self.active_report is None:
                self.art.animation_timer.stop()
                self.art.phase = None
                self.art.update()
                self.receipts.record(
                    "interrupted", self.request_animation_id, reason="report_dismissed"
                )
                self.request_animation_id = None
            if self.active_report is None:
                self.caption.setText(
                    (tr("演示 · ", "Demo · ") if self.test_mode else "")
                    + tr("自动请求", "Automatic request")
                )
                state_text = {
                    "prepared": ("准备完成", "Prepared"),
                    "forwarded": ("已转发", "Forwarded"),
                    "passthrough": ("保留原文", "Unchanged"),
                    "failed": ("请求失败", "Request failed"),
                }
                self.number.setText(
                    tr(*state_text.get((latest or {}).get("state"), ("等待新事件", "Waiting")))
                )
                self.latest.setText(tr("详情中查看请求状态", "See Details for status"))
                self.layout_report(True)
                self.report_timer.start(3000)
            self.start_collection()
        for event in prepared:
            stage_report = {
                "request_id": event["request_id"],
                "usable": True,
                "stage_only": True,
                "context_input_tokens": event["context_input_tokens"],
            }
            self.receipts.record(
                "queued", event["request_id"], context_input_tokens=event["context_input_tokens"]
            )
            self.latest_prepared_report = stage_report
            self.latest_prepared_at = event["prepared_utc"]
            self.idle_stage = growth_state({"last_preparation": stage_report}, self.language)
            self.enqueue_report(stage_report)
            self.prepared_cursor = event["seq"]
        self.start_collection()

    def show_request_busy(self):
        if self.active_report is not None:
            return
        tr = self.language.tr
        if self.active_report is None:
            self.apply_pet_stage(
                request_stage(
                    (self.preparing_request or {}).get("context_input_tokens"), self.language
                )
            )
        self.caption.setText(
            (tr("演示 · ", "Demo · ") if self.test_mode else "")
            + tr("自动请求", "Automatic request")
        )
        self.number.setText(tr("检查 / 压缩中", "Preparing"))
        count = (self.preparing_request or {}).get("active_count", 1)
        self.latest.setText(
            tr("{count} 个请求正在准备", "Preparing {count} requests", count=count)
            if count > 1
            else tr("CPU 正在准备上下文", "Preparing on CPU")
        )
        self.layout_report(True)

    def render_summary(self, summary, events=()):
        tr = self.language.tr
        values = display_values(summary, self.language)
        growth = growth_state(summary, self.language)
        if self.latest_prepared_report is not None and self.latest_prepared_at > (
            summary.get("last_preparation") or {}
        ).get("recorded_at", ""):
            growth = growth_state({"last_preparation": self.latest_prepared_report}, self.language)
        hint = growth_hint(growth, self.language)
        self.idle_stage = growth
        self.oasis_action.setVisible(growth["level"] == 4 or self.test_mode)
        self.number.setStyleSheet("font-size: 20px; font-weight: 600; color: #443B35;")
        self.number.setText("—")
        self.caption.setText(tr("上下文估算", "Context estimate"))
        last = summary.get("last_preparation")
        latest = tr("等待本次上下文", "Waiting for context")
        long_latest = tr("等待 TOMC 准备上下文。", "Waiting for TOMC to prepare context.")
        if last and last["usable"]:
            delta = last["reduced_tokens"]
            latest = (
                tr("本次增加 {count:,}", "Latest: {count:,} more", count=abs(delta))
                if delta < 0
                else tr("本次减少 {count:,}", "Latest: {count:,} fewer", count=abs(delta))
            )
            long_latest = tr(
                "最近一次  {before:,} → {after:,} tokens",
                "Latest: {before:,} → {after:,} tokens",
                before=last["input_tokens"],
                after=last["memory_tokens"],
            )
            self.report_text(last)
        elif last:
            latest, long_latest = (
                tr("本次无可用输出", "No usable output"),
                tr(
                    "最近一次未生成可用上下文，未计入减少量。",
                    "The latest preparation had no usable output and is excluded from reductions.",
                ),
            )
        self.latest.setText(self.estimate_note() if last and last["usable"] else latest)
        self.latest.setToolTip(long_latest)
        self.card.setAccessibleName(
            tr(
                "{name}，{latest}，点击查看累计统计",
                "{name}, {latest}, click for total statistics",
                name=growth["name"],
                latest=long_latest,
            )
        )
        self.card.setToolTip(
            tr(
                "{name} · {hint}\n仅上下文估算，非账单节省。点击展开统计。",
                "{name} · {hint}\nContext estimate, not bill savings. Click for statistics.",
                name=growth["name"],
                hint=hint,
            )
        )
        self.details.set_summary(summary, values, growth, long_latest)
        at = last["recorded_at"] if last else None
        if events:
            for event in events:
                self.enqueue_report(event)
                self.event_cursor = event["seq"]
            self.start_collection()
            if self.bubble_visible and self.report_timer.remainingTime() > 1800:
                self.report_timer.start(1800)
        self.initialized, self.last_at = True, at
        if self.active_report and self.bubble_visible:
            self.report_text(self.active_report)
        self.restore_displayed_stage()
        if self.preparing_request:
            self.show_request_busy()

    def start_collection(self):
        if self.active_report or not self.pending_reports:
            return
        self.active_report = self.pending_reports.popleft()
        stage = growth_state({"last_preparation": self.active_report}, self.language)
        self.apply_pet_stage(stage)
        identifier = self.active_report.get("request_id")
        envelope = any(
            marker in str(self.active_report.get("counter", "")).lower()
            for marker in ("request-json", "entire-payload")
        )
        if (
            not stage["length_known"]
            or identifier in self.animated_request_ids
            or envelope
            and not (
                self.active_report.get("stage_only") or self.active_report.get("animate_prepared")
            )
        ):
            # A usage receipt for an already played request is never replayed.
            skip = (
                "already_animated"
                if identifier in self.animated_request_ids
                else "length_unknown"
                if not stage["length_known"]
                else "envelope_estimate_only"
            )
            self.receipts.record(
                "skipped",
                identifier,
                stage=stage["level"],
                context_input_tokens=stage["input_tokens"],
                reason=skip,
            )
            self.finish_collection()
            return
        if identifier:
            self.animated_request_ids.add(identifier)
            self.request_animation_id = identifier
            self.receipts.record(
                "started",
                identifier,
                stage=stage["level"],
                context_input_tokens=stage["input_tokens"],
            )
        self.layout_report(False)
        self.report_timer.stop()
        self.art.collect()

    def enqueue_report(self, report):
        """Join the numeric receipt to the same prepared event without replay."""

        def merge_receipt(receipt, prepared):
            merged = {**receipt, "animate_prepared": True}
            length = receipt.get("context_input_tokens")
            if type(length) is not int or length < 0:
                merged["context_input_tokens"] = prepared.get("context_input_tokens")
            return merged

        identifier = report.get("request_id")
        if identifier:
            if self.active_report and self.active_report.get("request_id") == identifier:
                if self.active_report.get("stage_only") and not report.get("stage_only"):
                    self.active_report = merge_receipt(report, self.active_report)
                elif report.get("stage_only") and identifier not in self.animated_request_ids:
                    # A late prepared page can arrive after the numeric report.
                    # It still owns one animation and must not be discarded.
                    self.pending_reports.appendleft(dict(report))
                return
            for index, pending in enumerate(self.pending_reports):
                if pending.get("request_id") == identifier:
                    if pending.get("stage_only") and not report.get("stage_only"):
                        self.pending_reports[index] = merge_receipt(report, pending)
                    elif report.get("stage_only"):
                        self.pending_reports[index] = merge_receipt(pending, report)
                    return
        self.pending_reports.append(dict(report))

    def report_text(self, report):
        tr = self.language.tr
        if report.get("stage_only"):
            stage = growth_state({"last_preparation": report}, self.language)
            self.caption.setText(tr("上下文已准备", "Context prepared"))
            self.number.setText(tr("第 {level} 阶段", "Stage {level}/4", level=stage["level"]))
            self.latest.setText(
                tr(
                    "本次输入 {count:,} tokens",
                    "Input: {count:,} tokens",
                    count=stage["input_tokens"],
                )
            )
            return
        if report["usable"]:
            delta = report["reduced_tokens"]
            self.caption.setText(
                (tr("演示 · ", "Demo · ") if self.test_mode else "")
                + (
                    tr("本次估算增加", "Estimated increase")
                    if delta < 0
                    else tr("本次估算减少", "Estimated reduction")
                )
            )
            self.number.setText(
                percent_text(context_percent(report["input_tokens"], report["memory_tokens"]))
            )
        else:
            self.caption.setText(tr("本次准备", "Latest preparation"))
            self.number.setText(tr("无可用输出", "No usable output"))
            self.number.setStyleSheet("font-size: 16px; font-weight: 600; color: #443B35;")
        self.latest.setText(tr("上下文估算 · 非账单节省", "Context estimate, not savings"))

    def estimate_note(self):
        return (
            self.language.tr("参考估价 · 查看详情", "Pricing reference in Details")
            if self.pricing
            else self.language.tr("参考模型可在估价中选择", "Choose a model in Pricing")
        )

    def finish_collection(self):
        if self.request_animation_id:
            self.receipts.record("completed", self.request_animation_id, stage=self.art.level)
            self.request_animation_id = None
            if self.preparing_request and self.active_report is None:
                self.show_request_busy()
                return
        if self.active_report:
            self.report_text(self.active_report)
        self.layout_report(True)
        self.report_timer.start(1800 if self.pending_reports else 6000)

    def layout_report(self, visible):
        self.update_materialization()
        anchor = self.mapToGlobal(self.art.geometry().center())
        self.bubble_visible = visible
        pet_width = ACTIVE_WIDTH if self.art.phase is not None else IDLE_WIDTH
        pet_height = round(pet_width * 156 / 140)
        height = max(110, pet_height) if visible else pet_height
        pet_x, pet_y = (185 if visible else 0), (height - pet_height) // 2
        self.setFixedSize(pet_x + pet_width, height)
        self.art.setGeometry(pet_x, pet_y, pet_width, pet_height)
        self.card.setGeometry(8, 8, 170, 94)
        self.caption.setGeometry(13, 8, 144, 17)
        self.number.setGeometry(13, 26, 144, 30)
        self.progress.setGeometry(23, 65, 140, 3)
        self.latest.setGeometry(12, 81, 166, 20)
        self.close_button.setGeometry(pet_x + pet_width - 20, 0, 20, 20)
        self.close_button.setVisible(self.underMouse())
        for part in (self.card, self.caption, self.number, self.progress, self.latest):
            part.setVisible(visible)
        point = anchor - self.art.geometry().center()
        area = self.screen().availableGeometry()
        point.setX(max(area.left(), min(point.x(), area.right() - self.width() + 1)))
        point.setY(max(area.top(), min(point.y(), area.bottom() - self.height() + 1)))
        self.move(point)
        if self.session_notice.isVisible():
            self.position_session_notice()

    def update_materialization(self):
        # Keep actual work legible even when the cosmetic idle form is faint.
        # Language changes and summary refreshes must not dim an active animation.
        working = self.preparing_request is not None or self.art.phase is not None
        self.materialization.setOpacity(1.0 if working else self.growth_opacity)

    def apply_pet_stage(self, stage):
        self.art.set_state(stage)
        self.growth_opacity = stage["opacity"]
        self.progress.setValue(round(stage["progress"] * 1000))
        self.progress.setAccessibleName(stage["hint"])
        self.details.set_stage(stage)
        self.update_materialization()

    def restore_displayed_stage(self):
        if self.active_report is not None:
            stage = growth_state({"last_preparation": self.active_report}, self.language)
        elif self.preparing_request is not None:
            stage = request_stage(self.preparing_request.get("context_input_tokens"), self.language)
        else:
            stage = self.idle_stage
        self.apply_pet_stage(stage)

    def hide_report(self):
        self.layout_report(False)
        self.active_report = None
        self.start_collection()
        self.restore_displayed_stage()

    def enterEvent(self, event):
        self.close_button.show()

    def leaveEvent(self, event):
        self.close_button.hide()

    def set_period(self, period):
        self.period = period
        self.last_signature = None
        self.refresh()
        self.details.resize_to_content()

    def toggle_details(self):
        if self.details.isVisible():
            self.details.hide()
            return
        self.details.resize_to_content()
        self.position_details()
        self.details.show()

    def position_details(self):
        area = self.screen().availableGeometry()
        point = self.mapToGlobal(
            QPoint(self.width() - self.details.width(), -self.details.height() - 8)
        )
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
        if self.request_animation_id:
            self.receipts.record("interrupted", self.request_animation_id, reason="ui_closed")
            self.request_animation_id = None
        self.details.close()
        super().closeEvent(event)
        QApplication.instance().quit()


def run(path, test_mode=False, state_file=None, host="codex"):
    app = QApplication(sys.argv[:1])
    load_preview_fonts()
    app.setApplicationName("TOMC")
    app.setFont(ui_font())
    digest = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:24]
    lock = QLockFile(str(Path(tempfile.gettempdir()) / f"tomc-pet-{digest}.lock"))
    if not lock.tryLock(0):
        return
    widget = Companion(
        path,
        test_mode=test_mode,
        state_file=state_file,
        connect_quota=host == "codex" and not test_mode,
    )
    widget.set_host(host)
    widget.show()
    if sys.platform == "darwin":
        # Explicit launch should reveal the pet; background refreshes never take focus.
        widget.raise_()
        widget.activateWindow()
    try:
        app.exec()
    finally:
        lock.unlock()
