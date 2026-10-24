"""The savings analysis page and its anonymous GitHub feedback dialog."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .analysis import (
    MAX_COMMENT,
    MAX_CONVERSATIONS,
    analysis_report,
    feedback_filename,
    feedback_markdown,
    feedback_page,
    feedback_payload,
    feedback_url,
)
from .categories import CODES
from .categories import label as category_label
from .macos_ui import install_macos_style, is_macos, tokens
from .savings_qt import ElidedLabel, SavingsChart, compact_tokens, money_text

PALETTE = (
    "#507461",
    "#C08A4E",
    "#6B8CA6",
    "#A4687C",
    "#8A9A5B",
    "#7E6BA6",
    "#C2A04A",
    "#5E9C9A",
)
OTHER_COLOR = "#D8D2C6"
_MAC_LIGHT_CHART = (
    "#3876CA",
    "#B78037",
    "#399088",
    "#AD6684",
    "#738E3F",
    "#8471B5",
    "#A18B31",
    "#4D9585",
)
_MAC_DARK_CHART = (
    "#84B6FF",
    "#E5B778",
    "#8DD0C9",
    "#E5A4BD",
    "#BDD38C",
    "#BAADF0",
    "#EDD087",
    "#92C9B6",
)


def chart_color(widget, color):
    if not is_macos():
        return QColor(color)
    colors = tokens(widget)
    if color in PALETTE:
        palette = (
            _MAC_DARK_CHART if QColor(colors["background"]).lightness() < 128 else _MAC_LIGHT_CHART
        )
        return QColor(palette[PALETTE.index(color)])
    if color in (OTHER_COLOR, "#B9B0A2"):
        return QColor(colors["secondary"])
    return QColor(color)


class _LegendDot(QWidget):
    def __init__(self, color):
        super().__init__()
        self.color = color
        self.setFixedSize(12, 12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(chart_color(self, self.color))
        painter.drawEllipse(QRectF(2, 2, 8, 8))


class _WrappingCheckBox(QCheckBox):
    """Keep the checkbox's text and activation semantics while wrapping its label."""

    def _text_left(self):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        return (
            self.style()
            .subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
            .right()
            + 8
        )

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        text = self.fontMetrics().boundingRect(
            QRect(0, 0, max(1, width - self._text_left() - 4), 10000),
            Qt.TextFlag.TextWordWrap,
            self.text(),
        )
        return max(30, text.height() + 12)

    def sizeHint(self):
        return QSize(520, self.heightForWidth(520))

    def minimumSizeHint(self):
        return QSize(120, self.heightForWidth(520))

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_CheckBox, option)
        painter.setPen(QColor(tokens(self)["text" if self.isEnabled() else "muted"]))
        painter.drawText(
            self.rect().adjusted(self._text_left(), 0, -4, 0),
            Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )


def plain(text="", *, name=None, wrap=False):
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if name:
        item.setObjectName(name)
    return item


def notice():
    """The highlighted privacy promise, shown wherever feedback can be sent."""
    item = QLabel()
    item.setObjectName("privacy")
    item.setTextFormat(Qt.TextFormat.RichText)
    item.setWordWrap(True)
    return item


def card(title_label):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 14)
    layout.setSpacing(8)
    layout.addWidget(title_label)
    return frame, layout


