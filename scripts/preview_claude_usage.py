"""Native Claude TOMC companion; records only its own rendering, never the desktop."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--store", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    load_preview_fonts()
    database = args.store or output / "widget_test.sqlite3"
    pet = Companion(
        database,
        test_mode=not args.store,
        connect_quota=False,
        state_file=output / "widget_state.json",
    )
    pet.set_host("claude")
    pet.details.resize_to_content()
    events = []

    def save(kind):
        events.append(
            {
                "event": kind,
                "preparations": pet.summary["preparations"],
                "bubble": pet.number.text(),
                "total": pet.details.total.text(),
                "pet_width": pet.width(),
                "expression": pet.art.expression,
            }
        )
        (output / "display-events.json").write_text(
            json.dumps(
                {
                    "events": events,
                    "database": str(database),
                    "isolated_test": not bool(args.store),
                    "desktop_control_used": False,
                    "quota_provider": "Claude",
                    "quota_connected": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def started():
        pet.details.hide()
        save("animation_started")
        QTimer.singleShot(
            650,
            lambda: pet.grab().save(str(output / f"animation-{pet.summary['preparations']}.png")),
        )

    def finished():
        save("bubble_shown")
        pet.grab().save(str(output / f"bubble-{pet.summary['preparations']}.png"))
        if not args.store:
            # Dispatch directly to our own widget, never to OS input.
            QTest.mouseClick(pet.card, Qt.MouseButton.LeftButton)
            app.processEvents()
            save("statistics_clicked")
            pet.details.grab().save(str(output / f"statistics-{pet.summary['preparations']}.png"))
            QTimer.singleShot(3000, pet.details.hide)

    pet.art.collecting.connect(started)
    pet.art.collected.connect(finished)
    pet.show()
    save("watching")
    app.exec()


if __name__ == "__main__":
    main()
