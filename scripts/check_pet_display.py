"""Offscreen app rendering and internal Qt events; never captures/controls the desktop.

Run with the optional Qt environment. Two real MCP calls use the installed config
and an isolated database. Later evolution/error cases are clearly synthetic.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "2"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc.pet_growth import STAGES, growth_state  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


def check(config, output, client_python):
    output.mkdir(parents=True, exist_ok=True)
    db = output / "widget_test.sqlite3"
    if db.exists():
        raise ValueError("Use a fresh output folder; never overwrite a previous test database.")
    app = QApplication([])
    load_preview_fonts()
    widget = Companion(db, test_mode=True, state_file=output / "widget_state.json")
    widget.show()
    app.processEvents()
    assert widget.summary["preparations"] == 0
    assert widget.materialization.opacity() == 0.35
    assert not widget.card.isVisible()
    widget.grab().save(str(output / "empty.png"))
    for batch in (1, 2):
        subprocess.run(
            [str(client_python), str(ROOT / "scripts/check_installed_usage.py"),
             str(config), str(output), str(batch)], check=True,
            stdout=subprocess.DEVNULL,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        # Let the actual polling timer observe the new numeric data.
        QTest.qWait(1200)
        assert widget.art.animation_timer.isActive() or widget.pending_reports
        widget.grab().save(str(output / f"collect_call_{batch}.png"))
        QTest.qWait(4200)
        receipt = json.loads((output / f"installed_call_{batch}.json").read_text("utf-8"))
        assert widget.summary == receipt["after"]
        assert widget.card.isVisible()
        reduced = receipt["per_call"]
        expected_percent = 100*(reduced["input_tokens"]-reduced["memory_tokens"])/reduced["input_tokens"]
        assert widget.number.text() == f"{abs(expected_percent):.1f}%"
        widget.grab().save(str(output / f"compact_call_{batch}.png"))
    # These events are delivered directly to this offscreen widget, never the OS input stream.
    QTest.mouseClick(widget.card, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert widget.details.isVisible()
    for period in ("today", "7d", "all"):
        QTest.mouseClick(widget.details.buttons[period], Qt.MouseButton.LeftButton)
        app.processEvents()
        assert widget.period == period and widget.details.buttons[period].isChecked()
        assert widget.summary["preparations"] == 2
    widget.details.grab().save(str(output / "details.png"))
    widget.details.hide()
    QTest.qWait(6200)
    assert not widget.card.isVisible()
    widget.timer.stop()
    widget.report_timer.stop()
    widget.hide_report()
    assert not widget.card.isVisible() and widget.width() == 72

    board = QPixmap(1120, 590)
    board.fill(QColor("#F4F3EF"))
    painter = QPainter(board)
    painter.setFont(QFont("Microsoft YaHei UI", 14))
    painter.setPen(QColor("#443B35"))
    painter.drawText(30, 35, "进化预览 · 独立模拟数据 · 应用自身离屏渲染")
    for index, (threshold, name, _) in enumerate(STAGES):
        stage_db = output / f"stage_{index+1}.sqlite3"
        store = UsageStore(stage_db)
        store.record({"counter": "lexical", "usable": True, "input_tokens": threshold+100,
                      "memory_tokens": 100, "reduced_tokens": threshold})
        widget.store, widget.last_signature = store, None
        widget.last_level = None
        widget.initialized = False
        widget.refresh()
        app.processEvents()
        assert growth_state(widget.summary)["level"] == index+1
        rendered = widget.grab()
        rendered.save(str(output / f"stage_{index+1}.png"))
        x, y = 20 + (index % 2)*550, 55 + (index // 2)*260
        painter.drawPixmap(x+100, y, 180, 201, rendered)
        painter.drawText(x+20, y+225, f"{name} · {threshold:,} · 凝实度 {widget.materialization.opacity():.0%}")
    painter.end()
    board.save(str(output / "evolution_preview.png"))
    # Render four different choreographies from the SAME production painting code.
    frames = output / "animation_frames"
    frames.mkdir()
    widget.art.animation_timer.stop()
    for frame in range(41):
        sheet = QPixmap(1040, 310)
        sheet.fill(QColor("#F4F3EF"))
        painter = QPainter(sheet)
        painter.setPen(QColor("#443B35"))
        painter.setFont(QFont("Microsoft YaHei UI", 11))
        painter.drawText(20, 24, "上下文入袋 · 四阶段动画预览（模拟，不计入统计）")
        for i, (threshold, name, _) in enumerate(STAGES):
            state = growth_state({"growth": [{"peak_net_tokens": threshold, "net_tokens": threshold}]})
            widget.art.set_state(state)
            widget.materialization.setOpacity(state["opacity"])
            widget.art.phase = frame/40 if frame < 40 else None
            widget.art.update()
            rendered = widget.grab()
            painter.drawPixmap(30+i*255, 40, 180, 201, rendered)
            painter.drawText(30+i*255, 268, name)
        painter.end()
        sheet.save(str(frames / f"frame_{frame:03}.png"))
    widget.art.phase = None
    broken = output / "broken.sqlite3"
    broken.write_text("invalid database", encoding="utf-8")
    widget.store, widget.last_signature = UsageStore(broken), None
    widget.refresh()
    assert widget.error == "read_failed" and widget.number.text() == "暂不可读"
    widget.grab().save(str(output / "error.png"))
    widget.store, widget.last_signature = UsageStore(db), None
    widget.refresh()
    assert not widget.error and widget.summary["preparations"] == 2
    widget.close()
    (output / "validation.json").write_text(json.dumps({
        "mode": "offscreen application render; no desktop screenshot or OS input",
        "installed_mcp_calls": 2, "period_buttons": ["today", "7d", "all"],
        "four_forms_rendered": True, "error_recovery": True,
        "completion_animation_then_bubble": True, "bubble_auto_hides": True,
        "four_animation_frame_sequences": True,
        "actual_desktop_interaction": "not automated; user requested no Computer Use",
        "test_database": str(db), "production_database_written": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pet display checks passed: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("client_python", type=Path)
    args = parser.parse_args()
    check(args.config, args.output, args.client_python)
