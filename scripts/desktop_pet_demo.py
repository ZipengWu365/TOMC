"""Visible native cat-head demo; uses only its own UI and an isolated numeric database."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--restore-launcher", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    db = args.output / "demo.sqlite3"
    if db.exists():
        raise SystemExit("Use a fresh demo folder to keep each run separate.")
    store = UsageStore(db)
    store.record(
        {
            "counter": "demo-estimate",
            "usable": True,
            "input_tokens": 106000,
            "memory_tokens": 6000,
            "reduced_tokens": 100000,
        }
    )
    app = QApplication([])
    load_preview_fonts()
    widget = Companion(db, test_mode=True)
    widget.setWindowTitle("TOMC · 省 token 小猫 — 独立演示")
    replay = QPushButton("重播收上下文动画（不增加统计）")
    widget.details.layout().addWidget(replay)
    note = QPushButton("关闭演示")
    widget.details.layout().addWidget(note)
    note.clicked.connect(widget.close)
    opened = False

    def state(phase):
        (args.output / "demo_state.json").write_text(
            json.dumps(
                {
                    "phase": phase,
                    "details_visible": widget.details.isVisible(),
                    "total": widget.details.total.text(),
                    "production_database_written": False,
                    "desktop_control_used": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def show_details():
        nonlocal opened
        if not widget.details.isVisible():
            widget.toggle_details()
        opened = True
        state("cumulative_panel_shown")

    def after_animation():
        widget.caption.setText("演示 · 本次预计少用")
        state("animation_complete_and_result_shown")
        if not opened:
            QTimer.singleShot(1400, show_details)

    def replay_animation():
        nonlocal opened
        opened = False
        widget.details.hide()
        widget.report_timer.stop()
        widget.layout_report(False)
        widget.active_report = store.summary()["last_preparation"]
        widget.art.collect()
        state("replaying_without_new_statistics")

    def deposit():
        store.record(
            {
                "counter": "demo-estimate",
                "usable": True,
                "input_tokens": 1800,
                "memory_tokens": 126,
                "reduced_tokens": 1674,
            }
        )
        widget.refresh()
        state("collecting_context")

    replay.clicked.connect(replay_animation)
    widget.art.collected.connect(after_animation)
    widget.show()
    # More visible than the normal bottom-corner placement; never manipulates another window.
    area = app.primaryScreen().availableGeometry()
    widget.move(area.center().x() + 180, area.center().y() - 70)
    state("waiting_to_demonstrate")
    QTimer.singleShot(3000, deposit)
    app.exec()
    if args.restore_launcher:
        subprocess.Popen(
            [sys.executable, str(args.restore_launcher)], cwd=str(args.restore_launcher.parent)
        )


if __name__ == "__main__":
    main()
