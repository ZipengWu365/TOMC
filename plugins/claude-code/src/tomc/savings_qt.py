"""Shared savings-dashboard pieces for the companion popover and the context library."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QToolTip, QWidget

from .ui_language import ui_font


def compact_tokens(value):
    """12,345 → 12.3K and 1,234,567 → 1.23M; small counts keep every digit."""
    sign, value = ("−" if value < 0 else ""), abs(value)
    if value < 10_000:
        return f"{sign}{value:,}"
    if value < 1_000_000:
        return f"{sign}{value / 1000:.1f}K".replace(".0K", "K")
    for limit, unit in ((1e9, "M"), (1e12, "B")):
        if value < limit:
            return f"{sign}{value / (limit / 1000):.2f}{unit}"
    return f"{sign}{value / 1e12:.2f}T"


def total_tokens(value):
    """Headline count: every digit below ten million, compact above."""
    if abs(value) >= 10_000_000:
        return compact_tokens(value)
    return ("−" if value < 0 else "") + f"{abs(value):,}"


def money_text(value):
    """Dollars with cents; amounts under a cent read as <$0.01."""
    if value is None:
        return "—"
    sign, value = ("−" if value < 0 else ""), abs(value)
    if 0 < value < 0.005:
        return sign + "<$0.01"
    return f"{sign}${value:,.2f}"


def local_time(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value or "")[:16]


def rule():
    line = QFrame()
    line.setObjectName("rule")
    line.setFixedHeight(1)
    return line


def discard(widget):
    """Detach a replaced row now; deleteLater alone leaves it a child until the next loop."""
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


class ElidedLabel(QLabel):
    """One plain-text line that keeps its full text but paints an ellipsis when narrow."""

    def __init__(self, text="", size=10, color="#706659", bold=False):
        super().__init__(text)
        self.setFont(ui_font())
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setStyleSheet(
            f"color: {color}; font-size: {size}px; font-weight: {600 if bold else 400};"
        )
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(1)
        self.color = QColor(color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.color)
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(self.rect(), int(self.alignment() | Qt.AlignmentFlag.AlignVCenter), text)


class SavingsChart(QWidget):
    """Tokens saved per UTC day; days inside the selected period are drawn darker."""

    def __init__(self, language, parent=None):
        super().__init__(parent)
        self.language = language
        self.days, self.start = [], None
        self.setFixedHeight(42)
        self.setMouseTracking(True)

    def set_days(self, days, start):
        self.days, self.start = list(days), start
        total = sum(max(0, day["tokens_saved"]) for day in self.days)
        self.setAccessibleName(
            self.language.tr(
                "近 {count} 天每日节省 tokens，共 {total:,}",
                "Tokens saved per day over the last {count} days: {total:,} in total",
                count=len(self.days),
                total=total,
            )
        )
        self.update()

    def geometry_for(self, index):
        count = len(self.days)
        gap = 3
        width = (self.width() - gap * (count - 1)) / count
        return index * (width + gap), width

    def index_at(self, x):
        for index in range(len(self.days)):
            left, width = self.geometry_for(index)
            if left <= x <= left + width + 3:
                return index
        return None

    def paintEvent(self, event):
        if not self.days:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        floor = self.height() - 1
        peak = max([day["tokens_saved"] for day in self.days] + [1])
        for index, day in enumerate(self.days):
            left, width = self.geometry_for(index)
            value = max(0, day["tokens_saved"])
            current = self.start is None or day["day"] >= self.start
            if value:
                height = max(3.0, (floor - 2) * value / peak)
                painter.setBrush(QColor("#507461" if current else "#C9D6CB"))
                painter.drawRoundedRect(QRectF(left, floor - height, width, height), 2, 2)
            else:
                painter.setBrush(QColor("#E5DFD4"))
                painter.drawRect(QRectF(left, floor - 1, width, 1))

    def mouseMoveEvent(self, event):
        index = self.index_at(event.position().x()) if self.days else None
        if index is None:
            QToolTip.hideText()
            return
        day = self.days[index]
        QToolTip.showText(
            event.globalPosition().toPoint(),
            self.language.tr(
                "{day} · 节省 {count:,} tokens",
                "{day} · {count:,} tokens saved",
                day=day["day"][5:],
                count=day["tokens_saved"],
            ),
            self,
        )
