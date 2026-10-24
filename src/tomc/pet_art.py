"""Original plush cat head with four context-deposit choreographies."""

import math
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

INK = QColor("#6E4C35")
BODY = QColor("#C99562")
SHADE = QColor("#AE774E")
SAGE = QColor("#8DAD97")
NOTES = ("#F2D77B", "#B9D5B2", "#EDCDB9")
DURATIONS = (2400, 3400, 2800, 3200)
FORGE_HITS = (0.28, 0.38, 0.48)
IDLE_WIDTH = 72
ACTIVE_WIDTH = 132


def size_envelope(phase):
    """Grow before food arrives; swallow and return fully to compact size."""
    if phase is None:
        return IDLE_WIDTH / ACTIVE_WIDTH
    t = min(1.0, phase / 0.18) if phase < 0.76 else max(0.0, (1 - phase) / 0.24)
    ease = t * t * (3 - 2 * t)
    return IDLE_WIDTH / ACTIVE_WIDTH + (1 - IDLE_WIDTH / ACTIVE_WIDTH) * ease


def smoothstep(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def forge_pose(phase):
    staging = smoothstep(phase / 0.16) * (1 - smoothstep((phase - 0.76) / 0.24))
    impact = max(max(0, 1 - abs(phase - hit) / 0.038) ** 2 for hit in FORGE_HITS)
    compact = sum(smoothstep((phase - hit + 0.012) / 0.045) for hit in FORGE_HITS) / 3
    return staging, impact, compact


def paper(p, x, y, index, size=1, rotation=0, context=False):
    p.save()
    p.translate(x, y)
    p.rotate(rotation)
    p.scale(size, size)
    p.setPen(Qt.PenStyle.NoPen)
    # The bottom lifts from the fabric: soft offset shadow, adhesive band, curled corner.
    p.setBrush(QColor(55, 36, 24, 28))
    p.drawRoundedRect(QRectF(-5, -4, 15, 16), 2, 2)
    p.setBrush(QColor(55, 36, 24, 20))
    p.drawRoundedRect(QRectF(-4, -3, 15, 16), 2, 2)
    color = QColor(NOTES[index % len(NOTES)])
    wash = QLinearGradient(0, -8, 3, 9)
    wash.setColorAt(0, color.lighter(110))
    wash.setColorAt(1, color)
    page = QPainterPath(QPointF(-7, -8))
    page.lineTo(7, -8)
    page.lineTo(7, 4)
    page.quadTo(4, 9, -7, 8)
    page.closeSubpath()
    p.setBrush(wash)
    p.setPen(QPen(color.darker(118), 0.45))
    p.drawPath(page)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(115, 91, 42, 21))
    p.drawRect(QRectF(-6.7, -7.8, 13.4, 2.5))
    curl = QPainterPath(QPointF(7, 4))
    curl.quadTo(6, 8, 2, 8.4)
    curl.quadTo(4.6, 6.8, 3.9, 4.4)
    curl.closeSubpath()
    p.setBrush(color.lighter(133))
    p.setPen(QPen(color.darker(116), 0.45))
    p.drawPath(curl)
    p.setPen(QPen(QColor("#8D846A"), 0.65, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(-4, -2), QPointF(3, -2.4))
    p.drawLine(QPointF(-4, 1), QPointF(1 if context else 3, 0.7))
    p.restore()


class PetArt(QWidget):
    collected = Signal()
    collecting = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level, self.notes = 1, 2
        self.sprites = [
            QPixmap(str(Path(__file__).parent / "data" / f"tomc-expression-{i}.png"))
            for i in range(1, 5)
        ]
        if any(
            sprite.isNull() or sprite.width() < sprite.height() * 1.8 for sprite in self.sprites
        ):
            raise FileNotFoundError("Missing TOMC two-expression head strip")
        self.sprite = self.sprites[0]
        self.compact_idle = False
        self.phase = None
        self.clock = QElapsedTimer()
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(16)
        self.animation_timer.timeout.connect(self.advance)

    def set_state(self, state):
        self.level, self.notes = state["level"], state["notes"]
        self.sprite = self.sprites[self.level - 1]
        self.update()

    def collect(self):
        self.clock.start()
        self.phase = 0.0
        self.collecting.emit()
        self.animation_timer.start()
        self.update()

    def advance(self):
        self.phase = min(1, self.clock.elapsed() / DURATIONS[self.level - 1])
        if self.phase >= 1:
            self.animation_timer.stop()
            self.phase = None
            self.collected.emit()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(self.width() / 140, self.height() / 156)
        active = self.phase is not None
        motion = math.sin((self.phase or 0) * math.pi * 2) if active else 0
        scale = 1 if self.compact_idle and not active else size_envelope(self.phase)
        p.save()
        if active and self.level == 2:
            staging, impact, _ = forge_pose(self.phase)
            p.translate(70 - 26 * staging + 16 * impact, 90 + 22 * staging - 20 * impact)
            scale *= 1 - 0.30 * staging
            p.scale(scale * (1 + impact * 0.07), scale * (1 - impact * 0.06))
            p.rotate(impact * 12)
        else:
            p.translate(70, 90)
            p.scale(scale, scale)
        if active and self.level != 2:
            p.rotate(motion * (2.5 if self.level < 3 else 1.2))
            p.scale(1 + abs(motion) * 0.025, 1 - abs(motion) * 0.018)
        p.translate(-70, -90)
        # Left frame is listless and aggrieved; right frame smiles ONLY while working.
        frame_width = self.sprite.width() / 2
        frame = QRectF(frame_width if active else 0, 0, frame_width, self.sprite.height())
        p.drawPixmap(QRectF(0, 10, 140, 140), self.sprite, frame)
        p.restore()
        if active:
            if self.level == 2:
                self.forge_cards(p, self.phase)
            else:
                self.context_cards(p, self.phase, scale)

    def forge_cards(self, p, phase):
        """Three local headbutts transform loose source sheets into compiled cards."""
        _, impact, compact = forge_pose(phase)
        arrival = smoothstep(phase / 0.15)
        handoff = smoothstep((phase - 0.65) / 0.23)
        visibility = arrival * (1 - smoothstep((phase - 0.90) / 0.10))
        center_x, center_y = 101 + 8 * handoff, 46 - 9 * handoff
        scatter = ((-13, -17, -18), (12, -12, 16), (-10, 10, -10), (13, 16, 21), (0, 0, -4))
        p.save()
        p.setOpacity(visibility)
        for i, (dx, dy, tilt) in enumerate(scatter):
            # Repeated impacts align, pack and then reveal tidy structured lines.
            x = center_x + dx * (1 - compact) + (i - 2) * 1.35 * compact
            y = center_y + dy * (1 - compact) + (i - 2) * 1.45 * compact - (1 - arrival) * 12
            width, height = 31 - 10 * compact, 38 - 10 * compact
            p.save()
            p.translate(x + impact * (1 - compact) * 2, y + impact * 2)
            p.rotate(tilt * (1 - compact))
            shadow = QRectF(-width / 2 + 1.2, -height / 2 + 2, width, height)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(55, 42, 30, 25))
            p.drawRoundedRect(shadow, 2, 2)
            p.setPen(QPen(QColor("#BBA98D"), 0.65))
            p.setBrush(QColor("#FFF5D9") if compact < 0.65 else QColor("#F6FAF1"))
            p.drawRoundedRect(QRectF(-width / 2, -height / 2, width, height), 2, 2)
            p.setPen(QPen(QColor("#A6967D"), 0.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for row in range(4):
                yy = -height / 2 + 8 + row * 4.2
                indent = 0 if compact > 0.65 else (row % 2) * 2
                p.drawLine(
                    QPointF(-width / 2 + 4 + indent, yy),
                    QPointF(width / 2 - 4 - (row % 2) * (1 - compact) * 5, yy),
                )
            if compact > 0.66:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#709C86"))
                p.drawRoundedRect(QRectF(-width / 2 + 3, -height / 2 + 3, width - 6, 2.5), 1, 1)
            p.restore()
        # Tiny contact strokes stay local; no screen shake, flashing, or permanent particles.
        if impact > 0.03:
            p.setOpacity(visibility * impact)
            p.setPen(QPen(QColor("#D0A452"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for angle in (-100, -65, -25):
                rad = math.radians(angle)
                p.drawLine(
                    QPointF(91 + math.cos(rad) * 6, 60 + math.sin(rad) * 6),
                    QPointF(91 + math.cos(rad) * 13, 60 + math.sin(rad) * 13),
                )
        if phase > 0.58:
            p.setOpacity(visibility * smoothstep((phase - 0.58) / 0.09))
            p.setPen(
                QPen(
                    QColor("#4F8569"),
                    1.7,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            check = QPainterPath(QPointF(center_x - 5, center_y - 23))
            check.lineTo(center_x - 1, center_y - 19)
            check.lineTo(center_x + 7, center_y - 27)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(check)
        p.restore()

    @property
    def expression(self):
        return "smiling" if self.phase is not None else "dejected"

    def mouth_position(self):
        return ((70, 111), (70, 111), (70, 111), (70, 114))[self.level - 1]

    def context_cards(self, p, phase, scale):
        count = (4, 7, 10, 15)[self.level - 1]
        mx, my = self.mouth_position()
        tx, ty = 70 + (mx - 70) * scale, 90 + (my - 90) * scale
        for i in range(count):
            delay = 0.18 + i * 0.009
            u = (phase - delay) / 0.44
            if not 0 < u < 1:
                continue
            if self.level == 1:
                sx = 22 + (i * 29) % 100
                x = sx * (1 - u) + tx * u + math.sin(u * 8 + i) * 5 * (1 - u)
                y = -8 + (ty + 8) * u * u
            elif self.level == 3:
                sx = -5 if i % 2 == 0 else 145
                x = sx * (1 - u) + tx * u
                y = (1 - u) ** 2 * (65 + (i % 3) * 12) + 2 * (1 - u) * u * (-30) + u * u * ty
            else:
                angle = i * 2.4 + u * math.pi * 2
                radius = (1 - u) * 65
                x = tx + math.cos(angle) * radius
                y = ty - (ty + 10) * (1 - u) + math.sin(angle) * radius * 0.45
            p.save()
            p.setOpacity(min(1, u * 8, (1 - u) * 7))
            paper(
                p,
                x,
                y,
                i,
                size=0.9 * (1 - 0.95 * u),
                rotation=(i % 3 - 1) * 18 * (1 - u),
                context=True,
            )
            p.restore()
