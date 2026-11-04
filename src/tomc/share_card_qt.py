"""Draw the share card with QPainter, and the small preview dialog that saves or copies it.

Rendering is local and offscreen; nothing is uploaded. The demo watermark and the
fixed honesty footer have no switch.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from .pet_growth import STAGES
from .share_card import card_data, card_text, default_filename

SIZES = {"portrait": QSize(1080, 1350), "landscape": QSize(1200, 630)}
INK = QColor("#345743")
INK_DEEP = QColor("#22392C")
CREAM = QColor("#F5EEDD")
CREAM_LIGHT = QColor("#FAF5EA")
PAPER = QColor("#FFFCF5")
MUTED = QColor("#77806F")
MONEY = QColor("#5F675F")
LINE = QColor("#E4DAC4")
BAR = QColor("#B7CBB9")
BAR_TODAY = INK
TAN = QColor("#C99562")
WATERMARK = QColor(178, 64, 44, 46)
TEXT_FAMILIES = [
    "PingFang SC",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Hiragino Sans GB",
    "sans-serif",
]
NUMBER_FAMILIES = ["Avenir Next", "Helvetica Neue", "Segoe UI", "Roboto"] + TEXT_FAMILIES
DATA = Path(__file__).parent / "data"


def _ensure_fonts():
    """Qt's offscreen backend on Windows does not discover system fonts by itself."""
    if QGuiApplication.platformName() == "offscreen" and sys.platform == "win32":
        for name in ("msyh.ttc", "segoeui.ttf"):
            QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts") / name))


def _font(size, weight=QFont.Weight.Normal, numbers=False):
    font = QFont()
    font.setFamilies(NUMBER_FAMILIES if numbers else TEXT_FAMILIES)
    font.setPixelSize(max(8, round(size)))
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


