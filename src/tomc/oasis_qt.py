"""A bounded, dismissible crown celebration; no claims about physical water saved."""

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .impact_story import captions


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class OasisCelebration(QWidget):
    DURATION = 10500

    def __init__(self, owner):
        super().__init__(
            owner,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.owner = owner
        self.language = getattr(owner, "language", None)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(420, 260)
        self.phase = 0.0
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.advance)
        if self.language is not None:
            self.language.changed.connect(self.retranslate)
        self.retranslate()

    def tr_text(self, zh, en):
        return en if getattr(self.language, "code", self.language) == "en" else zh

    def retranslate(self, *_):
        self.setWindowTitle(self.tr_text("TOMC · 绿洲诞生", "TOMC · An oasis grows"))
        self.setAccessibleName(
            self.tr_text(
                "减少重复输入，若实际计算需求下降，有机会减少用电和冷却用水。绿洲象征把资源留给自然；未实测节水或植树。点击关闭。完整故事见右键菜单。",
                "Reducing repeated input may lower electricity and cooling water demand if actual computation falls. "
                "The oasis symbolizes resources left for nature; water savings and tree planting are not measured. "
                "Click to close. The full story is in the cat's context menu.",
            )
        )
        self.setToolTip(
            self.tr_text(
                "点击收起 · 右键小猫可读完整故事",
                "Click to dismiss · Right-click the cat for the full story",
            )
        )
        self.update()

    def start(self):
        area = self.owner.screen().availableGeometry()
        self.resize(min(420, area.width()), min(260, area.height()))
        point = self.owner.pos()
        point.setX(
            max(area.left(), min(point.x() - self.width() + 72, area.right() - self.width() + 1))
        )
        point.setY(
            max(area.top(), min(point.y() - self.height() - 10, area.bottom() - self.height() + 1))
        )
        self.move(point)
        self.phase = 0.0
        self.clock.start()
        self.show()
        self.timer.start()

    def advance(self):
        self.phase = min(1.0, self.clock.elapsed() / self.DURATION)
        if self.phase >= 1:
            self.close()
        else:
            self.update()

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def mousePressEvent(self, event):
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(self.width() / 420, self.height() / 260)
        t = self.phase
        p.setOpacity(min(1.0, t / 0.06, (1 - t) / 0.09))
        border = QPainterPath()
        border.addRoundedRect(QRectF(1, 1, 418, 258), 22, 22)
        p.setClipPath(border)
        sky = QLinearGradient(0, 0, 0, 260)
        sky.setColorAt(0, QColor("#F9F0DE"))
        sky.setColorAt(1, QColor("#E9EBDD"))
        p.fillRect(QRectF(0, 0, 420, 260), sky)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ECD29E"))
        p.drawEllipse(QRectF(-80, 146, 380, 160))
        p.setBrush(QColor("#D8BA87"))
        p.drawEllipse(QRectF(190, 150, 330, 140))
        # A living front moves across the dry ground, revealing lake, trees and flowers.
        green = ease((t - 0.17) / 0.48)
        p.save()
        p.setClipRect(QRectF(0, 100, 450 * green, 180), Qt.ClipOperation.IntersectClip)
        p.setBrush(QColor("#B5CAA0"))
        p.drawEllipse(QRectF(-65, 149, 420, 160))
        p.setBrush(QColor("#8EAF88"))
        p.drawEllipse(QRectF(200, 158, 310, 140))
        p.setBrush(QColor("#9DC6C1"))
        p.drawEllipse(QRectF(136, 207, 170, 24))
        p.setPen(QPen(QColor("#D7E8D8"), 1.3))
        p.drawArc(QRectF(165, 211, 105, 10), 0, 160 * 16)
        p.restore()
        trees = (
            (36, 204, 50),
            (72, 192, 69),
            (110, 203, 48),
            (308, 195, 62),
            (350, 200, 80),
            (391, 216, 56),
            (14, 235, 35),
            (282, 222, 38),
        )
        for i, (x, y, h) in enumerate(trees):
            g = ease((t - 0.26 - i * 0.025) / 0.23)
            if g <= 0:
                continue
            p.save()
            p.translate(x, y)
            p.scale(0.75 + 0.25 * g, g)
            p.setPen(QPen(QColor("#82664C"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(0, 0), QPointF(0, -h + 9))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(("#5F8B68", "#7CA078", "#9AB283")[i % 3]))
            p.drawEllipse(QRectF(-20, -h, 40, 38))
            p.drawEllipse(QRectF(-15, -h - 13, 31, 35))
            p.setBrush(QColor("#C3D3A1"))
            p.drawEllipse(QRectF(-13, -h - 7, 12, 18))
            p.restore()
        bloom = ease((t - 0.48) / 0.22)
        for i in range(45):
            x, y = 12 + (i * 73) % 400, 206 + (i * 19) % 37
            p.setPen(QPen(QColor("#527950"), 1))
            p.drawLine(QPointF(x, y), QPointF(x + 2, y - 7 * bloom))
            if i % 2 == 0 and bloom > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(("#F6DB82", "#E8B6A6", "#FFF6DE")[i % 3]))
                for angle in range(0, 360, 72):
                    a = math.radians(angle)
                    p.drawEllipse(
                        QPointF(
                            x + 2 + math.cos(a) * 2 * bloom, y - 7 * bloom + math.sin(a) * 2 * bloom
                        ),
                        2 * bloom,
                        2 * bloom,
                    )
        # Small original rabbit silhouettes in the grass, followed by a flock of birds.
        for i in range(4):
            g = ease((t - 0.57 - i * 0.03) / 0.14)
            if not g:
                continue
            x, y = 74 + i * 81, 229 - abs(math.sin(t * 18 + i)) * 4 * g
            p.save()
            p.translate(x, y)
            p.scale(g, g)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FFF2D9") if i % 2 else QColor("#BC9572"))
            p.drawEllipse(QRectF(-6, -7, 12, 9))
            p.drawEllipse(QRectF(2, -12, 8, 8))
            p.drawEllipse(QRectF(3, -20, 3, 10))
            p.drawEllipse(QRectF(7, -20, 3, 10))
            p.setBrush(QColor("#574A39"))
            p.drawEllipse(QPointF(8, -9), 0.8, 0.8)
            p.restore()
        for i in range(9):
            g = max(0.0, min(1.0, (t - 0.56 - i * 0.014) / 0.3))
            if g <= 0:
                continue
            x = 195 + (i - 4) * 19 * g
            y = 145 - g * (55 + i % 3 * 16)
            wing = 3 + math.sin(t * 55 + i) * 2
            path = QPainterPath(QPointF(x - 5, y - wing))
            path.quadTo(x - 2, y - 2, x, y)
            path.quadTo(x + 2, y - 2, x + 5, y - wing)
            p.setPen(QPen(QColor("#5F796B"), 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        sprite = self.owner.art.sprites[3]
        half = sprite.width() / 2
        p.setOpacity(min(1.0, t / 0.06, (1 - t) / 0.09) * ease(t / 0.15))
        p.drawPixmap(QRectF(150, 94, 120, 120), sprite, QRectF(half, 0, half, sprite.height()))
        p.setPen(QColor("#3F5945"))
        p.setFont(QFont("Microsoft YaHei UI", 14, QFont.Weight.DemiBold))
        title, subtitle = captions(self.language)[min(3, int(t * 4))]
        p.drawText(QRectF(20, 20, 380, 27), Qt.AlignmentFlag.AlignCenter, title)
        p.setFont(QFont("Microsoft YaHei UI", 8))
        p.setPen(QColor("#756C59"))
        p.drawText(QRectF(16, 51, 388, 21), Qt.AlignmentFlag.AlignCenter, subtitle)
        p.setFont(QFont("Microsoft YaHei UI", 7))
        p.drawText(
            QRectF(20, 74, 380, 16),
            Qt.AlignmentFlag.AlignCenter,
            self.tr_text(
                "点击收起 · 右键小猫可读完整故事",
                "Click to dismiss · Right-click the cat for the full story",
            ),
        )
        p.setClipping(False)
        p.setPen(QPen(QColor("#D3D5BF"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, 418, 258), 22, 22)
