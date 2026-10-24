"""Installer writes stay in a disposable home and preserve unrelated host/pet state."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install_context_workspace.py"
_SPEC = importlib.util.spec_from_file_location("tomc_workspace_installer_test", _SCRIPT)
installer = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = installer
_SPEC.loader.exec_module(installer)


def _fixture(tmp_path, *, claude=True, pet=True):
    home = tmp_path / "h"
    home.mkdir()
    runtime = tmp_path / "bundle/plugins/tomc-memory"
    package = runtime / "src/tomc"
    package.mkdir(parents=True)
    (runtime / "src/server.py").write_text("# configured server\n", encoding="utf-8")
    server = {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "--locked", "--directory", str(runtime), "src/server.py"],
        "env": {"MUST_NOT_COPY_RUNTIME_ENV": "runtime-value"},
    }
    (runtime / "mcp.json").write_text(
        json.dumps({"mcpServers": {"tomc": server}}), encoding="utf-8"
    )
    for name in installer.PET_MODULES:
        (package / name).write_bytes(f"# updated {name}\nVALUE = '上下文'\n".encode())
    if claude:
        config = {
            "mcpServers": {
                "tomc-memory": {
                    "type": "stdio",
                    "command": "old-uv",
                    "args": ["old"],
                    "env": {"KEEP_SECRET": "do-not-print-me", "TOMC_MEMORY_PATH": "chosen.sqlite3"},
                    "timeout": 5000,
                },
                "other": {"command": "keep-other", "env": {"TOKEN": "keep-me"}},
            },
            "projects": {"project": {"otherData": True}},
            "disabledMcpServers": ["other"],
        }
        (home / ".claude.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(config).encode() + b"\r\n")
    if pet:
        target = home / ".codex/tomc/pet-current/src/tomc"
        target.mkdir(parents=True)
        (target / "usage_widget_qt.py").write_bytes(b"# previous UI\r\n")
        (target / "context_library.py").write_bytes(b"# previous context\r\n")
        (target / "pet_art.py").write_bytes(b"KEEP ANIMATION EXACTLY\x00\xff")
        (target / "data").mkdir()
        (target / "data/tomc-expression-4.png").write_bytes(b"KEEP IMAGE EXACTLY")
        (home / ".codex/tomc/pet.pyw").write_bytes(b"KEEP LAUNCHER EXACTLY")
    return home, runtime


def _files(root):
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_default_dry_run_changes_nothing_and_does_not_print_config(tmp_path, capsys):
    home, runtime = _fixture(tmp_path)
    before = _files(tmp_path)
    assert installer.main(["--home", str(home), "--runtime", str(runtime)]) == 0
    output = capsys.readouterr().out
    assert "dry-run" in output and "No files changed" in output
    assert "do-not-print-me" not in output and "keep-me" not in output
    assert _files(tmp_path) == before


def test_install_preserves_claude_fields_artwork_and_exact_backups(tmp_path, capsys):
    home, runtime = _fixture(tmp_path)
    before = _files(home)
    config_before = json.loads((home / ".claude.json").read_text(encoding="utf-8-sig"))
    result = installer.install(installer.plan_update(home, runtime))
    assert result["status"] == "installed" and not result["processes_restarted"]
    config = json.loads((home / ".claude.json").read_text(encoding="utf-8-sig"))
    actual = config["mcpServers"]["tomc-memory"]
    expected = config_before["mcpServers"]["tomc-memory"]
    assert actual["env"] == expected["env"] and actual["timeout"] == expected["timeout"]
    assert actual["type"] == expected["type"]
    assert actual["command"] == "uv" and actual["args"][-1] == "src/server.py"
    assert config["mcpServers"]["other"] == config_before["mcpServers"]["other"]
    assert config["projects"] == config_before["projects"]
    assert config["disabledMcpServers"] == config_before["disabledMcpServers"]
    assert "MUST_NOT_COPY_RUNTIME_ENV" not in actual["env"]
    archive = Path(result["backup_directory"])
    receipt = json.loads(Path(result["receipt"]).read_text())
    assert "do-not-print-me" not in json.dumps(receipt)
    assert archive.name.startswith("session-update-")
    for change in result["changes"]:
        if change["backup"]:
            assert (archive / change["backup"]).read_bytes() == before[str(Path(change["target"]))]
    for relative, contents in before.items():
        if any(part in relative for part in ["pet_art.py", "tomc-expression-4.png", "pet.pyw"]):
            assert (home / relative).read_bytes() == contents
    for name in installer.PET_MODULES:
        assert (home / ".codex/tomc/pet-current/src/tomc" / name).read_bytes() == (
            runtime / "src/tomc" / name
        ).read_bytes()
    assert not (home / ".codex/plugins/cache").exists()
    assert not (home / ".claude/settings.json").exists()
    assert not (home / ".tomc").exists()
    assert capsys.readouterr().out == ""


def test_missing_existing_tomc_entry_is_skipped_without_duplicate_server(tmp_path):
    home, runtime = _fixture(tmp_path, claude=False)
    original = b'{"mcpServers":{"tomc":{"command":"existing-other-name"}}}\n'
    (home / ".claude.json").write_bytes(original)
    plan = installer.plan_update(home, runtime)
    assert all(change.relative != ".claude.json" for change in plan.changes)
    assert any("no existing top-level" in note for note in plan.notes)
    installer.install(plan)
    assert (home / ".claude.json").read_bytes() == original


def test_legacy_pet_update_can_import_analysis_and_mac_modules_on_windows(tmp_path):
    pytest.importorskip("PySide6")
    home, runtime = _fixture(tmp_path, claude=False)
    pet = home / ".codex/tomc/pet-current/src/tomc"
    package = runtime / "src/tomc"
    source = _SCRIPT.parents[1] / "src/tomc"
    # Model a complete previous installation which lacks the new UI dependencies.
    for target in (package, pet):
        shutil.copytree(
            source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
        )
    added = ("analysis_qt.py", "analysis.py", "categories.py", "macos_ui.py")
    for name in added:
        (pet / name).unlink()
    # An older savings module cannot provide the new report's per-request fields.
    (pet / "savings.py").write_text("# previous savings module\n", encoding="utf-8")
    installer.install(installer.plan_update(home, runtime))
    for name in (*added, "savings.py"):
        assert (pet / name).read_bytes() == (source / name).read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys; import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets; "
            "sys.path.insert(0, sys.argv[1]); sys.platform = 'win32'; "
            "import tomc.analysis_qt, tomc.context_library_qt; "
            "from tomc.macos_ui import install_macos_style, is_macos; "
            "assert not is_macos(); install_macos_style(object()); "
            "assert tomc.analysis_qt.__file__.startswith(sys.argv[1])",
            str(pet.parent),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_missing_hosts_are_skipped_without_installing_a_new_cat(tmp_path):
    home, runtime = _fixture(tmp_path, claude=False, pet=False)
    result = installer.install(installer.plan_update(home, runtime))
    assert result["status"] == "unchanged"
    assert _files(home) == {}


def test_second_install_is_noop_without_another_backup(tmp_path):
    home, runtime = _fixture(tmp_path)
    installer.install(installer.plan_update(home, runtime))
    before = _files(home)
    result = installer.install(installer.plan_update(home, runtime))
    assert result["status"] == "unchanged"
    assert _files(home) == before


@pytest.mark.parametrize(
    "damage", ["missing_module", "syntax", "bad_config", "wrong_directory", "bad_claude"]
)
def test_all_inputs_are_validated_before_changes_or_backup(tmp_path, damage):
    home, runtime = _fixture(tmp_path)
    if damage == "missing_module":
        (runtime / "src/tomc/session_store.py").unlink()
    elif damage == "syntax":
        (runtime / "src/tomc/session_store.py").write_text("not valid python :::", encoding="utf-8")
    elif damage == "bad_config":
        (runtime / "mcp.json").write_text('{"mcpServers":{}}', encoding="utf-8")
    elif damage == "wrong_directory":
        data = json.loads((runtime / "mcp.json").read_text())
        data["mcpServers"]["tomc"]["args"][3] = str(tmp_path / "other")
        (runtime / "mcp.json").write_text(json.dumps(data), encoding="utf-8")
    else:
        (home / ".claude.json").write_bytes(b"not-json-keep-exactly")
    before = _files(home)
    with pytest.raises((ValueError, OSError)):
        installer.plan_update(home, runtime)
    assert _files(home) == before
    assert not (home / ".codex/tomc/archive").exists()


def test_concurrent_change_is_not_overwritten(tmp_path):
    home, runtime = _fixture(tmp_path)
    plan = installer.plan_update(home, runtime)
    (home / ".claude.json").write_bytes(b"concurrent-user-edit")
    before = _files(home)
    with pytest.raises(ValueError, match="changed since validation"):
        installer.install(plan)
    assert _files(home) == before


def test_failed_replacement_restores_prior_bytes(tmp_path, monkeypatch):
    home, runtime = _fixture(tmp_path)
    before = _files(home)
    original = installer._atomic_write
    failed = False

    def fail_one(path, contents):
        nonlocal failed
        if path.name == "session_store.py" and not failed:
            failed = True
            raise OSError("simulated write failure")
        return original(path, contents)

    monkeypatch.setattr(installer, "_atomic_write", fail_one)
    with pytest.raises(RuntimeError, match="rolled_back"):
        installer.install(installer.plan_update(home, runtime))
    for relative, contents in before.items():
        assert (home / relative).read_bytes() == contents
    assert not (home / ".codex/tomc/pet-current/src/tomc/context_library_qt.py").exists()
    receipts = list((home / ".codex/tomc/archive").glob("session-update-*/receipt.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["status"] == "rolled_back"


def test_linked_claude_configuration_is_rejected(tmp_path):
    home, runtime = _fixture(tmp_path, claude=False)
    outside = tmp_path / "outside.json"
    outside.write_text('{"mcpServers":{}}', encoding="utf-8")
    try:
        (home / ".claude.json").symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links.")
    with pytest.raises(ValueError):
        installer.plan_update(home, runtime)