class DonutChart(QWidget):
    """Shares as a ring around a total; hovering a part names it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts, self.center = [], ("", "")
        size = 168 if is_macos() else 150
        self.setFixedSize(size, size)
        self.setMouseTracking(True)

    def set_parts(self, parts, value, caption):
        self.parts = [(name, max(0, amount), color) for name, amount, color in parts]
        self.center = (value, caption)
        self.update()

    def ring(self):
        size = min(self.width(), self.height()) - 6
        thickness = size * 0.2
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        return rect.adjusted(
            thickness / 2, thickness / 2, -thickness / 2, -thickness / 2
        ), thickness

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        ring, thickness = self.ring()
        total = sum(amount for _, amount, _ in self.parts)
        colors = tokens(self) if is_macos() else None
        if total <= 0:
            painter.setPen(QPen(QColor(colors["border"] if colors else "#ECE6DB"), thickness))
            painter.drawEllipse(ring)
        else:
            start = 90 * 16
            for _name, amount, color in self.parts:
                span = -round(360 * 16 * amount / total)
                painter.setPen(
                    QPen(
                        chart_color(self, color),
                        thickness,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.FlatCap,
                    )
                )
                painter.drawArc(ring, start, span)
                start += span
        value, caption = self.center
        font = QFont(self.font())
        font.setPixelSize(20 if colors else 17)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(colors["text"] if colors else "#2F2A26"))
        middle = self.rect().center()
        painter.drawText(
            QRectF(0, middle.y() - 20, self.width(), 22), Qt.AlignmentFlag.AlignCenter, value
        )
        font.setPixelSize(12 if colors else 10)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(colors["muted"] if colors else "#8A7F72"))
        painter.drawText(
            QRectF(0, middle.y() + 3, self.width(), 16), Qt.AlignmentFlag.AlignCenter, caption
        )

    def part_at(self, point):
        ring, thickness = self.ring()
        center = ring.center()
        dx, dy = point.x() - center.x(), center.y() - point.y()
        radius = math.hypot(dx, dy)
        if abs(radius - ring.width() / 2) > thickness / 2:
            return None
        # Angle clockwise from twelve o'clock, matching the drawing order.
        angle = (90 - math.degrees(math.atan2(dy, dx))) % 360
        total = sum(amount for _, amount, _ in self.parts)
        position = 0.0
        for part in self.parts:
            position += 360 * part[1] / total if total else 0
            if angle <= position:
                return part
        return None

    def mouseMoveEvent(self, event):
        part = self.part_at(event.position())
        total = sum(amount for _, amount, _ in self.parts)
        if part and total:
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{part[0]} · {compact_tokens(part[1])} · {part[1] / total:.0%}",
                self,
            )
        else:
            QToolTip.hideText()


class BarList(QWidget):
    """Horizontal bars, each with a label and a value."""

    ROW = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.row_height = 38 if is_macos() else self.ROW
        if is_macos():
            self.setMouseTracking(True)

    def set_rows(self, rows):
        """rows: (label, amount, shown value, color)."""
        self.rows = list(rows)
        self.setFixedHeight(max(1, len(self.rows)) * self.row_height + 4)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        metrics = self.fontMetrics()
        names = max((metrics.horizontalAdvance(name) for name, *_ in self.rows), default=0)
        values = max((metrics.horizontalAdvance(text) for _, _, text, _ in self.rows), default=0)
        left = min(names + 10, int(self.width() * 0.42))
        right = values + 10
        peak = max((amount for _, amount, _, _ in self.rows), default=0) or 1
        colors = tokens(self) if is_macos() else None
        if colors:
            left = max(1, self.width() - right - 8)
        for index, (name, amount, text, color) in enumerate(self.rows):
            top = 2 + index * self.row_height
            painter.setPen(QColor(colors["text"] if colors else "#4E453D"))
            shown = metrics.elidedText(name, Qt.TextElideMode.ElideRight, left - 8)
            painter.drawText(
                QRectF(0, top, left - 6, self.ROW - 4), Qt.AlignmentFlag.AlignVCenter, shown
            )
            track = QRectF(left, top + 6, max(1, self.width() - left - right), self.ROW - 14)
            if colors:
                track = QRectF(0, top + 25, self.width(), 5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["border"] if colors else "#F0ECE4"))
            painter.drawRoundedRect(track, 4, 4)
            if amount > 0:
                filled = QRectF(
                    track.left(),
                    track.top(),
                    max(4.0, track.width() * amount / peak),
                    track.height(),
                )
                painter.setBrush(chart_color(self, color))
                painter.drawRoundedRect(filled, 4, 4)
            painter.setPen(QColor(colors["secondary"] if colors else "#6E655B"))
            painter.drawText(
                QRectF(self.width() - right + 4, top, right - 4, self.ROW - 4),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                text,
            )

    def mouseMoveEvent(self, event):
        if not is_macos():
            return super().mouseMoveEvent(event)
        index = int((event.position().y() - 2) // self.row_height)
        if 0 <= index < len(self.rows):
            name, _, text, _ = self.rows[index]
            QToolTip.showText(event.globalPosition().toPoint(), f"{name} · {text}", self)
        else:
            QToolTip.hideText()


class Legend(QWidget):
    """Colour key for a donut: name, amount and share on one line each."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(4)

    def set_parts(self, parts, total):
        while self.layout_.count():
            widget = self.layout_.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for name, amount, color in parts:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(6)
            if is_macos():
                dot = _LegendDot(color)
            else:
                dot = plain("●")
                dot.setStyleSheet(f"color: {color}; font-size: 12px;")
            title = ElidedLabel(name, 11, "#4E453D")
            share = plain(f"{compact_tokens(amount)} · {amount / total:.0%}" if total else "—")
            if is_macos():
                share.setObjectName("muted")
            else:
                share.setStyleSheet("color: #8A7F72; font-size: 11px;")
            line.addWidget(dot)
            line.addWidget(title, 1)
            line.addWidget(share)
            self.layout_.addWidget(row)
            row.show()
        self.layout_.addStretch()


