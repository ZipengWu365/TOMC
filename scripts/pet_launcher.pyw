"""Single installed entry point, shared by all legacy TOMC desktop shortcuts."""

import json
import os
import runpy
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNTIME = BASE / "pet-current"
sys.path.insert(0, str(RUNTIME / "src"))

from PySide6.QtCore import QLockFile  # noqa: E402

lock = QLockFile(str(Path(tempfile.gettempdir()) / "tomc-current-desktop.lock"))
if not lock.tryLock(0):
    raise SystemExit(0)

demo = "--demo" in sys.argv
try:
    if demo:
        output = BASE / "pet-demos" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        script = RUNTIME / "scripts/desktop_pet_evolution.py"
        sys.argv = [str(script), str(output)]
        runpy.run_path(str(script), run_name="__main__")
    else:
        from tomc.usage_widget import main

        if "--host" not in sys.argv:
            try:
                host = json.loads((Path.home()/".tomc/pricing.json").read_text("utf-8")).get("host", "claude")
            except (OSError, ValueError, AttributeError):
                host = "claude"
            sys.argv.extend(["--host", host if host in ("codex", "claude", "cursor") else "other"])
        if "--state-file" not in sys.argv:
            sys.argv.extend(["--state-file", str(BASE / "pet-current-state.json")])
        main()
finally:
    lock.unlock()

if demo and not os.environ.get("TOMC_NO_RESTORE_AFTER_DEMO"):
    subprocess.Popen([sys.executable, str(BASE / "pet.pyw")], cwd=BASE)
