"""Appearance changes must preserve controls and leave non-Mac windows untouched."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget  # noqa: E402

from tomc import macos_ui  # noqa: E402


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    widget = QWidget()
    yield app, widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_appearance_change_preserves_editor_state_and_uses_readable_palette(window, monkeypatch):
    app, widget = window
    monkeypatch.setattr(macos_ui, "is_macos", lambda: True)
    editor = QLineEdit("Unsubmitted draft")
    QVBoxLayout(widget).addWidget(editor)
    editor.setSelection(0, 11)
    macos_ui.install_macos_style(widget)
    controller = widget._tomc_appearance
    for appearance in ("light", "dark", "light"):
        widget.setProperty("tomcAppearance", appearance)
        app.processEvents()
        c = macos_ui.tokens(editor)
        assert editor.text() == "Unsubmitted draft"
        assert editor.selectedText() == "Unsubmitted"
        assert widget.palette().color(QPalette.ColorRole.Window) == QColor(c["background"])
        assert widget.palette().color(QPalette.ColorRole.Text) == QColor(c["text"])
        assert abs(QColor(c["text"]).lightness() - QColor(c["field"]).lightness()) > 160
    macos_ui.install_macos_style(widget)
    assert widget._tomc_appearance is controller


def test_non_mac_style_is_unchanged(window, monkeypatch):
    _, widget = window
    monkeypatch.setattr(macos_ui, "is_macos", lambda: False)
    widget.setStyleSheet("color: red;")
    before = widget.palette()
    macos_ui.install_macos_style(widget)
    assert widget.styleSheet() == "color: red;"
    assert widget.palette() == before
    assert not hasattr(widget, "_tomc_appearance")


def test_parent_appearance_updates_child_window_style_and_paint_tokens(window, monkeypatch):
    app, widget = window
    monkeypatch.setattr(macos_ui, "is_macos", lambda: True)
    child = QWidget(widget)
    macos_ui.install_macos_style(widget)
    macos_ui.install_macos_style(child, variant="popover")
    widget.setProperty("tomcAppearance", "dark")
    app.processEvents()
    assert macos_ui.tokens(child)["text"] in child.styleSheet()
    child.setProperty("tomcAppearance", "light")
    widget.setProperty("tomcAppearance", "light")
    widget.setProperty("tomcAppearance", "dark")
    app.processEvents()
    assert macos_ui.tokens(child)["text"] in child.styleSheet()
    assert child.palette().color(QPalette.ColorRole.Text) == QColor("#202124")
