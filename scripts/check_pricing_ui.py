"""Local widget integration: no screen capture, OS input or production statistics."""

import json
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

import tomc.usage_widget_qt as ui  # noqa: E402
from tomc.cost_estimate import load_pricing  # noqa: E402
from tomc.pricing_qt import ReferenceSheet  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
config = out / "pricing.json"
config.write_text(
    json.dumps({"provider": "anthropic", "model": "claude-opus-5-5", "variant": "standard"})
)
ui.load_pricing = lambda: load_pricing(config)
app = QApplication([])
ui.load_preview_fonts()
store = UsageStore(out / "test.sqlite3")
store.record(
    {
        "counter": "demo-estimate",
        "usable": True,
        "input_tokens": 100_000,
        "memory_tokens": 0,
        "reduced_tokens": 100_000,
    }
)
# Checks compare Chinese text; the preference file lives in the isolated output folder.
UiLanguage(store.path).set_language("zh")
pet = ui.Companion(store.path, test_mode=True, connect_quota=False)
pet.show()
pet.toggle_details()
app.processEvents()
assert pet.details.money.text() == "$0.40"
assert pet.details.width() == 300
pet.details.grab().save(str(out / "compact.png"))
sheet = ReferenceSheet(pet, config)
pet.reference_sheet = sheet
sheet.open_tab()
app.processEvents()
sheet.grab().save(str(out / "pricing.png"))
sheet.host.setCurrentIndex(sheet.host.findData("cursor"))
sheet.provider.setCurrentIndex(sheet.provider.findData("cursor"))
sheet.models.setCurrentIndex(sheet.models.findData("cursor:composer-2-5:listed"))
sheet.save()
assert pet.details.money.text() == "$0.05"
sheet.mode.setCurrentIndex(sheet.mode.findData("cached"))
sheet.save()
assert pet.details.money.text() == "$0.02"
sheet.models.setCurrentIndex(0)
sheet.save()
assert pet.details.money.text() == "—"
assert "选择参考模型" in pet.details.basis.text()
sheet.provider.setCurrentIndex(sheet.provider.findData("openai"))
sheet.models.setCurrentIndex(sheet.models.findData("openai:gpt-6-astra:standard-short"))
sheet.mode.setCurrentIndex(0)
sheet.save()
assert pet.details.money.text() == "$1.00"
sheet.open_tab(1)
app.processEvents()
assert "没有测量" in sheet.story.toPlainText()
sheet.grab().save(str(out / "story.png"))
pet.close()
(out / "validation.json").write_text(
    json.dumps(
        {
            "switch_model": True,
            "cached_rate": True,
            "unknown_model_unpriced": True,
            "compact_panel_width": 300,
            "production_statistics_written": False,
            "desktop_control": False,
        },
        indent=2,
    )
)
print(f"Pricing UI checks passed: {out}")
