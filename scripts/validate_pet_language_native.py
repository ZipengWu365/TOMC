"""Exercise installed native language buttons without global mouse/keyboard input.

Uses the real preference file, ends in Chinese, and records only TOMC widgets.
Does not insert usage/activity, send model requests, or change processing policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc/memory.sqlite3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.store.is_file():
        parser.error("An existing installed store is required")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.runtime.resolve() / "src"))
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication

    from tomc.ui_language import UiLanguage, ui_font
    from tomc.usage_widget_qt import Companion, load_preview_fonts

    app = QApplication([])
    if app.platformName() != "windows":
        raise RuntimeError("Native Windows is required")
    load_preview_fonts()
    app.setFont(ui_font())
    digest = hashlib.sha256(str(args.store).casefold().encode()).hexdigest()[:24]
    lock = QLockFile(str(Path(tempfile.gettempdir()) / f"tomc-pet-{digest}.lock"))
    if not lock.tryLock(0):
        raise RuntimeError("Close the current pet before acceptance")
    report = {
        "native_platform": app.platformName(),
        "global_input_sent": False,
        "synthetic_activity_inserted": False,
        "steps": [],
        "errors": [],
    }
    pet = None
    try:
        pet = Companion(args.store, test_mode=False, connect_quota=False)
        pet.set_host((pet.pricing or {}).get("host", "claude"))
        pet.show()

        def save():
            (args.output / "language.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        def guard(action):
            def execute():
                try:
                    action()
                except Exception as error:
                    report["errors"].append(type(error).__name__)
                    app.quit()

            return execute

        def change(code):
            if not pet.details.isVisible():
                pet.toggle_details()
            pet.details.language_buttons[code].click()

        def capture(code, expanded=False):
            expected = "界面语言" if code == "zh" else "Language"
            persisted = UiLanguage(args.store).code
            assert pet.language.code == persisted == code
            assert pet.details.language_title.text() == expected
            assert pet.details.language_buttons[code].isChecked()
            assert pet.details.isVisible()
            name = (
                f"panel-{code}-{'expanded' if expanded else 'compact'}-{len(report['steps'])}.png"
            )
            assert pet.details.grab().save(str(args.output / name))
            report["steps"].append(
                {
                    "code": code,
                    "persisted": persisted,
                    "title": expected,
                    "file": name,
                    "visible": pet.details.isVisible(),
                    "device_pixel_ratio": pet.details.devicePixelRatioF(),
                    "size": [pet.details.width(), pet.details.height()],
                }
            )
            save()

        steps = [
            (300, lambda: change("zh")),
            (800, lambda: capture("zh")),
            (1100, lambda: change("en")),
            (1600, lambda: capture("en")),
            (1900, lambda: pet.details.toggle_scope(True)),
            (2400, lambda: capture("en", True)),
            (2700, lambda: change("zh")),
            (3200, lambda: capture("zh", True)),
            (3500, lambda: pet.details.toggle_scope(False)),
            (4000, lambda: capture("zh")),
            (4300, app.quit),
        ]
        for delay, action in steps:
            QTimer.singleShot(delay, guard(action))
        app.exec()
        report["passed"] = not report["errors"] and len(report["steps"]) == 5
        report["final_language"] = UiLanguage(args.store).code
        save()
    finally:
        if pet is not None:
            pet.close()
        lock.unlock()
    print(json.dumps({"passed": report.get("passed", False), "output": str(args.output)}))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
