"""Preview the native profile panel with isolated data, without desktop automation."""

import argparse
import json
import os
import sys
from pathlib import Path

if "--check" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = "2"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtGui import QContextMenuEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


def record(store, before, after, counter="demo-estimate"):
    store.record({"counter": counter, "usable": True, "input_tokens": before,
                  "memory_tokens": after, "reduced_tokens": before-after})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--quota", action="store_true", help="Read the signed-in Codex account allowance")
    parser.add_argument("--store", type=Path, help="Read existing real statistics; do not create demo records")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.check and args.store:
        raise ValueError("Checks must use isolated data")
    db = args.store.resolve() if args.store else output / "profile-demo.sqlite3"
    if not args.store and db.exists():
        raise ValueError("Use a fresh output directory; preview data is never overwritten.")
    store = UsageStore(db)
    if not args.store:
        record(store, 24000, 1900)
        record(store, 1800, 126)
    app = QApplication([])
    load_preview_fonts()
    pet = Companion(db, test_mode=not args.store, connect_quota=args.quota)
    if args.quota:
        def quota_received(state):
            (output / "quota_state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        pet.quota_reader.updated.connect(quota_received)
    pet.show()

    def snapshot(name):
        app.processEvents()
        pet.details.grab().save(str(output / f"{name}.png"))

    def open_panel():
        pet.toggle_details()
        app.processEvents()
        result = {"panel_visible": pet.details.isVisible(),
                  "panel_size": [pet.details.width(), pet.details.height()],
                  "pet_width": pet.width(), "expression": pet.art.expression,
                  "statistics_are_simulated": not bool(args.store), "production_database_written": False,
                  "desktop_control_used": False}
        if args.check:
            pet.timer.stop()
            snapshot("profile")
            assert pet.details.isVisible() and pet.width() == 72
            assert pet.art.expression == "dejected" and pet.details.portrait.expression == "dejected"
            for period in ("today", "7d", "all"):
                QTest.mouseClick(pet.details.buttons[period], Qt.MouseButton.LeftButton)
                assert pet.period == period and pet.details.buttons[period].isChecked()
                assert pet.details.total.text() == "92.1%"
                assert pet.art.phase is None
            QTest.mouseClick(pet.details.info_button, Qt.MouseButton.LeftButton)
            assert pet.details.scope.isVisible()
            snapshot("profile-explained")
            QTest.mouseClick(pet.details.info_button, Qt.MouseButton.LeftButton)
            assert not pet.details.scope.isVisible()
            for name, data in (
                ("empty", []),
                ("negative", [(100, 300, "demo-estimate")]),
                ("mixed", [(1800, 126, "demo-estimate"), (1000, 250, "another-counter")]),
                ("large", [(9999999999999, 1200000000000, "demo-estimate")]),
            ):
                scenario = UsageStore(output / f"{name}.sqlite3")
                for before, after, counter in data:
                    record(scenario, before, after, counter)
                pet.store, pet.last_signature, pet.initialized = scenario, None, False
                pet.refresh()
                snapshot(name)
                assert pet.details.width() == 240
                assert pet.art.phase is None
                if name == "negative":
                    assert pet.details.caption.text() == "上下文增加"
                    assert pet.details.total.text() == "200.0%"
                if name == "mixed":
                    assert pet.details.total.text() == "分口径"
                    assert "another-counter" in pet.details.rows.text()
            broken = output / "broken.sqlite3"
            broken.write_text("invalid database", encoding="utf-8")
            pet.store, pet.last_signature = UsageStore(broken), None
            pet.refresh()
            snapshot("error")
            assert pet.error == "read_failed" and pet.details.total.text() == "暂不可读"
            pet.store, pet.last_signature, pet.initialized = store, None, False
            pet.refresh()
            assert pet.details.total.text() == "92.1%"
            pet.details.set_quota({"status": "ready", "windows": [
                {"bucket": "codex", "period": "本周", "remaining": 68, "resets_at": None}]})
            assert pet.details.quota_value.text() == "剩余 68%"
            snapshot("quota-simulated")
            pet.details.set_quota({"status": "unavailable", "windows": []})
            assert pet.details.quota_value.text() == "暂不可读"
            snapshot("quota-unavailable")
            QTest.keyClick(pet.details, Qt.Key.Key_Escape)
            assert not pet.details.isVisible() and pet.isVisible()
            pet.toggle_details()
            QTest.mouseClick(pet.details.close_button, Qt.MouseButton.LeftButton)
            assert not pet.details.isVisible() and pet.isVisible()
            result["checks"] = ["periods", "no_smile_on_click", "scope_toggle", "empty",
                                "negative", "mixed_counters", "long_numbers", "read_error_recovery",
                                "escape_dismiss", "close_dismiss", "quota_remaining_not_savings",
                                "quota_failure_clears_stale_values"]
            # Deliver a context event to our own Qt widget, never the OS input stream.
            menu_event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                          pet.rect().center(), pet.mapToGlobal(pet.rect().center()))
            QApplication.sendEvent(pet, menu_event)
            app.processEvents()
            assert pet.pet_menu.isVisible()
            pet.quit_action.trigger()
            assert not pet.isVisible() and not pet.details.isVisible()
            assert not pet.timer.isActive() and not pet.art.animation_timer.isActive()
            result["checks"].append("right_click_exit")
        (output / "state.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.check:
            pet.close()

    QTimer.singleShot(250, open_panel)
    app.exec()


if __name__ == "__main__":
    main()
