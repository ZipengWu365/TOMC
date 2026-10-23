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
    QFileDialog,
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

from .cost_estimate import load_pricing
from .macos_ui import install_macos_style, is_macos, text_style, tokens
from .oasis_qt import OasisCelebration
from .pet_art import ACTIVE_WIDTH, IDLE_WIDTH, PetArt
from .pet_growth import growth_state, request_stage
from .quota_qt import QuotaReader
from .request_activity import RequestActivity
from .savings import savings_report
from .savings_qt import (
    ElidedLabel,
    SavingsChart,
    compact_tokens,
    discard,
    local_time,
    money_text,
    rule,
    total_tokens,
)
from .ui_language import UiLanguage, ui_font
from .usage import UsageStore

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
    if is_macos():
        text_style(item, size, color, bold)
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
        color = tokens(self)["secondary"] if is_macos() else "#796D60"
        painter.setPen(QPen(QColor(color), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(10, 10, 18, 18)
        painter.drawLine(18, 10, 10, 18)


DASHBOARD_STYLE = """
QWidget#periods { background: #EEEAE2; border-radius: 7px; }
QPushButton#period { color: #706659; border-radius: 5px; padding: 1px; font-size: 11px; }
QPushButton#period:checked { background: #FFFCF7; color: #354F42; font-weight: 600; }
QPushButton#language { color: #706659; font-size: 10px; padding: 2px 6px; border-radius: 6px; }
QPushButton#language:checked { background: #E4ECE5; color: #345743; font-weight: 600; }
QPushButton#link { color: #3F6B53; font-size: 11px; padding: 2px 5px; border-radius: 5px; }
QPushButton#link:hover { background: #E4ECE5; }
QPushButton#chip { background: #F1EDE4; color: #4E5F52; font-size: 10px; padding: 2px 8px; border-radius: 6px; }
QPushButton#chip:hover { background: #E4ECE5; color: #345743; }
QPushButton#foot { font-size: 10px; color: #706659; padding: 3px 5px; }
QFrame#rule { background: #EEE9DF; border: none; }
QScrollArea { background: transparent; border: none; }
"""


class RecordRow(QWidget):
    """One saved context: open it, copy its handoff prompt or export a bundle."""

    def __init__(self, dashboard, record):
        super().__init__()
        self.dashboard, self.record = dashboard, record
        tr = dashboard.language.tr
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        if is_macos():
            self.setObjectName("card")
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            layout.setContentsMargins(10, 9, 10, 9)
            layout.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = ElidedLabel(
            record.get("title") or tr("未命名上下文", "Untitled context"),
            12,
            "#443B35",
            bold=True,
        )
        self.title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title.setToolTip(tr("在上下文库中打开", "Open in the context library"))
        top.addWidget(self.title, 1)
        before = record.get("input_estimated_tokens")
        after = record.get("output_estimated_tokens")
        self.tokens = label(
            tr(
                "{before} → {after}",
                "{before} → {after}",
                before=compact_tokens(before),
                after=compact_tokens(after),
            )
            if isinstance(before, int) and isinstance(after, int)
            else "",
            10,
            "#52705D",
        )
        self.tokens.setToolTip(
            tr("这份上下文压缩前后的 tokens", "Context tokens before and after compression")
        )
        top.addWidget(self.tokens)
        layout.addLayout(top)
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        from .context_library_qt import host_label

        self.meta = ElidedLabel(
            f"{host_label(record.get('origin_host') or record.get('host'), dashboard.language)}"
            f" · {local_time(record.get('created_utc'))}",
        )
        bottom.addWidget(self.meta, 1)
        self.copy_button = QPushButton(tr("复制提示词", "Copy prompt"))
        self.copy_button.setObjectName("chip")
        self.copy_button.setToolTip(
            tr(
                "复制完整的接续提示词，粘贴给另一个 Agent 即可继续",
                "Copy the complete handoff prompt; paste it into another agent to continue",
            )
        )
        self.copy_button.clicked.connect(lambda: dashboard.copy_record(record))
        self.export_button = QPushButton(tr("导出", "Export"))
        self.export_button.setObjectName("chip")
        self.export_button.setToolTip(
            tr(
                "导出便携包，在另一台电脑上导入后继续",
                "Export a portable bundle to import on another computer",
            )
        )
        self.export_button.clicked.connect(lambda: dashboard.export_record(record))
        bottom.addWidget(self.copy_button)
        bottom.addWidget(self.export_button)
        layout.addLayout(bottom)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.title.geometry().contains(
            event.position().toPoint()
        ):
            self.dashboard.open_record(self.record)


class Details(QWidget):
    """Savings dashboard: tokens and money saved per model, then handoff and export."""

    RECORD_LIMIT = 3
    MODEL_LIMIT = 3

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        from .context_library import ContextLibrary

        self.owner = owner
        self.language = owner.language
        self.library = ContextLibrary(owner.store.path)
        self.quota_state = {"status": "unavailable", "windows": []}
        self.report = self.message = None
        self.failed = False
        self.records = []
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if not is_macos():
            self.setStyleSheet(STYLE + DASHBOARD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        if is_macos():
            layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(0)
        heading = QHBoxLayout()
        heading.setSpacing(5)
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
        self.language_buttons = {}
        for code, text in (("zh", "中文"), ("en", "English")):
            button = QPushButton(text)
            button.setObjectName("language")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=code: owner.set_ui_language(value))
            self.language_buttons[code] = button
            heading.addWidget(button)
        self.close_button = DismissButton(self.language)
        self.close_button.clicked.connect(self.hide)
        heading.addWidget(self.close_button)
        layout.addLayout(heading)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        layout.addSpacing(3)
        layout.addWidget(self.progress)
        layout.addSpacing(8)
        self.body = QWidget()
        self.body.setAutoFillBackground(False)
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        period_surface = QWidget()
        period_surface.setObjectName("periods")
        periods = QHBoxLayout(period_surface)
        periods.setContentsMargins(2, 2, 2, 2)
        periods.setSpacing(2)
        self.buttons = {}
        for key in ("today", "7d", "all"):
            button = QPushButton()
            button.setObjectName("period")
            button.setFixedHeight(30 if is_macos() else 22)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, p=key: owner.set_period(p))
            self.buttons[key] = button
            periods.addWidget(button)
        body.addWidget(period_surface)
        body.addSpacing(10)
        hero = QHBoxLayout()
        hero.setSpacing(12)
        column = QVBoxLayout()
        column.setSpacing(0)
        self.caption = label(size=10, color="#706659")
        self.total = label(size=22, color="#345743", bold=True)
        column.addWidget(self.caption)
        column.addWidget(self.total)
        hero.addLayout(column, 1)
        column = QVBoxLayout()
        column.setSpacing(0)
        self.money_caption = label(size=10, color="#706659")
        self.money = label(size=22, bold=True)
        column.addWidget(self.money_caption)
        column.addWidget(self.money)
        hero.addLayout(column, 1)
        body.addLayout(hero)
        body.addSpacing(8)
        self.model_rows = QVBoxLayout()
        self.model_rows.setSpacing(3)
        body.addLayout(self.model_rows)
        pricing = QHBoxLayout()
        pricing.setSpacing(4)
        self.basis = ElidedLabel()
        pricing.addWidget(self.basis, 1)
        self.price_button = QPushButton()
        self.price_button.setObjectName("link")
        self.price_button.clicked.connect(owner.open_reference)
        pricing.addWidget(self.price_button)
        body.addLayout(pricing)
        body.addSpacing(6)
        chart_heading = QHBoxLayout()
        self.chart_title = label(size=10, color="#706659")
        self.chart_today = label(size=10, color="#706659")
        chart_heading.addWidget(self.chart_title)
        chart_heading.addStretch()
        chart_heading.addWidget(self.chart_today)
        body.addLayout(chart_heading)
        body.addSpacing(3)
        self.chart = SavingsChart(self.language, self)
        if is_macos():
            self.chart.setFixedHeight(52)
        body.addWidget(self.chart)
        body.addSpacing(5)
        self.stats = ElidedLabel()
        body.addWidget(self.stats)
        body.addSpacing(10)
        body.addWidget(rule())
        body.addSpacing(8)
        records = QHBoxLayout()
        records.setSpacing(2)
        self.records_title = label(size=12, bold=True)
        records.addWidget(self.records_title)
        records.addStretch()
        self.import_button = QPushButton()
        self.import_button.setObjectName("link")
        self.import_button.clicked.connect(self.import_bundle)
        records.addWidget(self.import_button)
        self.library_button = QPushButton()
        self.library_button.setObjectName("link")
        self.library_button.clicked.connect(owner.open_context_library)
        records.addWidget(self.library_button)
        body.addLayout(records)
        body.addSpacing(6)
        self.record_list = QVBoxLayout()
        self.record_list.setSpacing(9)
        body.addLayout(self.record_list)
        self.records_empty = label(size=10, color="#706659")
        self.records_empty.setWordWrap(True)
        if is_macos():
            self.records_empty.setContentsMargins(0, 8, 0, 8)
        body.addWidget(self.records_empty)
        self.records_message = label(size=10, color="#3F6B53")
        self.records_message.setTextFormat(Qt.TextFormat.PlainText)
        self.records_message.setWordWrap(True)
        self.records_message.hide()
        body.addSpacing(4)
        body.addWidget(self.records_message)
        body.addSpacing(10)
        body.addWidget(rule())
        body.addSpacing(6)
        self.mode_status = ElidedLabel(color="#52705D")
        body.addWidget(self.mode_status)
        self.request_status = ElidedLabel()
        body.addWidget(self.request_status)
        footer = QHBoxLayout()
        footer.setSpacing(4)
        self.quota_title = label(size=10, color="#706659")
        self.quota_value = label(size=10, color="#706659")
        footer.addWidget(self.quota_title)
        footer.addWidget(self.quota_value)
        footer.addStretch()
        self.quit_button = QPushButton()
        self.quit_button.setObjectName("foot")
        self.quit_button.clicked.connect(owner.close)
        footer.addWidget(self.quit_button)
        body.addLayout(footer)
        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.body)
        self.scroll_area.viewport().setAutoFillBackground(False)
        layout.addWidget(self.scroll_area)
        self.request_status.setText(
            self.language.tr("自动请求：尚未观察到", "Automatic requests: none observed")
        )
        install_macos_style(self, variant="popover")
        self.retranslate()
        self.language.changed.connect(self.retranslate)

    def retranslate(self, _code=None):
        tr = self.language.tr
        if is_macos():
            self.setFixedWidth(400 if self.language.code == "zh" else 420)
        else:
            self.setFixedWidth(300 if self.language.code == "zh" else 324)
        self.setAccessibleName(tr("TOMC 省 token 看板", "TOMC token savings dashboard"))
        for code, button in self.language_buttons.items():
            button.setChecked(code == self.language.code)
            button.setAccessibleName("中文" if code == "zh" else "English")
        self.demo_badge.setText(tr("演示", "Demo"))
        for key, zh, en in (
            ("today", "今天", "Today"),
            ("7d", "近七天", "7 days"),
            ("all", "累计", "All time"),
        ):
            self.buttons[key].setText(tr(zh, en))
            self.buttons[key].setAccessibleName(
                tr("查看{period}节省", "Show savings for {period}", period=tr(zh, en))
            )
        self.caption.setText(tr("节省 tokens", "Tokens saved"))
        self.money_caption.setText(tr("省下的钱", "Money saved"))
        self.price_button.setText(tr("模型与估价 ›", "Models && pricing ›"))
        self.price_button.setToolTip(
            tr(
                "选择参考模型，或改按缓存读取价折算",
                "Choose the reference model, or value savings at the cached-read price",
            )
        )
        self.chart_title.setText(tr("每日节省 · 近 14 天", "Saved per day · last 14 days"))
        self.records_title.setText(tr("转移与导出", "Handoff & export"))
        self.import_button.setText(tr("导入", "Import"))
        self.import_button.setToolTip(
            tr(
                "导入另一台电脑导出的上下文包",
                "Import a context bundle exported on another computer",
            )
        )
        self.library_button.setText(tr("全部记录 ›", "All records ›"))
        self.quit_button.setText(tr("退出 TOMC", "Quit TOMC"))
        self.set_quota(self.quota_state)
        if self.failed:
            self.show_error()
        elif self.report is not None:
            self.render_report(self.report)
        self.render_records()
        self.resize_to_content()

    @staticmethod
    def layout_height(layout, width):
        # Without wrapped labels Qt reports no height-for-width; use the size hint.
        if layout.hasHeightForWidth():
            return layout.totalHeightForWidth(width)
        return layout.totalSizeHint().height()

    def resize_to_content(self):
        # Style-sheet fonts apply on polish; measure only after that.
        self.ensurePolished()
        for child in self.body.findChildren(QWidget):
            child.ensurePolished()
        margins = self.layout().contentsMargins()
        width = self.width() - margins.left() - margins.right()
        self.scroll_area.setFixedHeight(0)
        self.layout().activate()
        header = self.layout_height(self.layout(), self.width())
        maximum = max(160, self.screen().availableGeometry().height() - header - 24)
        desired = self.layout_height(self.body.layout(), width)
        if desired > maximum:
            # Reserve the scrollbar before wrapping so a new scrollbar cannot clip a line.
            width -= self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            desired = self.layout_height(self.body.layout(), width)
        self.body.setMinimumHeight(desired)
        self.scroll_area.setFixedHeight(min(desired, maximum))
        self.layout().activate()
        self.resize(self.width(), self.layout_height(self.layout(), self.width()))
        if self.isVisible():
            self.owner.position_details()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_report()
        self.refresh_records()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.message = None
        self.records_message.hide()

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
            detail = "\n".join(
                tr(
                    "{bucket} {period}剩余 {value:g}%",
                    "{bucket} {period}: {value:g}% left",
                    bucket=w["bucket"],
                    period=quota_period(w["period"], self.language),
                    value=w["remaining"],
                )
                for w in windows
            )
        elif state.get("status") == "unsupported_host":
            host = state.get("host", "Host")
            self.quota_title.setText(tr("{host} 额度", "{host} allowance", host=host))
            self.quota_value.setText(tr("未接入", "Not connected"))
            detail = tr(
                "尚未接入 {host} 账户额度。",
                "{host} account allowance is not connected.",
                host=host,
            )
        else:
            self.quota_title.setText(tr("Codex 额度", "Codex allowance"))
            self.quota_value.setText(
                tr("读取中", "Loading")
                if state.get("status") == "loading"
                else tr("暂不可读", "Unavailable")
            )
            detail = tr(
                "需要已登录的 Codex CLI 才能读取额度。",
                "A signed-in Codex CLI is needed to read the allowance.",
            )
        for item in (self.quota_title, self.quota_value):
            item.setToolTip(detail)

    def set_summary(self, summary, growth):
        """Statistics changed: reread the savings; saved contexts reload while open."""
        self.set_stage(growth)
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        self.refresh_report()
        if self.isVisible():
            self.refresh_records()

    def refresh_report(self):
        try:
            report = savings_report(
                self.owner.store.path, self.owner.period, reference=self.owner.pricing
            )
        except (OSError, sqlite3.Error, ValueError):
            self.show_error()
            return
        self.render_report(report)
        self.resize_to_content()

    def render_report(self, report):
        tr = self.language.tr
        self.report, self.failed = report, False
        for key, button in self.buttons.items():
            button.setChecked(key == report["period"])
        saved = report["tokens_saved"]
        self.total.setText(total_tokens(saved))
        self.total.setStyleSheet(
            f"font-size: 22px; font-weight: 600; color: {'#866239' if saved < 0 else '#345743'};"
        )
        self.money.setText(money_text(report["money"]))
        self.money.setStyleSheet("font-size: 22px; font-weight: 600; color: #443B35;")
        if is_macos():
            text_style(self.total, 22, "#866239" if saved < 0 else "#345743", True)
            text_style(self.money, 22, bold=True)
        self.money.setToolTip(
            tr(
                "按每次请求所用模型的列表价折算",
                "Valued at the list price of the model each request used",
            )
        )
        while self.model_rows.count():
            row = self.model_rows.takeAt(0).layout()
            while row.count():
                discard(row.takeAt(0).widget())
            row.deleteLater()
        models = report["models"]
        shown = models[: self.MODEL_LIMIT]
        if len(models) > self.MODEL_LIMIT:
            rest = models[self.MODEL_LIMIT - 1 :]
            shown = models[: self.MODEL_LIMIT - 1] + [
                {
                    "model": "others",
                    "label": tr("其他 {count} 个", "{count} others", count=len(rest)),
                    "hosts": [],
                    "bases": [],
                    "rates": [],
                    "tokens_saved": sum(m["tokens_saved"] for m in rest),
                    "money": sum(m["money"] or 0 for m in rest)
                    if any(m["money"] is not None for m in rest)
                    else None,
                }
            ]
        for model in shown:
            row = self.model_row(model, report["mode"])
            self.model_rows.addLayout(row)
            # A visible parent would show new children only on the next event
            # loop pass; show them now so the height measured below includes them.
            for index in range(row.count()):
                row.itemAt(index).widget().show()
        cached = report["mode"] == "cached"
        if not models:
            self.basis.setText(tr("暂无节省记录", "No savings yet"))
        elif report["money"] is None:
            self.basis.setText(
                tr("选择参考模型后显示金额", "Choose a reference model to see money saved")
            )
        else:
            self.basis.setText(
                tr("按各模型缓存读取价", "At each model's cached-read price")
                if cached
                else tr("按各模型输入价", "At each model's input price")
            )
        start = None
        if report["period"] != "all":
            days = 6 if report["period"] == "7d" else 0
            start = report["daily"][-1 - days]["day"] if len(report["daily"]) > days else None
        self.chart.set_days(report["daily"], start)
        today = report["daily"][-1]["tokens_saved"] if report["daily"] else 0
        self.chart_today.setText(tr("今天 {count}", "Today {count}", count=compact_tokens(today)))
        count = report["preparations"]
        self.stats.setText(
            tr(
                "{count:,} 次压缩 · 平均每次节省 {average:,} tokens",
                "{count:,} compressions · {average:,} tokens saved each on average",
                count=count,
                average=round(saved / count) if count else 0,
            )
            if count
            else tr("这段时间还没有压缩", "No compressions in this period")
        )
        self.stats.setToolTip(
            tr(
                "压缩前 {before:,} → 压缩后 {after:,} tokens",
                "{before:,} → {after:,} tokens before and after compression",
                before=report["input_tokens"],
                after=report["output_tokens"],
            )
        )

    def model_row(self, model, mode):
        tr = self.language.tr
        from .context_library_qt import host_label

        row = QHBoxLayout()
        row.setSpacing(6)
        hosts = " · ".join(host_label(host, self.language) for host in model.get("hosts", []))
        name = model["label"] or tr("未定价", "Unpriced")
        title = ElidedLabel(name, 11, "#443B35")
        tokens = label(compact_tokens(model["tokens_saved"]), 11, "#52705D")
        tokens.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tokens.setFixedWidth(66 if is_macos() else 54)
        money = label(money_text(model["money"]), 11, "#443B35")
        money.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        money.setFixedWidth(72 if is_macos() else 58)
        rates = model.get("rates") or []
        if model["money"] is None:
            tip = tr(
                "未找到这个模型的价格；可在「模型与估价」选择参考模型。",
                "No price was found for this model; choose a reference model in Models & pricing.",
            )
        else:
            price = " / ".join(f"${rate:g}" for rate in rates)
            unit = (
                tr("百万缓存读取 tokens", "per million cached-read tokens")
                if mode == "cached"
                else tr("百万输入 tokens", "per million input tokens")
            )
            basis = model.get("bases", [])
            source = (
                tr("按请求记录的模型", "model recorded with each request")
                if "request" in basis
                else tr("按安装时识别的默认模型", "default model detected at installation")
                if "detected" in basis
                else tr("按选择的参考模型", "selected reference model")
            )
            tip = tr(
                "{name}：{price} / {unit}（{source}）",
                "{name}: {price} {unit} ({source})",
                name=name,
                price=price,
                unit=unit,
                source=source,
            )
            if len(rates) > 1:
                tip += tr(
                    "\n超长请求按长上下文价折算。",
                    "\nVery long requests use the long-context price.",
                )
        tip += tr(
            "\n节省 {count:,} tokens",
            "\n{count:,} tokens saved",
            count=model["tokens_saved"],
        )
        if hosts:
            tip += tr("\n来自 {hosts}", "\nFrom {hosts}", hosts=hosts)
        for item in (title, tokens, money):
            item.setToolTip(tip)
        row.addWidget(title, 1)
        row.addWidget(tokens)
        row.addWidget(money)
        return row

    def refresh_records(self):
        try:
            self.records = self.library.list(limit=self.RECORD_LIMIT)
        except (OSError, sqlite3.Error, ValueError):
            self.records = []
        self.render_records()
        self.resize_to_content()

    def render_records(self):
        tr = self.language.tr
        while self.record_list.count():
            discard(self.record_list.takeAt(0).widget())
        for record in self.records:
            row = RecordRow(self, record)
            self.record_list.addWidget(row)
            row.show()
        self.records_empty.setVisible(not self.records)
        self.records_empty.setText(
            tr(
                "TOMC 压缩后的上下文会出现在这里：复制提示词给另一个 Agent，或导出到另一台电脑。",
                "Compressed contexts appear here. Copy a prompt for another agent, "
                "or export one to another computer.",
            )
        )
        if self.message:
            zh, en, values = self.message
            self.records_message.setText(tr(zh, en, **values))
            self.records_message.show()
        else:
            self.records_message.hide()

    def show_message(self, zh, en, **values):
        self.message = (zh, en, values)
        self.render_records()
        self.resize_to_content()

    def copy_record(self, record):
        try:
            prompt = self.library.handoff_prompt(
                record["id"], inline=True, language=self.language.code
            )
            QApplication.clipboard().setText(prompt)
            self.show_message(
                "已复制接续提示词（{count:,} 字符），粘贴给另一个 Agent 即可继续。",
                "Copied the handoff prompt ({count:,} characters). Paste it into another agent to continue.",
                count=len(prompt),
            )
        except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
            self.show_message("复制失败：{error}", "Copy failed: {error}", error=str(exc))

    def export_record(self, record):
        self.hide()
        folder = QFileDialog.getExistingDirectory(
            self.owner, self.language.tr("选择导出位置", "Choose where to export")
        )
        if folder:
            try:
                options = {}
                if sys.platform == "darwin":
                    options["conversation"] = self.macos_export_conversation(record)
                destination = self.library.export(
                    record["id"], Path(folder), language=self.language.code, **options
                )
                self.message = (
                    "已导出到 {path}。在另一台电脑上点“导入”即可继续。",
                    "Exported to {path}. Choose Import on the other computer to continue.",
                    {"path": str(destination)},
                )
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                self.message = ("导出失败：{error}", "Export failed: {error}", {"error": str(exc)})
        self.owner.show_details()

    def macos_export_conversation(self, record):
        """Use the same conversation name as All records for Mac quick exports."""
        from .conversation_names import resolve
        from .conversations import conversation_key, group_conversations

        key = conversation_key(record)
        if key[0] == "unlinked":
            return None
        records = [row for row in self.library.list(limit=10000) if conversation_key(row) == key]
        conversations = group_conversations(
            records,
            names=resolve({(key[1], key[2])}) if key[0] == "session" else {},
            imported=self.library.conversation_titles(),
        )
        if not conversations:
            return None
        conversation = conversations[0]
        return (
            conversation["title"]
            or conversation["first_title"]
            or self.language.tr("未命名对话", "Untitled conversation")
        )

    def import_bundle(self):
        self.hide()
        folder = QFileDialog.getExistingDirectory(
            self.owner,
            self.language.tr(
                "选择上下文包（包含 metadata.json 的文件夹）",
                "Choose a context bundle (a folder with metadata.json)",
            ),
        )
        if folder:
            try:
                row = self.library.import_bundle(Path(folder))
                zh, en = (
                    (
                        "已导入“{title}”，可以复制提示词继续。",
                        "Imported “{title}”. Copy its prompt to continue.",
                    )
                    if row.get("imported")
                    else (
                        "这个上下文已经存在，没有重复导入。",
                        "This context already exists; it was not imported twice.",
                    )
                )
                self.message = (zh, en, {"title": row.get("title") or ""})
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                self.message = ("导入失败：{error}", "Import failed: {error}", {"error": str(exc)})
        self.owner.show_details()

    def open_record(self, record):
        self.owner.open_context_library(select_id=record["id"])

    def set_stage(self, stage):
        self.portrait.set_state(stage)
        self.stage.setText(
            f"Lv.{stage['level']}"
            if stage.get("length_known")
            else self.language.tr("长度待定", "Length pending")
        )
        self.stage.setToolTip(stage["hint"])
        self.progress.show()
        self.progress.setValue(round(stage["progress"] * 1000))
        self.progress.setToolTip(stage["hint"])
        self.progress.setAccessibleName(stage["hint"])

    def show_error(self):
        tr = self.language.tr
        self.failed = True
        self.stage.clear()
        self.stage.setToolTip("")
        self.progress.hide()
        self.progress.setToolTip("")
        self.progress.setAccessibleName(tr("本次长度暂不可读", "Current input length unavailable"))
        for key, button in self.buttons.items():
            button.setChecked(key == self.owner.period)
        self.total.setText(tr("暂不可读", "Unavailable"))
        self.total.setStyleSheet("font-size: 18px; font-weight: 600; color: #866239;")
        if is_macos():
            text_style(self.total, 18, "#866239", True)
        self.money.setText("—")
        self.basis.setText(tr("统计读取失败，正在自动重试", "Could not read statistics · Retrying"))
        self.stats.setText("")
        self.resize_to_content()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = tokens(self) if is_macos() else None
        painter.setPen(QColor(colors["border"] if colors else "#E8E2D8"))
        painter.setBrush(QColor(colors["background"] if colors else "#FFFCF7"))
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
        if not is_macos():
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
        if is_macos():
            self.card.setObjectName("card")
            self.card.setStyleSheet("")
            text_style(self.latest, 10, "#74685D")
            self.close_button.setStyleSheet("padding: 0; border-radius: 6px;")
            install_macos_style(self, variant="pet")
        else:
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

    def open_context_library(self, checked=False, select_id=None):
        from .context_library_qt import ContextLibraryDialog

        self.details.hide()
        self.session_notice.hide()
        if self.context_dialog is None:
            self.context_dialog = ContextLibraryDialog(
                self.store.path, self, sessions=self.session_store
            )
            self.context_dialog.changed.connect(self.refresh_session_state)
            if select_id:
                self.context_dialog.refresh(select_id=select_id)
        else:
            self.context_dialog.refresh(select_id=select_id)
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
            status = request_activity_text(active or latest, self.language)
            self.details.request_status.setText(status)
            detail = status
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
                    detail += tr("。", ".")
                else:
                    detail += tr(
                        "\n模型实测用量尚未返回。", "\nProvider usage has not been returned yet."
                    )
            # The footer shows one line; hovering it shows the request's numbers.
            self.details.request_status.setToolTip(detail)
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
        growth = growth_state(summary, self.language)
        if self.latest_prepared_report is not None and self.latest_prepared_at > (
            summary.get("last_preparation") or {}
        ).get("recorded_at", ""):
            growth = growth_state({"last_preparation": self.latest_prepared_report}, self.language)
        hint = growth_hint(growth, self.language)
        self.idle_stage = growth
        self.oasis_action.setVisible(growth["level"] == 4 or self.test_mode)
        self.number.setStyleSheet("font-size: 20px; font-weight: 600; color: #443B35;")
        if is_macos():
            self.number.setStyleSheet("font-size: 20px; font-weight: 600;")
        self.number.setText("—")
        self.caption.setText(tr("上下文压缩", "Context compression"))
        last = summary.get("last_preparation")
        latest = tr("等待本次上下文", "Waiting for context")
        long_latest = tr("等待 TOMC 准备上下文。", "Waiting for TOMC to prepare context.")
        if last and last["usable"]:
            delta = last["reduced_tokens"]
            latest = (
                tr("本次增加 {count:,} tokens", "Latest: {count:,} tokens added", count=abs(delta))
                if delta < 0
                else tr(
                    "本次节省 {count:,} tokens", "Latest: {count:,} tokens saved", count=abs(delta)
                )
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
                "{name} · {hint}\n点击展开统计。",
                "{name} · {hint}\nClick for statistics.",
                name=growth["name"],
                hint=hint,
            )
        )
        self.details.set_summary(summary, growth)
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
        self.number.setStyleSheet("font-size: 18px; font-weight: 600; color: #443B35;")
        if is_macos():
            self.number.setStyleSheet("font-size: 18px; font-weight: 600;")
        context = report.get("context_input_tokens")
        if type(context) is not int or context < 0:
            # A whole-request (envelope) count is not the compressed context length.
            envelope = any(
                marker in str(report.get("counter", "")).lower()
                for marker in ("request-json", "entire-payload")
            )
            context = None if envelope else report.get("input_tokens")
        if report.get("stage_only"):
            stage = growth_state({"last_preparation": report}, self.language)
            self.caption.setText(tr("上下文已压缩", "Context compressed"))
            self.number.setText(tr("第 {level} 阶段", "Stage {level}/4", level=stage["level"]))
            self.latest.setText(
                tr(
                    "压缩上下文 {count:,} tokens",
                    "Compressed {count:,} tokens",
                    count=stage["input_tokens"],
                )
            )
            return
        if report["usable"]:
            delta = report["reduced_tokens"]
            self.caption.setText(
                (tr("演示 · ", "Demo · ") if self.test_mode else "")
                + (tr("本次增加", "Added") if delta < 0 else tr("本次节省", "Saved"))
            )
            self.number.setText(tr("{count:,} tokens", "{count:,} tokens", count=abs(delta)))
            if context is None:
                self.latest.setText(tr("上下文已压缩", "Context compressed"))
            elif delta < 0:
                self.latest.setText(
                    tr("上下文 {count:,} tokens", "Context {count:,} tokens", count=context)
                )
            else:
                self.latest.setText(
                    tr("压缩上下文 {count:,} tokens", "Compressed {count:,} tokens", count=context)
                )
            return
        self.caption.setText(tr("本次准备", "Latest preparation"))
        self.number.setText(tr("无可用输出", "No usable output"))
        self.number.setStyleSheet("font-size: 16px; font-weight: 600; color: #443B35;")
        if is_macos():
            self.number.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.latest.setText(tr("本次未压缩", "Not compressed"))

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
        if is_macos() and visible:
            height = max(118, pet_height)
            pet_x, pet_y = 235, (height - pet_height) // 2
        self.setFixedSize(pet_x + pet_width, height)
        self.art.setGeometry(pet_x, pet_y, pet_width, pet_height)
        self.card.setGeometry(8, 8, 170, 94)
        self.caption.setGeometry(13, 8, 144, 17)
        self.number.setGeometry(13, 26, 144, 30)
        self.progress.setGeometry(23, 65, 140, 3)
        self.latest.setGeometry(12, 81, 166, 20)
        if is_macos():
            self.card.setGeometry(8, 8, 220, 104)
            self.caption.setGeometry(13, 9, 194, 20)
            self.number.setGeometry(13, 30, 194, 32)
            self.progress.setGeometry(23, 78, 190, 3)
            self.latest.setGeometry(12, 88, 212, 20)
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
        self.show_details()

    def show_details(self):
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
