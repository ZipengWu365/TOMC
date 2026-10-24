"""Exercise read-only app-server allowance access without an inference request."""

import json
import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from tomc.quota_qt import QuotaReader  # noqa: E402

app = QCoreApplication([])
reader = QuotaReader()
result = {"status": "timeout", "windows": []}
reconnect = "--reconnect" in sys.argv
startup_retry = "--startup-retry" in sys.argv
saved_executable = os.environ.get("TOMC_CODEX_PATH")
if startup_retry:
    os.environ["TOMC_CODEX_PATH"] = str(Path(__file__).with_name("missing-codex-for-test.exe"))
phase = 0


def received(state):
    global phase
    if startup_retry and phase == 0 and state["status"] == "unavailable":
        phase = 2
        if saved_executable is None:
            os.environ.pop("TOMC_CODEX_PATH", None)
        else:
            os.environ["TOMC_CODEX_PATH"] = saved_executable
        reader.poll.setInterval(100)
        return
    if reconnect and phase == 0 and state["status"] == "ready":
        phase = 1
        QTimer.singleShot(0, reader.process.kill)  # Terminate only this test's owned helper.
        return
    if reconnect and phase == 1 and state["status"] == "unavailable":
        phase = 2
        reader.poll.setInterval(100)  # Test-only acceleration of the normal 60-second retry.
        return
    if reconnect and phase == 2 and state["status"] != "ready":
        return
    result.update(state)
    result["reconnected_after_helper_exit"] = reconnect and phase == 2
    result["recovered_after_missing_cli"] = startup_retry and phase == 2
    reader.stop()
    app.quit()


reader.updated.connect(received)
QTimer.singleShot(0, reader.start)
QTimer.singleShot(18000, app.quit)
app.exec()
reader.stop()
output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
if result["status"] != "ready":
    raise SystemExit(1)
