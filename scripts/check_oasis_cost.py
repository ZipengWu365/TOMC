"""Exercise cost scope and the one-time crown transition using own offscreen Qt widgets."""

import json
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import tomc.usage_widget_qt as ui  # noqa: E402
from tomc.pricing_catalog import all_rates  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
app = QApplication([])
ui.load_preview_fonts()
ui.load_pricing = lambda: {
    "model": "claude-opus-5-5",
    "mode": "input",
    "rate": 4.0,
    **next(
        r for r in all_rates() if r["provider"] == "anthropic" and r["model"] == "claude-opus-5-5"
    ),
}
store = UsageStore(out / "test.sqlite3")
store.record(
    {
        "counter": "demo-estimate",
        "usable": True,
        "input_tokens": 900,
        "memory_tokens": 252,
        "reduced_tokens": 648,
    }
)
pet = ui.Companion(store.path, test_mode=True, connect_quota=False)
pet.show()
pet.toggle_details()
app.processEvents()
assert pet.details.total.text() == "$0.0026"
assert pet.details.width() == 240
pet.details.grab().save(str(out / "money.png"))
pet.details.hide()
# A real statistics transition unlocks the celebration. No production DB is touched.
store.record(
    {
        "counter": "demo-estimate",
        "usable": True,
        "input_tokens": 1_000_000,
        "memory_tokens": 100,
        "reduced_tokens": 999_900,
    }
)
QTest.qWait(4600)
assert pet.oasis.isVisible()
assert not pet.pending_victory
assert pet.details.total.text() == "$4.00"
pet.oasis.timer.stop()
for t, name in ((0.1, "desert"), (0.4, "growing"), (0.80, "oasis")):
    pet.oasis.phase = t
    pet.oasis.update()
    app.processEvents()
    pet.oasis.grab().save(str(out / f"{name}.png"))
QTest.mouseClick(pet.oasis, Qt.MouseButton.LeftButton)
assert not pet.oasis.isVisible() and not pet.oasis.timer.isActive()
pet.oasis.start()
QTest.qWait(pet.oasis.DURATION + 200)
assert not pet.oasis.isVisible() and not pet.oasis.timer.isActive()
# A further preparation at the same crown stage must not replay the milestone.
pet.hide_report()
store.record(
    {
        "counter": "demo-estimate",
        "usable": True,
        "input_tokens": 100,
        "memory_tokens": 90,
        "reduced_tokens": 10,
    }
)
QTest.qWait(4600)
assert not pet.oasis.isVisible()
pet.close()
(out / "validation.json").write_text(
    json.dumps(
        {
            "signed_cost_math_tested_separately": True,
            "panel_width": 240,
            "crown_threshold_celebration": True,
            "automatic_dismiss": True,
            "click_dismiss": True,
            "no_replay_on_later_crown_calls": True,
            "desktop_control_used": False,
            "production_database_written": False,
            "water_savings_claimed": False,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Cost and oasis checks passed: {out}")
