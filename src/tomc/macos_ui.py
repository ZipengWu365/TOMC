"""macOS presentation primitives. No storage, connection or request behavior lives here."""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


def is_macos():
    return sys.platform == "darwin"


def tokens(widget=None):
    """Follow system appearance; a window override is useful for isolated UI previews."""
    appearance = None
    current = widget
    while current is not None:
        appearance = current.property("tomcAppearance")
        if appearance in ("light", "dark"):
            break
        current = current.parentWidget()
    app = QApplication.instance()
    dark = appearance == "dark"
    if appearance not in ("light", "dark") and app is not None:
        scheme = app.styleHints().colorScheme()
        dark = scheme == Qt.ColorScheme.Dark or (
            scheme == Qt.ColorScheme.Unknown
            and app.palette().color(QPalette.ColorRole.Window).lightness() < 128
        )
    if dark:
        return dict(
            background="#222326",
            surface="#2C2D31",
            raised="#34353A",
            sidebar="#27282C",
            text="#F2F3F5",
            secondary="#C0C2C9",
            muted="#A0A3AD",
            border="#484A52",
            accent="#84B6FF",
            accent_text="#102B4C",
            selection="#28456D",
            selection_text="#F3F7FF",
            danger="#FF9690",
            hover="#3D3F46",
            field="#202125",
        )
    return dict(
        background="#F5F5F7",
        surface="#FFFFFF",
        raised="#FFFFFF",
        sidebar="#ECEEF2",
        text="#202124",
        secondary="#555963",
        muted="#666B76",
        border="#D5D8DF",
        accent="#075FC8",
        accent_text="#FFFFFF",
        selection="#DCEAFF",
        selection_text="#154478",
        danger="#B82D27",
        hover="#E5E8EE",
        field="#FFFFFF",
    )


def text_style(widget, size=13, color="#443B35", bold=False):
    """Keep legacy call sites' emphasis, with readable type and semantic colors on Mac."""
    tone = "text"
    if color.lower() in ("#706659", "#74685d", "#796d60"):
        tone = "muted"
    elif color.lower() in ("#345743", "#52705d", "#3f6b53", "#507461"):
        tone = "accent"
    elif color.lower() == "#866239":
        tone = "secondary"
    widget.setProperty("tomcTone", tone)
    size = max(12, size + (1 if size < 16 else 4))
    widget.setStyleSheet(f"font-size: {size}px; font-weight: {600 if bold else 400};")


