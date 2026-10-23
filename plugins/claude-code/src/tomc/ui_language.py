"""Shared, local UI language preference independent of session and pricing data."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, Signal
from PySide6.QtGui import QFont


def system_language() -> str:
    return "zh" if QLocale.system().name().lower().startswith("zh") else "en"


def ui_font(point_size: int = 9) -> QFont:
    """Prefer a font with CJK coverage; keep Latin and cross-platform fallbacks."""
    font = QFont()
    font.setFamilies(
        [
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Noto Sans CJK SC",
            "PingFang SC",
            "Segoe UI",
            "sans-serif",
        ]
    )
    font.setPointSize(point_size)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias
    )
    return font


class UiLanguage(QObject):
    changed = Signal(str)

    def __init__(self, path: Path | str, parent: QObject | None = None):
        super().__init__(parent)
        self.path = Path(path).parent / "ui_settings.json"
        self._code = system_language()
        try:
            settings = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(settings, dict) and settings.get("language") in ("zh", "en"):
                self._code = settings["language"]
        except (OSError, ValueError, UnicodeError):
            pass

    @property
    def code(self) -> str:
        return self._code

    def tr(self, zh: str, en: str, **values) -> str:
        text = zh if self._code == "zh" else en
        return text.format(**values) if values else text

    def set_language(self, code: str) -> None:
        if code not in ("zh", "en"):
            raise ValueError("UI language must be 'zh' or 'en'")
        # Persist even when the default was selected explicitly. A later change
        # to the system locale must not discard the user's preference.
        settings = {}
        try:
            previous = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(previous, dict):
                settings = previous
        except (OSError, ValueError, UnicodeError):
            pass
        settings["language"] = code
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".ui-settings-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(settings, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        if code != self._code:
            self._code = code
            self.changed.emit(code)
