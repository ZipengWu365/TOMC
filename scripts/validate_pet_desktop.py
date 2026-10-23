"""Observe the installed native companion against its real request database.

No fake requests or animation triggers. Default window flags remain unchanged;
--discoverable optionally exposes a normal top-level window for accessibility.
Captures contain only this companion's rendered widgets. The caller restores
the normal launcher after this bounded recorder exits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def duration_seconds(value):
    value = int(value)
    if not 30 <= value <= 900:
        raise argparse.ArgumentTypeError("Duration must be 30–900 seconds")
    return value


def write_report(path, report):
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def animation_identity(pet, stage_for_report):
    # A newer request can be preparing while an earlier report is playing.
    # The active report, never the newest request, owns the displayed animation.
    active = pet.active_report or {}
    stage = stage_for_report({"last_preparation": active})
    return {
        "request_id": active.get("request_id") or pet.request_animation_id,
        "context_input_tokens": stage.get("input_tokens"),
        "stage": pet.art.level,
        "expected_stage": stage["level"],
        "length_known": stage.get("length_known", False),
    }


def phase_coverage(phases):
    active = [p for p in phases if isinstance(p, (int, float))]
    return {
        "active_frames": len(active),
        "early": any(p <= 0.15 for p in active),
        "middle": any(0.35 <= p <= 0.65 for p in active),
        "late": any(p >= 0.85 for p in active),
        "idle": None in phases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--store", type=Path, default=Path.home() / ".tomc/memory.sqlite3")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=duration_seconds, default=300)
    parser.add_argument("--discoverable", action="store_true")
    args = parser.parse_args(argv)
    if not args.store.is_file() or not 30 <= args.seconds <= 900:
        parser.error("An existing real database and 30–900 second duration are required")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.runtime.resolve() / "src"))
    from PySide6.QtCore import QLockFile, Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from tomc.pet_growth import growth_state
    from tomc.ui_language import ui_font
    from tomc.usage_widget_qt import Companion

    app = QApplication([])
    if app.platformName() != "windows":
        raise RuntimeError("Desktop acceptance requires the native Windows Qt platform")
    app.setFont(ui_font())
    args.store = args.store.resolve()
    digest = hashlib.sha256(str(args.store).casefold().encode()).hexdigest()[:24]
    lock = QLockFile(str(Path(tempfile.gettempdir()) / f"tomc-pet-{digest}.lock"))
    if not lock.tryLock(0):
        raise RuntimeError("Close the existing companion before desktop acceptance")
    try:
        pet = Companion(args.store, test_mode=False, connect_quota=False)
    except Exception:
        lock.unlock()
        raise
    pet.set_host((pet.pricing or {}).get("host", "claude"))
    if args.discoverable:
        pet.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        pet.setWindowTitle("TOMC Desktop Acceptance")
        pet.details.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        pet.details.setWindowTitle("TOMC Statistics Acceptance")
    started = time.monotonic()
    report = {
        "native_platform": app.platformName(),
        "test_mode": False,
        "synthetic_activity_inserted": False,
        "window_discovery_flag_changed": args.discoverable,
        "events": [],
        "frames": [],
        "languages": [],
        "panels": [],
        "idle_after_animation": False,
        "duration_limit_seconds": args.seconds,
        "exit_reason": "window_closed",
        "capture_errors": [],
        "animations": [],
    }
    last_phase = None
    last_language = None
    previous_capture = 0.0
    current_animation = None

    def save():
        write_report(args.output / "observation.json", report)

    def capture(name, widget=None):
        if (widget or pet).grab().save(str(args.output / name)):
            return True
        report["capture_errors"].append(name)
        return False

    def frame(phase):
        if current_animation is None:
            return
        name = f"animation-{len(report['frames']):04d}.png"
        if capture(name):
            report["frames"].append(
                {
                    **current_animation["identity"],
                    "file": name,
                    "animation_index": current_animation["index"],
                    "phase": phase,
                    "elapsed": time.monotonic() - started,
                    "observed_stage": pet.art.level,
                    "expression": pet.art.expression,
                    "opacity": pet.materialization.opacity(),
                    "window_size": [pet.width(), pet.height()],
                }
            )

    def collect():
        nonlocal current_animation
        identity = animation_identity(pet, growth_state)
        current_animation = {
            "index": len(report["animations"]),
            "identity": identity,
            "completed": False,
        }
        report["animations"].append(current_animation)
        report["events"].append(
            {
                **identity,
                "event": "collect",
                "phase": pet.art.phase,
                "animation_index": current_animation["index"],
                "elapsed": time.monotonic() - started,
            }
        )
        frame(pet.art.phase)
        save()

    def collected():
        if current_animation is not None:
            current_animation["completed"] = True
            report["events"].append(
                {
                    **current_animation["identity"],
                    "event": "collected",
                    "animation_index": current_animation["index"],
                    "terminal_phase": 1.0,
                    "elapsed": time.monotonic() - started,
                }
            )
            frame(None)
            save()

    def guarded(callback):
        def call():
            try:
                callback()
            except Exception as error:
                report.setdefault("callback_errors", []).append(type(error).__name__)
                report["exit_reason"] = "observer_error"
                app.quit()

        return call

    pet.art.collecting.connect(guarded(collect))
    pet.art.collected.connect(guarded(collected))

    def observe():
        nonlocal last_phase, last_language, previous_capture
        elapsed = time.monotonic() - started
        if elapsed >= args.seconds:
            report["exit_reason"] = "duration_limit"
            app.quit()
            return
        phase = pet.art.phase
        language = pet.language.code
        if language != last_language:
            report["languages"].append(language)
            last_language = language
            save()
        if pet.details.isVisible():
            state = "expanded" if pet.details.scope_area.isVisible() else "compact"
            name = f"panel-{language}-{state}.png"
            if name not in report["panels"]:
                if capture(name, pet.details):
                    report["panels"].append(name)
                save()
        if phase is not None and elapsed - previous_capture >= 0.08:
            frame(phase)
            previous_capture = elapsed
            save()
        if last_phase is not None and phase is None:
            report["idle_after_animation"] = True
            report["idle_opacity"] = pet.materialization.opacity()
            capture(f"idle-after-{len(report['events']):02d}.png")
            save()
        last_phase = phase

    timer = QTimer(pet)
    timer.setInterval(40)
    timer.timeout.connect(guarded(observe))
    timer.start()
    pet.show()
    QTimer.singleShot(1000, guarded(lambda: capture("idle-before.png")))

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
        try:
            timer.stop()
            deadline.stop()
            pet.close()
            for animation in report["animations"]:
                animation["coverage"] = phase_coverage(
                    [
                        item["phase"]
                        for item in report["frames"]
                        if item["animation_index"] == animation["index"]
                    ]
                )
            report["animation_observed"] = any(
                item["coverage"]["active_frames"] >= 3 for item in report["animations"]
            )
            report["elapsed_seconds"] = time.monotonic() - started
            save()
        finally:
            lock.unlock()
    return 1 if report.get("callback_errors") or report["capture_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
