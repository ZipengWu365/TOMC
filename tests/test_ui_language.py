"""Language preferences are portable UI settings, never session policy writes."""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtGui import QFont  # noqa: E402

from tomc import ui_language  # noqa: E402
from tomc.ui_language import UiLanguage, ui_font  # noqa: E402


def test_missing_settings_uses_locale_without_creating_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_language, "system_language", lambda: "en")
    path = tmp_path / "new" / "memory.sqlite3"
    language = UiLanguage(path)
    assert language.code == "en"
    assert not path.parent.exists()
    assert language.tr("数量 {count:,}", "Count {count:,}", count=1234) == "Count 1,234"


@pytest.mark.parametrize(
    "contents", [b"{broken", b"\xff", b"[]", b'{"language":"fr"}', b'{"language":{}}']
)
def test_corrupt_or_unknown_settings_fall_back(tmp_path, monkeypatch, contents):
    monkeypatch.setattr(ui_language, "system_language", lambda: "zh")
    path = tmp_path / "ui_settings.json"
    path.write_bytes(contents)
    assert UiLanguage(tmp_path / "memory.sqlite3").code == "zh"
    assert path.read_bytes() == contents


def test_atomic_persistence_preserves_other_ui_values_and_never_edits_db(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_language, "system_language", lambda: "zh")
    db = tmp_path / "memory.sqlite3"
    db.write_bytes(b"DB session enabled=false; not a UI settings file")
    path = tmp_path / "ui_settings.json"
    path.write_text(json.dumps({"window_position": [1, 2], "language": "zh"}), encoding="utf-8")
    language = UiLanguage(db)
    changes = []
    language.changed.connect(changes.append)
    language.set_language("en")
    language.set_language("en")
    assert changes == ["en"]
    assert UiLanguage(db).code == "en"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "window_position": [1, 2],
        "language": "en",
    }
    assert db.read_bytes() == b"DB session enabled=false; not a UI settings file"
    assert not list(tmp_path.glob(".ui-settings-*"))


def test_failed_save_keeps_prior_language_and_setting(tmp_path, monkeypatch):
    language = UiLanguage(tmp_path / "memory.sqlite3")
    language.set_language("zh")
    before = language.path.read_bytes()
    changes = []
    language.changed.connect(changes.append)

    def denied(*args):
        raise PermissionError("fixture")

    monkeypatch.setattr(ui_language.os, "replace", denied)
    with pytest.raises(PermissionError):
        language.set_language("en")
    assert language.code == "zh" and not changes
    assert language.path.read_bytes() == before
    assert not list(tmp_path.glob(".ui-settings-*"))


def test_invalid_language_rejected_without_writing(tmp_path):
    language = UiLanguage(tmp_path / "memory.sqlite3")
    for value in ("fr", "", None, {}, []):
        with pytest.raises(ValueError):
            language.set_language(value)
    assert not language.path.exists()


def test_cjk_font_fallback_disables_subpixel_color_fringes(monkeypatch):
    monkeypatch.setattr(ui_language.sys, "platform", "win32")
    font = ui_font()
    assert font.families()[0] == "Microsoft YaHei UI"
    assert "Segoe UI" in font.families()
    assert font.styleStrategy() & QFont.StyleStrategy.NoSubpixelAntialias


def test_mac_uses_system_typeface(monkeypatch):
    monkeypatch.setattr(ui_language.sys, "platform", "darwin")
    monkeypatch.setattr(ui_language.QFontDatabase, "systemFont", lambda _: QFont("System fixture"))
    font = ui_font()
    assert font.family() == "System fixture"
    assert font.pointSize() >= 12
