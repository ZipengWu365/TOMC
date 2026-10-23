"""Compact native four-stage demo; isolated numbers, no computer-control APIs."""

import argparse
import json
import os
import sys
from pathlib import Path

if "--check" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget  # noqa: E402

from tomc.pet_growth import STAGES  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import STYLE, Companion, load_preview_fonts  # noqa: E402


class EvolutionDemo(QWidget):
    def __init__(self, output, check=False):
        super().__init__()
        self.output, self.check = output, check
        self.setWindowTitle("TOMC · 四阶段演示")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedSize(470, 86)
        self.stores = []
        for i, (threshold, _, _) in enumerate(STAGES):
            store = UsageStore(output / f"stage-{i + 1}.sqlite3")
            if store.path.exists():
                raise ValueError("Choose a fresh demo output directory")
            store.record(
                {
                    "counter": "demo-estimate",
                    "usable": True,
                    "input_tokens": threshold + 100,
                    "memory_tokens": 100,
                    "reduced_tokens": threshold,
                }
            )
            store.record(
                {
                    "counter": "demo-estimate",
                    "usable": True,
                    "input_tokens": 1800,
                    "memory_tokens": 126,
                    "reduced_tokens": 1674,
                }
            )
            self.stores.append(store)
        self.pet = Companion(self.stores[0].path, test_mode=True)
        self.pet.details.quota_title.setText("账户额度")
        self.pet.details.quota_value.setText("演示不读取")
        self.pet.details.quota_detail.setText("本演示使用独立模拟数据，不计入真实统计。")
        self.pet.setWindowTitle("TOMC · 省 token 小猫 · 演示")
        self.pet.art.collected.connect(self.finished)
        self.current, self.completed, self.automatic = 0, [], False
        self.max_width, self.min_width = 0, 999
        self.sample = QTimer(self)
        self.sample.timeout.connect(self.measure)
        self.sample.start(40)
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.timeout.connect(self.eat)
        self.next_timer = QTimer(self)
        self.next_timer.setSingleShot(True)
        self.next_timer.timeout.connect(self.next_stage)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.status = QLabel("TOMC · 演示数字；点击猫头看累计")
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        for i in range(4):
            button = QPushButton(f"{i + 1} 阶")
            button.clicked.connect(lambda checked=False, n=i: self.play(n))
            buttons.addWidget(button)
        all_button = QPushButton("全部重播")
        all_button.clicked.connect(self.start_all)
        buttons.addWidget(all_button)
        close = QPushButton("关闭")
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
        self.pet.move(area.right() - 110, self.y() - 155)
        self.pet.show()
        QTimer.singleShot(500 if check else 1800, self.start_all)

    def record(self, phase):
        (self.output / "demo_state.json").write_text(
            json.dumps(
                {
                    "phase": phase,
                    "current_stage": self.current + 1,
                    "completed_stages": self.completed,
                    "idle_art_width": self.min_width,
                    "expanded_art_width": self.max_width,
                    "current_art_width": self.pet.art.width(),
                    "expression": self.pet.art.expression,
                    "desktop_control_used": False,
                    "production_database_written": False,
                    "statistics_are_simulated": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def measure(self):
        self.min_width = min(self.min_width, self.pet.art.width())
        self.max_width = max(self.max_width, self.pet.art.width())

    def start_all(self):
        self.completed = []
        self.automatic = True
        self.play(0, auto=True)

    def play(self, index, auto=False):
        self.delay.stop()
        self.next_timer.stop()
        self.automatic = auto
        self.current = index
        self.pet.oasis.close()
        self.pet.pending_victory = False
        self.pet.details.hide()
        self.pet.art.animation_timer.stop()
        self.pet.art.phase = None
        self.pet.report_timer.stop()
        self.pet.active_report = None
        self.pet.pending_reports.clear()
        self.pet.layout_report(False)
        self.pet.store = self.stores[index]
        self.pet.initialized, self.pet.last_signature = False, None
        self.pet.refresh()
        self.status.setText(f"{index + 1}/4 {STAGES[index][1]} · 平时委屈脸；马上开始干活")
        assert self.pet.art.expression == "dejected"
        self.record("compact_before_collection")
        if self.check:
            self.pet.grab().save(str(self.output / f"stage-{index + 1}-idle.png"))
        self.delay.start(500 if self.check else 1200)

    def eat(self):
        self.pet.pending_victory = self.current == 3
        self.pet.active_report = self.stores[self.current].summary()["last_preparation"]
        self.pet.art.collect()
        self.status.setText(
            f"{self.current + 1}/4 {STAGES[self.current][1]} · "
            + ("三次撞击，把上下文编译成小卡片" if self.current == 1 else "放大笑脸，收上下文……")
        )
        self.measure()
        assert self.pet.art.expression == "smiling"
        self.record("collecting")
        if self.check:
            QTimer.singleShot(1100, self.capture_active)
            if self.current == 1:
                for delay, label in (
                    (500, "loose"),
                    (950, "hit1"),
                    (1290, "hit2"),
                    (1630, "hit3"),
                    (2500, "compiled"),
                ):
                    QTimer.singleShot(delay, lambda name=label: self.capture_forge(name))

    def capture_forge(self, name):
        self.pet.grab().save(str(self.output / f"forge-{name}.png"))

    def capture_active(self):
        self.pet.grab().save(str(self.output / f"stage-{self.current + 1}-eating.png"))

    def finished(self):
        if self.current + 1 not in self.completed:
            self.completed.append(self.current + 1)
        self.status.setText(f"{STAGES[self.current][1]} · 完成后恢复委屈脸 · 72 px")
        assert self.pet.art.expression == "dejected"
        self.record("compact_after_collection")
        if self.check:
            self.pet.grab().save(str(self.output / f"stage-{self.current + 1}-result.png"))
        if self.automatic:
            self.next_timer.start(
                self.pet.oasis.DURATION + 500
                if self.current == 3
                else (600 if self.check else 2600)
            )

    def next_stage(self):
        if self.current < 3:
            self.play(self.current + 1, auto=True)
        else:
            self.automatic = False
            self.pet.hide_report()
            self.status.setText("四阶段已演示完 · 点击阶段重播；点猫头看累计")
            self.record("all_stages_complete")
            if self.check:
                assert self.completed == [1, 2, 3, 4]
                assert self.min_width == 72 and self.max_width == 132
                assert self.pet.width() == 72
                assert self.pet.art.expression == "dejected"
                self.pet.toggle_details()
                assert self.pet.details.isVisible()
                assert self.pet.art.expression == "dejected"
                self.pet.details.grab().save(str(self.output / "statistics.png"))
                self.close()

    def closeEvent(self, event):
        self.sample.stop()
        self.delay.stop()
        self.next_timer.stop()
        self.pet.close()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    load_preview_fonts()
    demo = EvolutionDemo(args.output, args.check)
    demo.show()
    app.exec()


if __name__ == "__main__":
    main()