def _stylesheet(c):
    return f"""
    QWidget {{ color: {c["text"]}; font-size: 13px; }}
    QWidget[tomcWindowSurface="true"] {{ background: {c["background"]}; }}
    QLabel {{ background: transparent; }}
    QLabel[tomcTone="muted"], QLabel#muted, QLabel#subtitle {{ color: {c["muted"]}; }}
    QLabel[tomcTone="secondary"] {{ color: {c["secondary"]}; }}
    QLabel[tomcTone="accent"] {{ color: {c["accent"]}; }}
    QLabel#privacy {{ background: {c["selection"]}; color: {c["selection_text"]}; border: 1px solid {c["border"]}; border-radius: 8px; padding: 10px 12px; }}
    QLabel#title {{ font-size: 22px; font-weight: 600; }}
    QLabel#conversationTitle {{ font-size: 16px; font-weight: 600; }}
    QLabel#metric {{ font-size: 18px; font-weight: 600; }}
    QLabel#section {{ font-size: 13px; font-weight: 600; }}
    QWidget#sidebar {{ background: {c["sidebar"]}; border-radius: 10px; }}
    QFrame#card, QWidget#card {{ background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 10px; }}
    QFrame#rule {{ background: {c["border"]}; border: none; }}
    QPushButton {{ background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 6px; padding: 6px 12px; }}
    QPushButton:hover {{ background: {c["hover"]}; }}
    QPushButton:pressed, QPushButton:checked {{ background: {c["selection"]}; color: {c["selection_text"]}; }}
    QPushButton:focus, QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 1px solid {c["accent"]}; }}
    QPushButton:disabled {{ color: {c["muted"]}; background: {c["background"]}; }}
    QPushButton#primary {{ background: {c["accent"]}; color: {c["accent_text"]}; border-color: {c["accent"]}; font-weight: 600; }}
    QPushButton#primary:hover {{ background: {c["selection_text"]}; }}
    QPushButton#destructive {{ color: {c["danger"]}; }}
    QPushButton#primary:disabled, QPushButton#destructive:disabled {{ background: {c["background"]}; color: {c["muted"]}; border-color: {c["border"]}; }}
    QPushButton#link, QPushButton#foot, QPushButton#language {{ background: transparent; border: 1px solid transparent; padding: 4px 6px; color: {c["accent"]}; }}
    QPushButton#foot {{ color: {c["muted"]}; }}
    QPushButton#link:hover, QPushButton#foot:hover, QPushButton#language:hover {{ background: {c["hover"]}; }}
    QPushButton#language:checked {{ background: {c["selection"]}; color: {c["selection_text"]}; }}
    QWidget#periods {{ background: {c["sidebar"]}; border-radius: 7px; }}
    QPushButton#period {{ background: transparent; border: none; padding: 3px 8px; color: {c["secondary"]}; }}
    QPushButton#period:checked {{ background: {c["surface"]}; color: {c["text"]}; font-weight: 600; }}
    QPushButton#chip {{ padding: 4px 9px; font-size: 12px; }}
    QLineEdit, QPlainTextEdit, QTextBrowser, QTableWidget {{ background: {c["field"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 7px; selection-background-color: {c["selection"]}; selection-color: {c["selection_text"]}; }}
    QLineEdit {{ padding: 6px 8px; }}
    QPlainTextEdit, QTextBrowser {{ padding: 10px; }}
    QComboBox {{ background: {c["field"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 6px; min-height: 24px; padding: 3px 8px; }}
    QComboBox QAbstractItemView {{ background: {c["raised"]}; color: {c["text"]}; selection-background-color: {c["selection"]}; selection-color: {c["selection_text"]}; }}
    QListWidget {{ background: {c["sidebar"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 8px; outline: none; }}
    QListWidget::item {{ border: none; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {c["selection"]}; color: {c["selection_text"]}; }}
    QListWidget::item:hover {{ background: {c["hover"]}; }}
    QCheckBox {{ spacing: 8px; padding: 5px 0; }}
    QTabWidget::pane {{ border: none; }}
    QTabWidget::tab-bar {{ alignment: left; }}
    QTabBar::tab {{ background: {c["sidebar"]}; color: {c["secondary"]}; padding: 7px 18px; margin: 0 0 10px 0; }}
    QTabBar::tab:selected {{ background: {c["surface"]}; color: {c["text"]}; font-weight: 600; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle {{ background: {c["muted"]}; border-radius: 3px; min-height: 24px; min-width: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QProgressBar {{ border: none; background: {c["border"]}; border-radius: 2px; }}
    QProgressBar::chunk {{ background: {c["accent"]}; border-radius: 2px; }}
    QHeaderView::section {{ background: {c["sidebar"]}; color: {c["secondary"]}; border: none; border-bottom: 1px solid {c["border"]}; padding: 8px; }}
    QTableWidget {{ gridline-color: {c["border"]}; alternate-background-color: {c["background"]}; }}
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:hover {{ background: {c["border"]}; }}
    QToolTip {{ background: {c["raised"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 5px; }}
    """


class _Appearance(QObject):
    def __init__(self, widget, variant):
        super().__init__(widget)
        self.widget, self.variant = widget, variant
        if variant == "window":
            # Cocoa can replace a dialog's Window palette when creating its native window.
            # Paint the surface through the same stylesheet that supplies its text colours.
            widget.setProperty("tomcWindowSurface", True)
            widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.installEventFilter(self)
        QApplication.instance().styleHints().colorSchemeChanged.connect(self.apply)
        self.apply()

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.DynamicPropertyChange
            and bytes(event.propertyName()) == b"tomcAppearance"
        ):
            self.apply()
            for child in self.widget.findChildren(QWidget):
                if hasattr(child, "_tomc_appearance"):
                    child._tomc_appearance.apply()
        return False

    def apply(self, *_):
        widget = self.widget
        # Settle delayed child styling before installing the window's palette.
        widget.ensurePolished()
        c = tokens(widget)
        palette = QPalette(widget.palette())
        for role, key in (
            (QPalette.ColorRole.Window, "background"),
            (QPalette.ColorRole.WindowText, "text"),
            (QPalette.ColorRole.Base, "field"),
            (QPalette.ColorRole.AlternateBase, "sidebar"),
            (QPalette.ColorRole.Text, "text"),
            (QPalette.ColorRole.Button, "surface"),
            (QPalette.ColorRole.ButtonText, "text"),
            (QPalette.ColorRole.Highlight, "selection"),
            (QPalette.ColorRole.HighlightedText, "selection_text"),
            (QPalette.ColorRole.Link, "accent"),
            (QPalette.ColorRole.PlaceholderText, "muted"),
        ):
            palette.setColor(role, QColor(c[key]))
        for role in (
            QPalette.ColorRole.Text,
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.ButtonText,
        ):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["muted"]))
        widget.setStyleSheet(_stylesheet(c))
        widget.setPalette(palette)
        widget.setAutoFillBackground(self.variant == "window")
        widget.update()


def install_macos_style(widget, variant="window"):
    """Install one live appearance controller per Mac window; other platforms are untouched."""
    if not is_macos():
        return
    from .ui_language import ui_font

    widget.setFont(ui_font())
    if not hasattr(widget, "_tomc_appearance"):
        widget._tomc_appearance = _Appearance(widget, variant)
    else:
        widget._tomc_appearance.apply()
