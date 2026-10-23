"""Native four-stage visual review using installed art, without any usage writes."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from validate_pet_desktop import duration_seconds, phase_coverage, write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=duration_seconds, default=300)
    parser.add_argument("--auto-play", action="store_true",
                        help="Play the isolated preview once without mouse/keyboard input")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.runtime.resolve() / "src"))
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    from tomc.pet_art import PetArt
    from tomc.pet_growth import STAGES, request_stage
    from tomc.ui_language import ui_font

    app = QApplication([])
    if app.platformName() != "windows":
        raise RuntimeError("This visual review requires the native Windows platform")
    app.setFont(ui_font())
    window = QWidget()
    window.setWindowTitle("TOMC Four-stage Animation Review")
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    window.setStyleSheet("QWidget { background: #FFFCF7; color: #443B35; }"
                        "QPushButton { padding: 10px; background: #E4ECE5; border-radius: 8px; }")
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Four original animation stages / 四阶段动画验收"))
    layout.addWidget(QLabel("Animation preview only · no production usage or chat records are written"))
    row = QHBoxLayout()
    arts = []
    for number, (threshold, _, _) in enumerate(STAGES, 1):
        column = QVBoxLayout()
        title = QLabel(f"Stage {number} · {threshold:,}+")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(title)
        art = PetArt(window)
        art.setFixedSize(160, 178)
        art.set_state(request_stage(max(1, threshold), "en"))
        column.addWidget(art)
        arts.append(art)
        row.addLayout(column)
    layout.addLayout(row)
    play = QPushButton("Play all four stages / 播放四阶段")
    layout.addWidget(play)
    report = {"native_platform": app.platformName(), "production_database_written": False,
              "preview_only": True, "frames": [], "completed": [], "events": [],
              "runs": [], "capture_errors": [], "duration_limit_seconds": args.seconds,
              "exit_reason": "window_closed",
              "automatic_preview": args.auto_play,
              "stage_inputs": [max(1, item[0]) for item in STAGES]}
    started = time.monotonic()
    current_run = None
    timer = QTimer(window)
    timer.setInterval(100)

    def save():
        write_report(args.output / "stages.json", report)

    def guarded(callback):
        def call():
            try:
                callback()
            except Exception as error:
                report.setdefault("callback_errors", []).append(type(error).__name__)
                report["exit_reason"] = "observer_error"
                app.quit()
        return call

    def event(kind, index):
        if current_run is not None:
            report["events"].append({"event": kind, "stage": index + 1,
                                     "context_input_tokens": report["stage_inputs"][index],
                                     "run": current_run["index"],
                                     "phase": 0.0 if kind == "collect" else 1.0,
                                     "elapsed": time.monotonic() - started})
            if kind == "collected":
                current_run["completed"].append(index + 1)
            save()

    for index, art in enumerate(arts):
        art.collecting.connect(guarded(lambda i=index: event("collect", i)))
        art.collected.connect(guarded(lambda i=index: event("collected", i)))

    def frame():
        name = f"stages-{len(report['frames']):03d}.png"
        if window.grab().save(str(args.output / name)):
            report["frames"].append({"file": name, "phases": [art.phase for art in arts],
                                     "run": current_run["index"], "elapsed": time.monotonic() - started,
                                     "stages": [art.level for art in arts],
                                     "context_input_tokens": report["stage_inputs"],
                                     "expressions": [art.expression for art in arts]})
        else:
            report["capture_errors"].append(name)
        save()
        if set(current_run["completed"]) == {1, 2, 3, 4} and all(art.phase is None for art in arts):
            timer.stop()
            report["completed"] = sorted(set(current_run["completed"]))
            current_run["finished"] = True
            save()
            play.setEnabled(True)

    def start():
        nonlocal current_run
        current_run = {"index": len(report["runs"]), "completed": [], "finished": False}
        report["runs"].append(current_run)
        play.setEnabled(False)
        for art in arts:
            art.collect()
        frame()  # Record phase zero before the first 100 ms sampling interval.
        timer.start()

    timer.timeout.connect(guarded(frame))
    play.clicked.connect(guarded(start))
    window.show()
    QTimer.singleShot(500, lambda: window.grab().save(str(args.output / "idle-all-four.png")))
    if args.auto_play:
        QTimer.singleShot(1000, guarded(start))
    def timeout():
        report["exit_reason"] = "duration_limit"
        app.quit()

    deadline = QTimer(app)
    deadline.setSingleShot(True)
    deadline.timeout.connect(timeout)
    deadline.start(args.seconds * 1000)
    try:
        save()
        app.exec()
    finally:
        timer.stop()
        deadline.stop()
        for art in arts:
            art.animation_timer.stop()
        window.close()
        for run in report["runs"]:
            frames = [item for item in report["frames"] if item["run"] == run["index"]]
            run["stage_coverage"] = [phase_coverage([item["phases"][i] for item in frames]) for i in range(4)]
        report["all_four_stages_observed"] = any(run["finished"] and all(
            item["early"] and item["middle"] and item["late"] and item["idle"]
            for item in run["stage_coverage"]) for run in report["runs"])
        report["elapsed_seconds"] = time.monotonic() - started
        save()
    return 1 if report.get("callback_errors") or report["capture_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
