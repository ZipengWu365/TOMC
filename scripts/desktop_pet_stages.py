"""Native four-stage design player. No desktop capture, OS input, or production DB access."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

if "--check" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer, Signal  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from tomc.pet_art import PetArt  # noqa: E402
from tomc.pet_growth import STAGES, request_stage  # noqa: E402
from tomc.usage_widget_qt import STYLE, load_preview_fonts  # noqa: E402


class ClickCat(PetArt):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class StagePlayer(QWidget):
    def __init__(self, output, check=False):
        super().__init__()
        self.output, self.check = output, check
        self.setWindowTitle("TOMC · 省 token 小猫 · 四阶段演示")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, sys.platform != "darwin")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, sys.platform != "darwin")
        self.setStyleSheet(STYLE + "QWidget#stagePlayer { background: #F7F4ED; }")
        self.setObjectName("stagePlayer")
        self.setFixedSize(900, 530)
        self.played, self.automatic, self.current = [], False, 0
        self.next_timer = QTimer(self)
        self.next_timer.setSingleShot(True)
        self.next_timer.timeout.connect(self.next_stage)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        title = QLabel("TOMC · 四阶猫头")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel("从轻绒虚影到蓬密实体 / 黄毛只在究极阶段出现    ·    演示数字不计入真实统计")
        )
        self.status = QLabel("即将依次演示四种收上下文动作。点击任意小猫查看该阶段输入长度。")
        self.status.setStyleSheet("color: #507461; padding-top: 6px;")
        layout.addWidget(self.status)
        cards = QHBoxLayout()
        self.arts, self.cards, self.reports = [], [], []
        motions = ("纸片摇晃飘落", "三次撞击 · 锻造小卡片", "两侧吸入嘴巴", "旋流吸入嘴巴")
        for i, (threshold, name, _) in enumerate(STAGES):
            frame = QFrame()
            frame.setObjectName(f"stage{i}")
            frame.setStyleSheet(
                f"QFrame#stage{i} {{ background: #FFFCF6; border: 1px solid #E4DDCF; border-radius: 16px; }}"
            )
            col = QVBoxLayout(frame)
            col.setContentsMargins(9, 12, 9, 10)
            label = QLabel(f"{i + 1}  {name}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 14px; font-weight: 600;")
            col.addWidget(label)
            art = ClickCat()
            art.setFixedSize(186, 207)
            state = request_stage(max(1, threshold))
            art.set_state(state)
            opacity = QGraphicsOpacityEffect(art)
            opacity.setOpacity(state["opacity"])
            art.setGraphicsEffect(opacity)
            art.clicked.connect(lambda n=i: self.show_stats(n))
            art.collected.connect(lambda n=i: self.finished(n))
            col.addWidget(art, alignment=Qt.AlignmentFlag.AlignCenter)
            desc = QLabel(motions[i])
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setStyleSheet("color: #74685D; font-size: 11px;")
            col.addWidget(desc)
            report = QLabel(f"凝实度 {state['opacity']:.0%}")
            report.setAlignment(Qt.AlignmentFlag.AlignCenter)
            report.setStyleSheet("font-size: 10px; color: #74685D;")
            col.addWidget(report)
            replay = QPushButton("播放这个阶段")
            replay.clicked.connect(lambda checked=False, n=i: self.play(n, manual=True))
            col.addWidget(replay)
            cards.addWidget(frame)
            self.arts.append(art)
            self.cards.append(frame)
            self.reports.append(report)
        layout.addLayout(cards)
        self.stats = QLabel("点击小猫查看示例输入长度；重播动画不会增加任何统计。")
        self.stats.setStyleSheet(
            "background: #EAF0E6; border-radius: 10px; padding: 10px; color: #345743;"
        )
        self.stats.setMinimumHeight(52)
        layout.addWidget(self.stats)
        controls = QHBoxLayout()
        restart = QPushButton("从头演示四阶段")
        restart.clicked.connect(self.start_all)
        pause = QPushButton("暂停自动演示")
        pause.clicked.connect(self.pause)
        close = QPushButton("关闭演示")
        close.clicked.connect(self.close)
        for button in (restart, pause, close):
            controls.addWidget(button)
        layout.addLayout(controls)
        QTimer.singleShot(600 if check else 2200, self.start_all)

    def record(self, phase):
        (self.output / "player_state.json").write_text(
            json.dumps(
                {
                    "phase": phase,
                    "current_stage": self.current + 1,
                    "completed_stages": self.played,
                    "desktop_control_used": False,
                    "production_database_opened": False,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def pause(self):
        self.automatic = False
        self.next_timer.stop()
        self.status.setText("已暂停自动演示；可点击任意阶段单独播放。")

    def start_all(self):
        self.next_timer.stop()
        self.played = []
        self.automatic = True
        self.play(0)

    def play(self, index, manual=False):
        if manual:
            self.automatic = False
            self.next_timer.stop()
        self.current = index
        for i, art in enumerate(self.arts):
            art.animation_timer.stop()
            art.phase = None
            art.update()
            color = "#8DA58B" if i == index else "#E4DDCF"
            self.cards[i].setStyleSheet(
                f"QFrame#stage{i} {{ background: #FFFCF6; border: 1px solid {color}; border-radius: 16px; }}"
            )
        self.status.setText(f"正在演示 {index + 1}/4：{STAGES[index][1]} 收上下文……")
        self.arts[index].collect()
        self.record("collecting")

    def finished(self, index):
        if index + 1 not in self.played:
            self.played.append(index + 1)
        self.reports[index].setText("动画完成 · 未写入真实统计")
        self.show_stats(index)
        self.status.setText(f"第 {index + 1} 阶段：吃纸片动画完成。")
        self.record("stage_complete")
        if self.automatic:
            self.next_timer.start(800 if self.check else 2000)

    def next_stage(self):
        if self.current < 3:
            self.play(self.current + 1)
        else:
            self.automatic = False
            self.status.setText("四阶段演示完毕。可单独重播、查看输入长度，或从头再看一遍。")
            self.record("all_stages_complete")
            if self.check:
                self.grab().save(str(self.output / "four_stages.png"))
                self.close()

    def show_stats(self, index):
        threshold = STAGES[index][0]
        self.stats.setText(
            f"素材预览 · 第 {index + 1} 阶段    示例输入 {max(1, threshold):,} 估算 tokens\n"
            "这里只播放动作，不执行压缩、不写统计，也不代表真实聊天已经接入。"
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--check", action="store_true")
    p.add_argument("--restore-launcher", type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    load_preview_fonts()
    window = StagePlayer(args.output, args.check)
    area = app.primaryScreen().availableGeometry()
    window.move(area.center() - window.rect().center())
    window.show()
    if sys.platform == "darwin":
        window.raise_()
        window.activateWindow()
    app.exec()
    if args.restore_launcher and not args.check:
        subprocess.Popen(
            [sys.executable, str(args.restore_launcher)], cwd=str(args.restore_launcher.parent)
        )


if __name__ == "__main__":
    main()
