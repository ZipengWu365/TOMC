"""UI-only updates include newly imported modules in an isolated existing installation."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("pet_ui_updater_test", SCRIPTS / "update_pet_ui.py")
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


@pytest.mark.parametrize(
    "platform",
    [
        "win32",
        # Faking macOS on another system imports macOS-only modules such as _scproxy.
        pytest.param(
            "darwin",
            marks=pytest.mark.skipif(sys.platform != "darwin", reason="needs a real macOS"),
        ),
    ],
)
def test_ui_update_installs_analysis_dependencies_and_preserves_host_settings(tmp_path, platform):
    pytest.importorskip("PySide6")
    home = tmp_path / "home"
    source = tmp_path / "source"
    pet = home / ".codex/tomc/pet-current/src/tomc"
    for target in (source / "src/tomc", pet):
        shutil.copytree(ROOT / "src/tomc", target, ignore=shutil.ignore_patterns("__pycache__"))
    added = ("analysis_qt.py", "analysis.py", "categories.py", "macos_ui.py")
    for name in added:
        (pet / name).unlink()
    config = home / ".codex/config.toml"
    config.write_text('# Synthetic host configuration\nmodel="fixture"\n', encoding="utf-8")
    previous_config = config.read_bytes()

    plan = updater.plan(home, source)
    assert {Path(change.relative).name for change in plan.changes} == set(added)
    assert all(not (pet / name).exists() for name in added)  # planning is read-only
    updater.install(plan)
    for name in added:
        assert (pet / name).read_bytes() == (source / "src/tomc" / name).read_bytes()
    assert config.read_bytes() == previous_config
    assert updater.plan(home, source).changes == ()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys; import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets; "
            "sys.path.insert(0, sys.argv[1]); sys.platform = sys.argv[2]; "
            "import tomc.analysis_qt, tomc.context_library_qt; "
            "from tomc.macos_ui import is_macos; "
            "assert is_macos() == (sys.argv[2] == 'darwin'); "
            "assert tomc.analysis_qt.__file__.startswith(sys.argv[1])",
            str(pet.parent),
            platform,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
