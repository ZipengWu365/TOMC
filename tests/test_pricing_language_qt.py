"""Language changes on existing estimate/story windows; isolated fixtures only."""

import os
import re
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QColor, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from tomc import pricing_qt  # noqa: E402
from tomc.impact_story import captions, story_html  # noqa: E402
from tomc.oasis_qt import OasisCelebration  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402

RATE = {"key": "anthropic:fixture:standard", "provider": "anthropic", "model": "fixture",
        "label": "Fixture model", "variant": "standard", "input": 2.0, "cached": 0.2,
        "output": 8.0, "condition": "Standard · 全球基础价", "verified_at": "2026-10-22",
        "sync_status": "bundled", "source": "https://example.test/pricing"}


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    for window in instance.topLevelWidgets():
        window.deleteLater()
    instance.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def owner(app, tmp_path, monkeypatch):
    monkeypatch.setattr(pricing_qt, "all_rates", lambda: [RATE])
    monkeypatch.setattr(pricing_qt, "SETTINGS", tmp_path / "pricing.json")
    window = QWidget()
    window.language = UiLanguage(tmp_path / "memory.sqlite3", window)
    window.language.set_language("zh")
    window.test_mode = True
    window.pricing = {**RATE, "mode": "input", "rate": 2.0, "host": "claude", "evidence": "手选参考模型"}
    window.summary = {"by_counter": [{"reduced_tokens": 5000}]}
    window.details = QWidget(window)
    window.refresh = lambda: None
    sprite = QPixmap(200, 100)
    sprite.fill(QColor("transparent"))
    window.art = SimpleNamespace(sprites=[sprite] * 4)
    yield window
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_estimate_sheet_switches_live_without_changing_selection_or_value(owner, app, tmp_path):
    sheet = pricing_qt.ReferenceSheet(owner, settings_path=tmp_path / "reference.json")
    sheet.show()
    app.processEvents()
    key, value = sheet.models.currentData(), sheet.selected()["rate"]
    assert sheet.tabs.tabText(0) == "模型与估价"
    owner.language.set_language("en")
    app.processEvents()
    assert sheet.tabs.tabText(0) == "Models && estimates"
    assert sheet.host_label.text() == "Host"
    assert sheet.mode.currentText() == "Use uncached input rate"
    assert sheet.models.currentData() == key and sheet.selected()["rate"] == value
    assert "$0.0100" in sheet.preview.text()
    assert sheet.table.horizontalHeaderItem(2).text() == "Cache read"
    assert sheet.models.accessibleName() == "Reference model and tier"
    assert not re.search(r"[\u3400-\u9fff]", sheet.basis.toPlainText() + sheet.story.toPlainText())
    assert "not measured" in sheet.story.toPlainText() or "unmeasured" in sheet.story.toPlainText()
    assert not sheet.grab().isNull()
    owner.language.set_language("zh")
    assert sheet.tabs.tabText(1) == "绿洲的故事"
    assert sheet.models.currentData() == key and sheet.selected()["rate"] == value
    assert not (tmp_path / "reference.json").exists()


def test_detection_error_and_demo_action_retranslate_without_reading_real_settings(owner):
    sheet = pricing_qt.ReferenceSheet(owner)
    sheet.use_detected()
    assert "尚无安装时" in sheet.basis.toPlainText()
    owner.language.set_language("en")
    assert "No saved model-detection record" in sheet.basis.toPlainText()
    assert sheet.save_button.text() == "Demo: settings are not saved"
    assert not sheet.save_button.isEnabled()


def test_oasis_language_preserves_animation_state_and_translates_accessibility(owner, app):
    oasis = OasisCelebration(owner)
    oasis.phase = 0.6
    oasis.show()
    owner.language.set_language("en")
    app.processEvents()
    assert oasis.phase == 0.6 and not oasis.timer.isActive()
    assert oasis.windowTitle() == "TOMC · An oasis grows"
    assert "water savings" in oasis.accessibleName()
    assert "Right-click" in oasis.toolTip()
    assert not re.search(r"[\u3400-\u9fff]", str(captions(owner.language)) + story_html(owner.language))
    assert not oasis.grab().isNull()
    owner.language.set_language("zh")
    assert "绿洲诞生" in oasis.windowTitle()