def conversation_name(row, t):
    name = row["title"] or t("未命名对话", "Untitled conversation")
    return f"{name} · {t('子代理', 'subagent')}" if row.get("agent") else name


def donut_parts(rows, name, amount, limit=6, other="Other"):
    """The largest ``limit`` rows, then one grey remainder."""
    rows = [row for row in rows if amount(row) > 0]
    parts = [
        (name(row), amount(row), PALETTE[i % len(PALETTE)]) for i, row in enumerate(rows[:limit])
    ]
    rest = sum(amount(row) for row in rows[limit:])
    if rest > 0:
        parts.append((other, rest, OTHER_COLOR))
    return parts


class AnalysisPage(QWidget):
    """Which conversations and kinds of work saved the most, and how requests were handled."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.language = dialog.language
        self.report = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The page background matches the window; the cards stay white.
        scroll.viewport().setObjectName("analysisSurface")
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("analysisSurface")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(12)
        header = QHBoxLayout()
        self.summary = plain(name="muted", wrap=True)
        header.addWidget(self.summary, 1)
        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self.copy_report)
        header.addWidget(self.copy_button)
        self.feedback_button = QPushButton()
        self.feedback_button.setObjectName("primary")
        self.feedback_button.clicked.connect(self.open_feedback)
        header.addWidget(self.feedback_button)
        layout.addLayout(header)
        # Next to the button, so nobody has to wonder what leaves the computer.
        self.anonymity = notice()
        layout.addWidget(self.anonymity)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        self.titles = {
            key: plain(name="section")
            for key in (
                "conversations",
                "categories",
                "table",
                "coverage",
                "reductions",
                "stages",
                "daily",
            )
        }
        frame, box = card(self.titles["conversations"])
        row = QHBoxLayout()
        self.conversation_donut = DonutChart()
        self.conversation_legend = Legend()
        row.addWidget(self.conversation_donut)
        row.addWidget(self.conversation_legend, 1)
        box.addLayout(row)
        grid.addWidget(frame, 0, 0)
        frame, box = card(self.titles["categories"])
        row = QHBoxLayout()
        self.category_donut = DonutChart()
        self.category_legend = Legend()
        row.addWidget(self.category_donut)
        row.addWidget(self.category_legend, 1)
        box.addLayout(row)
        grid.addWidget(frame, 0, 1)
        layout.addLayout(grid)
        frame, box = card(self.titles["table"])
        self.table = QTableWidget(0, 6)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        if is_macos():
            self.table.setAlternatingRowColors(True)
            self.table.verticalHeader().setDefaultSectionSize(34)
            self.table.setWordWrap(False)
        else:
            self.table.setStyleSheet(
                "QTableWidget { background: #FFFFFF; border: none; }"
                "QHeaderView::section { background: #F6F2EA; border: none; padding: 6px; color: #6E655B; }"
            )
        box.addWidget(self.table)
        self.table_note = plain(name="muted", wrap=True)
        box.addWidget(self.table_note)
        layout.addWidget(frame)
        bars = QHBoxLayout()
        bars.setSpacing(12)
        self.coverage_bars, self.reduction_bars, self.stage_bars = BarList(), BarList(), BarList()
        self.notes = {}
        for key, widget in (
            ("coverage", self.coverage_bars),
            ("reductions", self.reduction_bars),
            ("stages", self.stage_bars),
        ):
            frame, box = card(self.titles[key])
            box.addWidget(widget)
            self.notes[key] = plain(name="muted", wrap=True)
            box.addWidget(self.notes[key])
            box.addStretch()
            bars.addWidget(frame, 1)
        layout.addLayout(bars)
        frame, box = card(self.titles["daily"])
        self.daily = SavingsChart(self.language, self)
        self.daily.setFixedHeight(70)
        box.addWidget(self.daily)
        layout.addWidget(frame)
        self.privacy = plain(name="muted", wrap=True)
        layout.addWidget(self.privacy)
        layout.addStretch()
        self.retranslate()

    def t(self, zh, en, **values):
        return self.language.tr(zh, en, **values)

    def retranslate(self, *_):
        t = self.t
        self.copy_button.setText(t("复制匿名报告", "Copy anonymous report"))
        self.feedback_button.setText(t("匿名提交反馈 ›", "Send anonymous feedback ›"))
        self.feedback_button.setToolTip(
            t(
                "先看完整的匿名报告，确认后才在 GitHub 上提交",
                "See the complete anonymous report first; it is submitted on GitHub only after you confirm",
            )
        )
        self.anonymity.setText(
            t(
                "<b>反馈是匿名的</b>：只提交工作类型（如编程、写作、论文）和数字，"
                "不含对话名称、对话内容、文件夹或任何 ID。提交前会先给你看完整内容。",
                "<b>Feedback is anonymous</b>: only kinds of work (such as coding, writing or papers) "
                "and numbers are sent, never conversation names, content, folders or IDs. "
                "You see the complete report before anything is sent.",
            )
        )
        for key, zh, en in (
            ("conversations", "各对话节省占比", "Savings by conversation"),
            ("categories", "工作类型", "Kinds of work"),
            ("table", "省得最多和最少的对话", "Conversations that saved the most and least"),
            ("coverage", "请求的处理情况", "How requests were handled"),
            ("reductions", "每次压缩减少的比例", "Reduction per compression"),
            ("stages", "上下文长度（小猫阶段）", "Context length (cat stages)"),
            ("daily", "每日节省 · 近 30 天", "Saved per day · last 30 days"),
        ):
            self.titles[key].setText(t(zh, en))
        self.table.setHorizontalHeaderLabels(
            [
                t("对话", "Conversation"),
                t("类型", "Kind"),
                t("压缩次数", "Compressions"),
                t("上下文", "Contexts"),
                t("节省 tokens", "Tokens saved"),
                t("金额", "Money"),
            ]
        )
        self.privacy.setText(
            t(
                "这份分析只在本机计算，不会自动上传任何内容。",
                "This analysis is computed on this computer; nothing is uploaded automatically.",
            )
        )
        if self.report is not None:
            self.render()

    def refresh(self):
        """Recompute for the window's selected period (today, 7 days or all time)."""
        dialog = self.dialog
        try:
            self.report = analysis_report(dialog.path, dialog.period, reference=dialog.pricing)
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.report = None
            self.summary.setText(
                self.t(
                    "分析暂不可读：{error}", "The analysis cannot be read: {error}", error=str(exc)
                )
            )
            return
        self.render()

    def conversation_name(self, row):
        return conversation_name(row, self.t)

    def render(self):
        t, report = self.t, self.report
        totals = report["totals"]
        share = totals["compressed_share"]
        period = {
            "today": ("今天", "Today"),
            "7d": ("近七天", "Last 7 days"),
            "all": ("累计", "All time"),
        }[report["period"]]
        self.summary.setText(
            t(*period)
            + (
                t(
                    " · {total} 个请求中压缩了 {share:.0%}",
                    " · {share:.0%} of {total} requests compressed",
                    share=share,
                    total=f"{totals['requests']:,}",
                )
                if share is not None
                else ""
            )
        )
        rows = report["conversations"]
        other = t("其他", "Other")
        parts = donut_parts(
            rows, self.conversation_name, lambda row: row["tokens_saved"], other=other
        )
        total = sum(amount for _, amount, _ in parts)
        self.conversation_donut.set_parts(
            parts, compact_tokens(total), t("节省 tokens", "tokens saved")
        )
        self.conversation_legend.set_parts(parts, total)
        kinds = donut_parts(
            report["categories"],
            lambda row: category_label(row["category"], self.language),
            lambda row: row["tokens_saved"],
            limit=7,
            other=other,
        )
        total = sum(amount for _, amount, _ in kinds)
        self.category_donut.set_parts(
            kinds, f"{len(report['categories'])}", t("种工作", "kinds of work")
        )
        self.category_legend.set_parts(kinds, total)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = (
                self.conversation_name(row),
                category_label(row["category"], self.language),
                f"{row['compressions']:,}",
                f"{row['contexts']:,}",
                f"{row['tokens_saved']:,}",
                money_text(row["money"]),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if column == 0:
                    item.setToolTip(" · ".join(part for part in (value, row.get("folder")) if part))
                self.table.setItem(index, column, item)
        # The header's own geometry is not settled before the page is first shown.
        self.table.setFixedHeight(
            self.table.horizontalHeader().sizeHint().height()
            + sum(self.table.rowHeight(i) for i in range(min(len(rows), 8)))
            + 6
        )
        self.table.setVisible(bool(rows))
        unattributed = totals["unattributed_tokens"]
        if not rows:
            self.table_note.setText(
                t("这段时间还没有压缩过的对话。", "No conversation was compressed in this period.")
            )
        elif unattributed > 0:
            self.table_note.setText(
                t(
                    "按节省 tokens 从多到少排列。另有 {tokens} tokens 来自没有对话身份的准备（例如笔记本调用）。",
                    "Sorted by tokens saved. Another {tokens} tokens came from preparations without a conversation (such as notebook recalls).",
                    tokens=f"{unattributed:,}",
                )
            )
        else:
            self.table_note.setText(t("按节省 tokens 从多到少排列。", "Sorted by tokens saved."))
        names = {
            "compressed": ("已压缩", "Compressed"),
            "host_managed": ("宿主自己管理上下文", "Managed by the host"),
            "short": ("历史太短", "History too short"),
            "unsupported": ("内容格式暂不支持", "Content not yet supported"),
            "auxiliary": ("宿主辅助请求", "Host auxiliary requests"),
            "switched_off": ("TOMC 已关闭", "TOMC switched off"),
            "failed": ("取消或失败", "Cancelled or failed"),
        }
        coverage = report["coverage"]
        observed = sum(row["requests"] for row in coverage) or 1
        self.coverage_bars.set_rows(
            (
                t(*names[row["group"]]),
                row["requests"],
                f"{row['requests']:,} · {row['requests'] / observed:.0%}",
                "#507461" if row["group"] == "compressed" else "#B9B0A2",
            )
            for row in coverage
            if row["requests"]
        )
        self.notes["coverage"].setText(
            t(
                "所有经过 TOMC 的请求；没被压缩的会原样发给模型。",
                "Every request routed through TOMC; uncompressed ones reach the model unchanged.",
            )
        )
        self.reduction_bars.set_rows(
            (row["bucket"].replace(">=", "≥"), row["requests"], f"{row['requests']:,}", "#6B8CA6")
            for row in report["reductions"]
        )
        self.notes["reductions"].setText(
            t("整个请求因压缩变小的比例。", "How much smaller each whole request became.")
        )
        thresholds = ("< 10K", "10K–100K", "100K–1M", "≥ 1M")
        self.stage_bars.set_rows(
            (
                t(
                    "第 {n} 阶段 {range}",
                    "Stage {n} {range}",
                    n=row["stage"],
                    range=thresholds[row["stage"] - 1],
                ),
                row["compilations"],
                f"{row['compilations']:,}",
                "#C08A4E",
            )
            for row in report["stages"]
        )
        self.notes["stages"].setText(
            t(
                "每次压缩的历史长度，对应小猫的四个阶段。",
                "The history length of each compression, matching the cat's four stages.",
            )
        )
        self.daily.set_days(report["daily"], None)
        for widget in (self.feedback_button, self.copy_button):
            widget.setEnabled(bool(rows) or totals["compressions"] > 0)

    def copy_report(self):
        if self.report is None:
            return
        QApplication.clipboard().setText(feedback_markdown(feedback_payload(self.report)))
        self.dialog.show_message(
            "已复制匿名报告：只有工作类型和数字，不含对话名称或内容。",
            "Copied the anonymous report: kinds of work and numbers only, no conversation names or content.",
        )

    def open_feedback(self):
        if self.report is None:
            return
        FeedbackDialog(self.report, self.dialog).exec()


class FeedbackDialog(QDialog):
    """Review the anonymous report, correct the kinds of work, then submit it on GitHub."""

    def __init__(self, report, parent):
        super().__init__(parent)
        self.report = report
        self.language = parent.language
        self.message = parent.show_message
        self.overrides, self.status_spec = {}, None
        self.filename = feedback_filename(report["generated_utc"][:10])
        self._mac = is_macos()
        if self._mac:
            self.resize(900, 820)
            self.setMinimumSize(720, 560)
        else:
            self.setStyleSheet(parent.styleSheet())
            self.resize(820, 720)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 18, 22, 16)
        outer.setSpacing(10)
        self.heading = plain(name="title")
        outer.addWidget(self.heading)
        if self._mac:
            self.heading.setWordWrap(True)
            self.content_scroll = QScrollArea()
            self.content_scroll.setWidgetResizable(True)
            self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget()
            layout = QVBoxLayout(body)
            layout.setContentsMargins(0, 0, 8, 0)
            layout.setSpacing(12)
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            self.content_scroll.setWidget(body)
            outer.addWidget(self.content_scroll, 1)
        else:
            layout = outer
        self.anonymity = notice()
        layout.addWidget(self.anonymity)
        self.explanation = plain(name="muted", wrap=True)
        layout.addWidget(self.explanation)
        self.table = QTableWidget(0, 3)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if self._mac:
            self.table.setWordWrap(False)
            self.table.setAlternatingRowColors(True)
            self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.table)
        self.comment_title = plain(name="section")
        layout.addWidget(self.comment_title)
        self.comment = QPlainTextEdit()
        if self._mac:
            self.comment.setMinimumHeight(90)
            self.comment.setMaximumHeight(120)
        else:
            self.comment.setMaximumHeight(80)
        self.comment.textChanged.connect(self.update_preview)
        layout.addWidget(self.comment)
        self.preview_title = plain(name="section")
        layout.addWidget(self.preview_title)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        if self._mac:
            self.preview.setMinimumHeight(180)
        layout.addWidget(self.preview, 1)
        self.confirm = _WrappingCheckBox() if self._mac else QCheckBox()
        if self._mac:
            self.confirm.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.confirm.toggled.connect(self.update_buttons)
        outer.addWidget(self.confirm)
        actions = QHBoxLayout()
        self.status = plain(name="muted", wrap=True)
        if self._mac:
            outer.addWidget(self.status)
            self.status.hide()
        else:
            actions.addWidget(self.status, 1)
        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self.copy)
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.save)
        self.submit_button = QPushButton()
        self.submit_button.setObjectName("primary")
        self.submit_button.clicked.connect(self.submit)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.reject)
        for button in (self.copy_button, self.save_button, self.submit_button, self.close_button):
            actions.addWidget(button)
            if self._mac and button is self.save_button:
                actions.addStretch()
        outer.addLayout(actions)
        install_macos_style(self)
        self.populate()
        self.retranslate()
        self.language.changed.connect(self.retranslate)

    def t(self, zh, en, **values):
        return self.language.tr(zh, en, **values)

    def set_status(self, zh, en, **values):
        self.status_spec = (zh, en, values)
        self.status.setText(self.t(zh, en, **values))
        if self._mac:
            self.status.setVisible(bool(self.status.text()))

    def populate(self):
        rows = self.rows = self.report["conversations"][:MAX_CONVERSATIONS]
        self.table.setRowCount(len(rows))
        self.combos = []
        for index, row in enumerate(rows):
            item = QTableWidgetItem(conversation_name(row, self.t))
            item.setToolTip(
                self.t("只在本机显示，不会提交", "Shown on this computer only; never submitted")
            )
            self.table.setItem(index, 0, item)
            combo = QComboBox()
            if self._mac:
                combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
                combo.setMinimumHeight(34)
            for code in CODES:
                combo.addItem(category_label(code, self.language), code)
            combo.setCurrentIndex(CODES.index(row["category"]))
            combo.currentIndexChanged.connect(
                lambda _index, key=row["key"], box=combo: self.change_category(key, box)
            )
            self.table.setCellWidget(index, 1, combo)
            self.table.setItem(index, 2, QTableWidgetItem(""))
            self.combos.append(combo)
        self.table.setFixedHeight(
            min(
                260 if self._mac else 220,
                self.table.horizontalHeader().sizeHint().height()
                + sum(self.table.rowHeight(i) for i in range(len(rows)))
                + 4,
            )
        )

    def change_category(self, key, box):
        self.overrides[key] = box.currentData()
        self.update_preview()

    def payload(self):
        return feedback_payload(
            self.report, categories=self.overrides, comment=self.comment.toPlainText()
        )

    def update_preview(self):
        if len(self.comment.toPlainText()) > MAX_COMMENT:
            self.comment.setPlainText(self.comment.toPlainText()[:MAX_COMMENT])
            return
        payload = self.payload()
        self.markdown = feedback_markdown(payload)
        self.preview.setPlainText(self.markdown)
        for index, row in enumerate(payload["conversations"]):
            self.table.item(index, 2).setText(row["label"])

    def update_buttons(self):
        self.submit_button.setEnabled(self.confirm.isChecked())

    def retranslate(self, *_):
        t = self.t
        self.setWindowTitle(t("TOMC · 提交反馈", "TOMC · Send feedback"))
        self.heading.setText(t("提交匿名分析报告", "Send an anonymous analysis report"))
        self.anonymity.setText(
            t(
                "<b>已匿名：只提交工作类型和数字</b><br>"
                "会提交：每个对话的工作类型和编号（如 coding #1，即第 1 个编程开发对话）、"
                "压缩次数、节省的 tokens 等统计，以及你写的建议。<br>"
                "不会提交：对话名称、对话内容、文件夹、任务、会话或请求 ID。"
                "下表左列的对话名只在你的电脑上显示，方便你核对分类。",
                "<b>Anonymous: only kinds of work and numbers are sent</b><br>"
                "Sent: each conversation's kind of work and number (coding #1 is the first coding "
                "conversation), compressions, tokens saved and other counts, and any suggestion you write.<br>"
                "Never sent: conversation names, content, folders, tasks, session or request IDs. "
                "The names in the first column are shown on this computer only, to help you check the kinds.",
            )
        )
        self.explanation.setText(
            t(
                "分类不准可以在表格里改。点“在 GitHub 提交”会在浏览器打开 GitHub，把报告作为新文件提出，"
                "GitHub 替你建立 Pull Request；你在网页上确认后才会发出。报告和 Pull Request 是公开的，会显示你的 GitHub 账号。",
                "Fix any kind in the table. “Submit on GitHub” opens GitHub in your browser with the report as a new file, "
                "and GitHub opens a pull request for you; nothing is sent until you confirm there. "
                "The report and the pull request are public and show your GitHub account.",
            )
        )
        if self._mac:
            self.explanation.setText(
                t(
                    "先检查下方完整报告。自动报告将对话替换为工作类型和编号，只保留数字，不含对话名称、文件夹、任务、正文或 ID；分类可在表格中修改。"
                    "点击“在 GitHub 提交”会打开浏览器：较短报告会随链接发送给 GitHub，较长报告会先复制到剪贴板供你粘贴。"
                    "在网页确认后才会创建公开的报告和 Pull Request，并显示你的 GitHub 账号。",
                    "Review the complete report below. The generated report replaces conversations with a kind of work and a number, keeping counts without names, folders, tasks, content or IDs. You can correct categories in the table. "
                    "Clicking Submit on GitHub opens your browser: a shorter report is sent to GitHub in the link, while a longer report is copied for you to paste. "
                    "Confirming on the webpage creates the public report and pull request under your GitHub account.",
                )
            )
        self.table.setHorizontalHeaderLabels(
            [
                t("对话（只在本机显示）", "Conversation (shown here only)"),
                t("工作类型", "Kind of work"),
                t("报告中的标签", "Label in the report"),
            ]
        )
        for index, (row, combo) in enumerate(zip(self.rows, self.combos)):
            self.table.item(index, 0).setText(conversation_name(row, t))
            for position, code in enumerate(CODES):
                combo.setItemText(position, category_label(code, self.language))
        self.comment_title.setText(t("你的建议（可选）", "Your suggestion (optional)"))
        self.comment.setPlaceholderText(
            t(
                "比如：哪里好用、哪里不好用、希望增加什么。最多 {count} 字。",
                "For example what works, what doesn't, what you'd like next. Up to {count} characters.",
                count=MAX_COMMENT,
            )
        )
        self.preview_title.setText(t("将要提交的内容", "What will be submitted"))
        self.confirm.setText(
            t(
                "我已检查：报告里没有对话名称、文件夹、任务或正文。",
                "I checked: the report has no conversation names, folders, tasks or content.",
            )
        )
        self.copy_button.setText(t("复制", "Copy"))
        self.save_button.setText(t("保存为文件…", "Save as file…"))
        self.submit_button.setText(t("在 GitHub 提交 ›", "Submit on GitHub ›"))
        self.close_button.setText(t("关闭", "Close"))
        if self.status_spec:
            zh, en, values = self.status_spec
            self.status.setText(t(zh, en, **values))
        if self._mac:
            self.confirm.updateGeometry()
        self.update_preview()
        self.update_buttons()

    def copy(self):
        QApplication.clipboard().setText(self.markdown)
        self.set_status("已复制。", "Copied.")

    def save(self):
        target, _ = QFileDialog.getSaveFileName(
            self,
            self.t("保存匿名报告", "Save the anonymous report"),
            str(Path.home() / Path(self.filename).name),
            "Markdown (*.md)",
        )
        if not target:
            return
        try:
            Path(target).write_text(self.markdown, encoding="utf-8")
            self.set_status("已保存：{path}", "Saved: {path}", path=target)
        except OSError as exc:
            self.set_status("保存失败：{error}", "Save failed: {error}", error=str(exc))

    def submit(self):
        if not self.confirm.isChecked():
            return
        url = feedback_url(self.markdown, self.filename)
        if url is None:
            # Too long for a link: the report goes to the clipboard to paste on the page.
            QApplication.clipboard().setText(self.markdown)
            url = feedback_page(self.filename)
            self.set_status(
                "报告较长，已复制到剪贴板；请在打开的 GitHub 页面里粘贴，再提交。",
                "The report is long and was copied; paste it into the GitHub page that opens, then submit.",
            )
        else:
            if self._mac:
                self.set_status(
                    "已将预览报告随链接发送给 GitHub 并打开网页。检查内容后点“Propose new file”，再创建公开的 Pull Request。",
                    "The preview report was sent to GitHub in the link and its webpage is open. Check the content, choose “Propose new file”, then create the public pull request.",
                )
            else:
                self.set_status(
                    "已在浏览器打开 GitHub。确认内容后点“Propose new file”，再创建 Pull Request。",
                    "GitHub is open in your browser. Check the content, choose “Propose new file”, then create the pull request.",
                )
        QDesktopServices.openUrl(QUrl(url))
        if self._mac:
            self.message(
                "已打开 GitHub 反馈页面；在网页确认后创建公开的反馈 Pull Request。",
                "Opened the GitHub feedback page; confirm there to create the public feedback pull request.",
            )
        else:
            self.message(
                "已打开 GitHub 反馈页面；在网页确认后才会提交。",
                "Opened the GitHub feedback page; nothing is submitted until you confirm there.",
            )