class _Pen:
    """A QPainter wrapper that records every string it draws."""

    def __init__(self, painter, drawn):
        self.p = painter
        self.drawn = drawn

    def fit(self, text, size, width, weight=QFont.Weight.Normal, numbers=False, smallest=10):
        font = _font(size, weight, numbers)
        while font.pixelSize() > smallest and QFontMetricsF(font).horizontalAdvance(text) > width:
            font.setPixelSize(font.pixelSize() - 1)
        return font

    def text(
        self, x, y, text, font, color, width=None, align=Qt.AlignmentFlag.AlignLeft, record=True
    ):
        """Draw one line with its top at y; returns the line height."""
        if not text:
            return 0
        metrics = QFontMetricsF(font)
        width = width if width is not None else metrics.horizontalAdvance(text) + 4
        self.p.setFont(font)
        self.p.setPen(color)
        rect = QRectF(x, y, width, metrics.height())
        self.p.drawText(rect, int(align | Qt.AlignmentFlag.AlignVCenter), text)
        if record:
            self.drawn.append(text)
        return metrics.height()

    def wrapped(self, x, y, width, text, font, color, align=Qt.AlignmentFlag.AlignLeft):
        if not text:
            return 0
        flags = int(align | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
        bound = QFontMetricsF(font).boundingRect(QRectF(x, y, width, 2000), flags, text)
        self.p.setFont(font)
        self.p.setPen(color)
        self.p.drawText(QRectF(x, y, width, bound.height() + 2), flags, text)
        self.drawn.append(text)
        return bound.height()


def _cat(stage):
    """The smiling right half of this stage's two-expression head strip."""
    image = QImage(str(DATA / STAGES[max(1, min(4, stage)) - 1][2]))
    if image.isNull():
        return None
    half = image.width() // 2
    return image.copy(half, 0, image.width() - half, image.height())


def _background(p, width, height):
    p.fillRect(QRectF(0, 0, width, height), CREAM)
    glow = QLinearGradient(0, 0, 0, height)
    glow.setColorAt(0, CREAM_LIGHT)
    glow.setColorAt(1, CREAM)
    p.fillRect(QRectF(0, 0, width, height), glow)
    # A quiet green rule along the top edge, the only ornament.
    p.fillRect(QRectF(0, 0, width, 10), INK)


def _panel(p, rect, radius=28):
    p.setPen(QPen(LINE, 2))
    p.setBrush(PAPER)
    p.drawRoundedRect(rect, radius, radius)


def _badge(pen, x, y, text, size):
    font = _font(size, QFont.Weight.DemiBold)
    metrics = QFontMetricsF(font)
    width, height = metrics.horizontalAdvance(text) + size * 1.1, metrics.height() + size * 0.35
    pen.p.setPen(QPen(INK, 2))
    pen.p.setBrush(Qt.BrushStyle.NoBrush)
    pen.p.drawRoundedRect(QRectF(x, y, width, height), height / 2, height / 2)
    pen.text(x, y + size * 0.17, text, font, INK, width, Qt.AlignmentFlag.AlignHCenter)
    return width


def _header(pen, x, y, data, text, scale, cat_size):
    cat = _cat(data["stage"])
    if cat is not None:
        pen.p.drawImage(QRectF(x - cat_size * 0.06, y, cat_size, cat_size), cat)
    left = x + cat_size * 1.0
    title = pen.fit(text["title"], 46 * scale, 1e4, QFont.Weight.Bold)
    pen.text(left, y + cat_size * 0.18, text["title"], title, INK_DEEP)
    pen.text(left, y + cat_size * 0.18 + 60 * scale, text["range"], _font(32 * scale), MUTED)


def _hero(pen, x, y, width, text, scale):
    """The main number, or the plain-words state; returns the bottom y."""
    if "number" in text:
        lead = _font(40 * scale, QFont.Weight.DemiBold)
        lead_top = y
        y += pen.text(x, y, text["lead"], lead, INK) + 2 * scale
        lead_end = x + QFontMetricsF(lead).horizontalAdvance(text["lead"])
        number = _font(164 * scale, QFont.Weight.Bold, numbers=True)
        unit = _font(52 * scale, QFont.Weight.DemiBold)
        n_metrics, u_metrics = QFontMetricsF(number), QFontMetricsF(unit)
        n_width = n_metrics.horizontalAdvance(text["number"])
        pen.text(x - 6 * scale, y, text["number"], number, INK)
        baseline = y + n_metrics.ascent()
        unit_top = baseline - u_metrics.ascent()
        pen.text(x + n_width + 18 * scale, unit_top, text["unit"], unit, INK)
        u_width = u_metrics.horizontalAdvance(text["unit"])
        badge_size = 24 * scale
        badge_font = _font(badge_size, QFont.Weight.DemiBold)
        badge_width = QFontMetricsF(badge_font).horizontalAdvance(text["badge"]) + badge_size * 1.1
        badge_x = x + n_width + u_width + 38 * scale
        if badge_x + badge_width <= x + width:
            _badge(pen, badge_x, unit_top + 8 * scale, text["badge"], badge_size)
        else:
            # No room after the unit: the badge follows the lead line instead.
            _badge(pen, lead_end + 14 * scale, lead_top + 6 * scale, text["badge"], badge_size)
        y += n_metrics.ascent() + n_metrics.descent() * 0.35 + 14 * scale
    else:
        head = pen.fit(text["head"], 104 * scale, width, QFont.Weight.Bold)
        y += pen.text(x, y + 10 * scale, text["head"], head, INK) + 20 * scale
    sub = pen.fit(text["sub"], 34 * scale, width)
    y += pen.wrapped(x, y, width, text["sub"], sub, MUTED)
    return y


def _money(pen, x, y, width, text, scale):
    if "money" not in text:
        return y
    y += pen.text(x, y, text["money"], pen.fit(text["money"], 40 * scale, width), MONEY)
    note = _font(23 * scale)
    y += 4 * scale + pen.wrapped(x, y + 4 * scale, width, text["money_note"], note, MUTED)
    if "money_unpriced" in text:
        y += pen.wrapped(x, y + 2 * scale, width, text["money_unpriced"], note, MUTED)
    return y


def _chart(pen, rect, data, text, scale):
    _panel(pen.p, rect, 28 * scale)
    pad = 34 * scale
    caption = pen.fit(text["chart"], 26 * scale, rect.width() - 2 * pad)
    pen.text(rect.left() + pad, rect.top() + pad * 0.8, text["chart"], caption, MUTED)
    days = data["daily"]
    values = [max(0, row["tokens_saved"]) for row in days]
    peak = max(values) if values else 0
    label_font = _font(24 * scale)
    label_h = QFontMetricsF(label_font).height()
    peak_h = QFontMetricsF(_font(26 * scale, QFont.Weight.DemiBold, numbers=True)).height()
    top = rect.top() + pad * 0.8 + QFontMetricsF(caption).height() + peak_h + 14 * scale
    bottom = rect.bottom() - pad * 0.6 - label_h - 10 * scale
    inner_left, inner_width = rect.left() + pad, rect.width() - 2 * pad
    slot = inner_width / len(days)
    bar_width = min(slot * 0.56, 84 * scale)
    pen.p.setPen(QPen(LINE, 2 * scale))
    pen.p.drawLine(QPointF(inner_left, bottom), QPointF(inner_left + inner_width, bottom))
    peak_index = values.index(peak) if peak > 0 else None
    if text["chart_empty"]:
        font = _font(28 * scale)
        pen.text(
            inner_left,
            (top + bottom) / 2 - QFontMetricsF(font).height() / 2,
            text["chart_empty"],
            font,
            MUTED,
            inner_width,
            Qt.AlignmentFlag.AlignHCenter,
        )
    for index, (row, value) in enumerate(zip(days, values)):
        center = inner_left + slot * (index + 0.5)
        height = (bottom - top) * (value / peak) if peak else 0
        height = max(height, 5 * scale)
        bar = QRectF(center - bar_width / 2, bottom - height, bar_width, height)
        path = QPainterPath()
        path.addRoundedRect(bar, min(12 * scale, bar_width / 2), min(12 * scale, bar_width / 2))
        pen.p.setPen(Qt.PenStyle.NoPen)
        pen.p.fillPath(path, BAR_TODAY if row["today"] else (BAR if value else LINE))
        bold = QFont.Weight.Bold if row["today"] else QFont.Weight.Normal
        pen.text(
            center - slot / 2,
            bottom + 10 * scale,
            text["days"][index],
            _font(24 * scale, bold),
            INK if row["today"] else MUTED,
            slot,
            Qt.AlignmentFlag.AlignHCenter,
        )
        if index == peak_index and text["peak"]:
            font = _font(26 * scale, QFont.Weight.DemiBold, numbers=True)
            pen.text(
                center - slot,
                bar.top() - QFontMetricsF(font).height() - 4 * scale,
                text["peak"],
                font,
                INK,
                slot * 2,
                Qt.AlignmentFlag.AlignHCenter,
            )


def _cells(pen, x, y, width, height, text, scale, gap):
    cell_width = (width - 2 * gap) / 3
    for index, (caption, value) in enumerate(text["cells"]):
        left = x + index * (cell_width + gap)
        _panel(pen.p, QRectF(left, y, cell_width, height), 22 * scale)
        pad = 22 * scale
        room = cell_width - 2 * pad
        top = y + pad * 0.9
        top += pen.text(left + pad, top, caption, pen.fit(caption, 23 * scale, room), MUTED)
        top += 6 * scale
        font = pen.fit(value, 32 * scale, room, QFont.Weight.Bold, smallest=round(15 * scale))
        if QFontMetricsF(font).horizontalAdvance(value) <= room:
            pen.text(left + pad, top, value, font, INK_DEEP)
        else:
            pen.wrapped(left + pad, top, room, value, font, INK_DEEP)


def _pack(items, font, width):
    """Join short notes with " · " into as few lines as fit; a long note gets its own line."""
    metrics, lines = QFontMetricsF(font), []
    for item in items:
        if lines and metrics.horizontalAdvance(" · ".join(lines[-1] + [item])) <= width:
            lines[-1].append(item)
        else:
            lines.append([item])
    return lines


def _footer_lines(text, width, scale):
    small = _font(21 * scale)
    strong = _font(21 * scale, QFont.Weight.DemiBold)
    rows = [(strong, INK, [line]) for line in text["sources"]]
    rows += [(small, MUTED, items) for items in _pack(text["fixed"], small, width)]
    rows.append((small, MUTED, [text["footer"]]))
    return rows


def _footer_height(text, width, scale):
    rows = _footer_lines(text, width, scale)
    return (len(rows) + 1) * QFontMetricsF(_font(21 * scale)).height() * 1.12


def _footer(pen, x, y, width, text, scale):
    small = _font(21 * scale)
    step = QFontMetricsF(small).height() * 1.12
    for font, color, items in _footer_lines(text, width, scale):
        line = " · ".join(items)
        pen.text(x, y, line, pen.fit(line, font.pixelSize(), width), color, width, record=False)
        pen.drawn.extend(items)
        y += step
    repo = _font(21 * scale, QFont.Weight.DemiBold)
    pen.text(x, y, text["repo"], repo, INK, width)
    pen.text(x, y, text["made"], small, MUTED, width, Qt.AlignmentFlag.AlignRight)
    return y + step


def _watermark(pen, width, height, words):
    """Diagonal and repeated across the whole card; drawn last so nothing covers it."""
    p = pen.p
    p.save()
    p.translate(width / 2, height / 2)
    p.rotate(-28)
    font = _font(max(width, height) * 0.05, QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(WATERMARK)
    metrics = QFontMetricsF(font)
    step_x = metrics.horizontalAdvance(words) + metrics.height() * 2
    step_y = metrics.height() * 3.2
    reach = (width**2 + height**2) ** 0.5
    row = 0
    y = -reach / 2
    while y < reach / 2:
        x = -reach / 2 - (row % 2) * step_x / 2
        while x < reach / 2:
            p.drawText(QPointF(x, y), words)
            x += step_x
        y += step_y
        row += 1
    p.restore()
    pen.drawn.append(words)


def render_card(data, size="portrait", *, hide_money=False, drawn=None):
    """The card as a QImage; ``drawn`` (a list) receives every string drawn on it."""
    if size not in SIZES:
        raise ValueError("size must be portrait or landscape.")
    if QGuiApplication.instance() is None:
        raise RuntimeError("Create a QGuiApplication before rendering the card.")
    _ensure_fonts()
    text = card_text(data, hide_money=hide_money)
    width, height = SIZES[size].width(), SIZES[size].height()
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(CREAM)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    pen = _Pen(painter, drawn if drawn is not None else [])
    try:
        _background(painter, width, height)
        if size == "portrait":
            _portrait(pen, data, text, width, height)
        else:
            _landscape(pen, data, text, width, height)
        if text["watermark"]:
            _watermark(pen, width, height, text["watermark"])
    finally:
        painter.end()
    return image


def _portrait(pen, data, text, width, height):
    margin = 72
    inner = width - 2 * margin
    _header(pen, margin, 50, data, text, 1.0, 150)
    y = _hero(pen, margin, 232 if "number" in text else 300, inner, text, 1.0)
    y = _money(pen, margin, y + 20, inner, text, 1.0)
    footer_top = height - 40 - _footer_height(text, inner, 1.0)
    cells_height = 124
    cells_top = footer_top - 30 - cells_height
    chart_top = max(y + 34, cells_top - 20 - 400)
    _chart(pen, QRectF(margin, chart_top, inner, cells_top - 20 - chart_top), data, text, 1.0)
    _cells(pen, margin, cells_top, inner, cells_height, text, 1.0, 18)
    pen.p.setPen(QPen(LINE, 2))
    pen.p.drawLine(QPointF(margin, footer_top - 14), QPointF(width - margin, footer_top - 14))
    _footer(pen, margin, footer_top, inner, text, 1.0)


def _landscape(pen, data, text, width, height):
    margin, scale = 44, 0.62
    split = 590
    left_width = split - margin - 12
    footer_top = height - 22 - _footer_height(text, width - 2 * margin, scale)
    _header(pen, margin, 28, data, text, scale * 1.08, 100)
    y = _hero(pen, margin, 146, left_width, text, scale * 1.05)
    _money(pen, margin, y + 10, left_width, text, scale * 1.05)
    right = split + 8
    right_width = width - margin - right
    cells_height = 84
    cells_top = footer_top - 22 - cells_height
    _chart(pen, QRectF(right, 30, right_width, cells_top - 12 - 30), data, text, scale)
    _cells(pen, right, cells_top, right_width, cells_height, text, scale, 10)
    pen.p.setPen(QPen(LINE, 1.5))
    pen.p.drawLine(QPointF(margin, footer_top - 9), QPointF(width - margin, footer_top - 9))
    _footer(pen, margin, footer_top, width - 2 * margin, text, scale)


def save_card(image, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise OSError(f"Could not write {path}")
    return path


def default_folder():
    for candidate in (Path.home() / "Pictures", Path.home() / "Desktop"):
        if candidate.is_dir():
            return candidate
    return Path.home()


def _language(parent, path):
    language = getattr(parent, "language", None)
    code = getattr(language, "code", language)
    if code in ("zh", "en"):
        return code
    try:
        from .ui_language import UiLanguage

        return UiLanguage(path).code
    except (OSError, ValueError, RuntimeError):
        return "zh"


def show_share_card(parent=None, path=None, *, language=None, demo=None):
    """Open the preview dialog for this week's card; returns the (non-modal) dialog.

    ``path`` is the statistics database (default: the user's TOMC store). Without
    ``demo``, a parent with ``test_mode`` (the pet in test mode) turns the demo
    watermark on. Nothing is uploaded; the image is only copied or saved locally.
    """
    from PySide6.QtWidgets import (
        QCheckBox,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
    )

    from .store import default_store_path

    path = Path(path) if path else default_store_path()
    code = language or _language(parent, path)
    english = code == "en"
    if demo is None:
        demo = bool(getattr(parent, "test_mode", False))
    data = card_data(path, code, demo=demo)

    def tr(zh, en):
        return en if english else zh

    dialog = QDialog(parent)
    dialog.setWindowTitle(tr("本周战报", "This week's card"))
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    layout = QVBoxLayout(dialog)
    preview = QLabel()
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview.setMinimumSize(480, 600)
    layout.addWidget(preview)
    options = QHBoxLayout()
    hide = QCheckBox(tr("隐藏金额", "Hide money"))
    hide.setEnabled(data["money"] is not None)
    if data["money"] is None:
        hide.setToolTip(
            tr(
                "这周没有可用的标价，卡上本来就不显示金额。",
                "No listed price this week; the card shows no money.",
            )
        )
    wide = QCheckBox(tr("横版", "Landscape"))
    options.addWidget(hide)
    options.addWidget(wide)
    options.addStretch(1)
    layout.addLayout(options)
    note = QLabel(tr("图片只在本机生成，不会上传。", "Made on this computer; nothing is uploaded."))
    note.setStyleSheet("color: #77806F;")
    note.setWordWrap(True)
    layout.addWidget(note)
    buttons = QHBoxLayout()
    copy = QPushButton(tr("复制图片", "Copy image"))
    save = QPushButton(tr("保存 PNG…", "Save PNG…"))
    close = QPushButton(tr("关闭", "Close"))
    buttons.addWidget(copy)
    buttons.addWidget(save)
    buttons.addStretch(1)
    buttons.addWidget(close)
    layout.addLayout(buttons)
    status = QLabel("")
    status.setStyleSheet("color: #345743;")
    layout.addWidget(status)
    dialog.card_data = data
    dialog.preview, dialog.hide_money, dialog.landscape = preview, hide, wide
    dialog.copy_button, dialog.save_button, dialog.status = copy, save, status

    def current():
        size = "landscape" if wide.isChecked() else "portrait"
        return render_card(data, size, hide_money=hide.isChecked())

    def refresh():
        dialog.image = current()
        box = QSize(560, 320) if wide.isChecked() else QSize(480, 600)
        preview.setMinimumSize(box)
        preview.setPixmap(
            QPixmap.fromImage(dialog.image).scaled(
                box,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        status.setText("")

    def copy_image():
        QGuiApplication.clipboard().setImage(dialog.image)
        status.setText(tr("已复制，可以直接粘贴。", "Copied. Paste it anywhere."))

    def save_image():
        suggested = str(default_folder() / default_filename(data))
        target, _ = QFileDialog.getSaveFileName(
            dialog, tr("保存 PNG", "Save PNG"), suggested, "PNG (*.png)"
        )
        if not target:
            return
        if not target.lower().endswith(".png"):
            target += ".png"
        try:
            save_card(dialog.image, target)
        except OSError:
            status.setText(tr("没能保存，换个文件夹试试。", "Could not save; try another folder."))
            return
        status.setText(tr(f"已保存到 {target}", f"Saved to {target}"))

    hide.toggled.connect(refresh)
    wide.toggled.connect(refresh)
    copy.clicked.connect(copy_image)
    save.clicked.connect(save_image)
    close.clicked.connect(dialog.close)
    refresh()
    if parent is not None:
        parent._share_card_dialog = dialog
    dialog.show()
    return dialog
