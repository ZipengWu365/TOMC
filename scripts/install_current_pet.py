"""Install one current pet runtime; redirect old launchers without changing MCP backends."""

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path.home() / ".codex/tomc"
RUNTIME = BASE / "pet-current"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
BACKUP = BASE / "archive" / ("pet-entrypoints-" + STAMP)
UI_MODULES = ("usage_widget.py", "usage_widget_qt.py", "pet_art.py", "pet_growth.py",
              "quota.py", "quota_qt.py", "cost_estimate.py", "oasis_qt.py",
              "pricing_catalog.py", "pricing_qt.py", "model_detection.py", "impact_story.py",
              "ui_language.py")


def backup(path):
    if path.is_file():
        destination = BACKUP / path.relative_to(BASE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def main():
    BACKUP.mkdir(parents=True, exist_ok=False)
    source = ROOT / "src/tomc"
    sys.path.insert(0, str(ROOT / "src"))
    from tomc.model_detection import install_detection
    from tomc.pricing_catalog import sync

    catalog = sync()
    detected, settings = install_detection()
    # A self-contained UI runtime; no dependency on the mutable project checkout.
    shutil.copytree(source, RUNTIME / "src/tomc", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "pocket-*.png",
                                                 "tomc-head-*.png", "plush-cat-head.png"))
    (RUNTIME / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts/desktop_pet_evolution.py", RUNTIME / "scripts")
    for name in ("pet.pyw", "pocket.pyw", "hourglass.pyw"):
        backup(BASE / name)
    shutil.copy2(ROOT / "scripts/pet_launcher.pyw", BASE / "pet.pyw")
    shim = ('"""Compatibility entry: always launch the current TOMC cat head."""\n'
            'import runpy\nfrom pathlib import Path\n'
            'runpy.run_path(str(Path(__file__).parent / "pet.pyw"), run_name="__main__")\n')
    for name in ("pocket.pyw", "hourglass.pyw"):
        (BASE / name).write_text(shim, encoding="utf-8")
    # Old installed Python module entry points also resolve to the same current UI files.
    installed = list(BASE.glob("assistant-preview.*/plugins/tomc-memory/src/tomc"))
    installed += list(BASE.glob("hourglass-*/src/tomc"))
    installed += list(BASE.glob("hourglass-*/plugins/tomc-memory/src/tomc"))
    cache = Path.home() / ".codex/plugins/cache/tomc-local/tomc-memory/0.1.4/src/tomc"
    if cache.exists():
        installed.append(cache)
    for package in installed:
        for name in UI_MODULES:
            target = package / name
            if target.is_relative_to(BASE):
                backup(target)
            elif target.exists():
                archive = BACKUP / "plugin-cache" / name
                archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, archive)
            shutil.copy2(source / name, target)
        (package / "data").mkdir(exist_ok=True)
        shutil.copy2(source / "data/pricing_snapshot.json", package / "data")
        for i in range(1, 5):
            shutil.copy2(source / f"data/tomc-expression-{i}.png", package / "data")
        # -m and console entry points must not mix old core modules with the new GUI.
        entry = package / "usage_widget.py"
        text = entry.read_text("utf-8")
        start, end = text.index("def main():"), text.index('if __name__ == "__main__":')
        delegate = ("def main():\n    import subprocess\n    import sys\n"
                    f"    subprocess.Popen([{str(BASE / 'hourglass-ui/Scripts/pythonw.exe')!r}, "
                    f"{str(BASE / 'pet.pyw')!r}, *sys.argv[1:]])\n\n\n")
        entry.write_text(text[:start] + delegate + text[end:], encoding="utf-8")
    receipt = {"installed_at": STAMP, "runtime": str(RUNTIME), "launcher": str(BASE / "pet.pyw"),
               "legacy_launchers": [str(BASE / n) for n in ("pocket.pyw", "hourglass.pyw")],
               "updated_ui_packages": [str(p) for p in installed], "backup": str(BACKUP),
               "database": str(Path.home() / ".tomc/memory.sqlite3"),
               "host": settings.get("host"), "model": settings.get("model"),
               "model_detection": detected,
               "pricing_sync": {key: {field: value.get(field) for field in
                               ("status", "verified_at", "attempted_at", "source", "error")}
                                for key, value in catalog["providers"].items()},
               "backend_configuration_changed": False,
               "assets": {f"tomc-expression-{i}.png": hashlib.sha256(
                   (source / f"data/tomc-expression-{i}.png").read_bytes()).hexdigest()
                   for i in range(1, 5)}}
    (RUNTIME / "CURRENT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    # Supersede stale discovery markers, preserving their old contents in the receipt directory.
    markers = ("pet_final_path.txt", "cat_release_path.txt", "cat_demo_path.txt")
    for name in markers:
        p = ROOT / "outputs" / name
        if p.exists():
            shutil.copy2(p, BACKUP / name)
        p.write_text(str(RUNTIME) + "\n", encoding="utf-8")
    (RUNTIME / "README.md").write_text(
        "# Current TOMC cat head\n\nOnly the current four-stage cat-head UI is active.\n"
        "Start: `../pet.pyw`; demonstrate all four motions: `../pet.pyw --demo`.\n"
        "Legacy pocket.pyw and hourglass.pyw forward here. Desktop shortcut: TOMC.\n"
        "No body/pocket. Idle dejected; smiles while collecting. Claude quota is not connected.\n"
        "With ~/.tomc/pricing.json configured, the headline shows estimated input dollar value, not billed savings.\n"
        "The first crown milestone plays a virtual desert-to-oasis celebration; no water savings are measured.\n"
        "Demo statistics are isolated. Close the demo to return to live statistics.\n"
        "Older asset folders are historical sources, not current launch targets.\n",
        encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
