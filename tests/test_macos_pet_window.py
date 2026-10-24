"""Window-policy and preview regressions; no production database or desktop input."""

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc import usage_widget_qt  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
def test_companion_remains_a_tool_and_only_mac_uses_persistent_visibility(
    app, tmp_path, monkeypatch, platform
):
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    with monkeypatch.context() as patch:
        patch.setattr(usage_widget_qt.sys, "platform", platform)
        pet = usage_widget_qt.Companion(
            tmp_path / "memory.sqlite3", test_mode=True, connect_quota=False
        )
    try:
        assert pet.windowType() == Qt.WindowType.Tool
        assert pet.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        assert pet.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow) == (
            platform == "darwin"
        )
        assert pet.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating) == (
            platform != "darwin"
        )
    finally:
        pet.close()
        pet.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_preview_uses_all_four_input_length_forms_without_writing_usage(app, tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "scripts/desktop_pet_stages.py"
    spec = importlib.util.spec_from_file_location("tomc_stage_preview", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "platform", "darwin")
        player = module.StagePlayer(tmp_path)
    try:
        assert [art.level for art in player.arts] == [1, 2, 3, 4]
        assert not player.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        assert not player.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        player.show_stats(3)
        assert "1,000,000" in player.stats.text()
        assert "不执行压缩" in player.stats.text()
        assert not list(tmp_path.glob("*.sqlite3"))
    finally:
        player.close()
        player.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
