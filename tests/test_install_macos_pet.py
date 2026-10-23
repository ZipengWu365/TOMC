"""A native launcher must preserve existing apps and never need demo/user data."""

import importlib.util
import json
import os
import plistlib
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install_macos_pet.py"
_SPEC = importlib.util.spec_from_file_location("macos_pet_installer_test", _SCRIPT)
installer = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = installer
_SPEC.loader.exec_module(installer)


def existing_app(path, bundle_id=None):
    contents = path / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps({"CFBundleIdentifier": bundle_id or installer.BUNDLE_ID})
    )
    (contents / "old-app").write_bytes(b"keep previous app exactly\x00\xff")


def files(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


@pytest.fixture
def fake_build(monkeypatch):
    monkeypatch.setattr(installer, "discover_runtime", lambda: object())

    def build(app, runtime):
        contents = app / "Contents"
        contents.mkdir(parents=True)
        (contents / "Info.plist").write_bytes(
            plistlib.dumps({"CFBundleIdentifier": installer.BUNDLE_ID})
        )
        (contents / "new-app").write_bytes(b"new launcher")
        return {"environment": "/env", "source": "/source"}

    monkeypatch.setattr(installer, "build_bundle", build)


@pytest.mark.parametrize("kind", ["other_app", "file", "invalid_plist", "symlink"])
def test_unrelated_destination_is_preserved_before_dependency_checks(tmp_path, monkeypatch, kind):
    output = tmp_path / "TOMC.app"
    if kind == "other_app":
        existing_app(output, "org.other.product")
    elif kind == "file":
        output.write_bytes(b"unrelated file")
    elif kind == "invalid_plist":
        existing_app(output)
        (output / "Contents/Info.plist").write_bytes(b"invalid plist")
    else:
        actual = tmp_path / "actual.app"
        existing_app(actual)
        output.symlink_to(actual)
    before = files(tmp_path)
    monkeypatch.setattr(
        installer, "discover_runtime", lambda: pytest.fail("Must refuse before checking runtime")
    )
    with pytest.raises(ValueError, match="Refusing|symbolic link"):
        installer.install(output, replace=True)
    assert files(tmp_path) == before


def test_existing_tomc_requires_explicit_replace(tmp_path, fake_build):
    output = tmp_path / "TOMC.app"
    existing_app(output)
    before = files(tmp_path)
    with pytest.raises(ValueError, match="--replace"):
        installer.install(output)
    assert files(tmp_path) == before


def test_update_retains_exact_previous_app_and_has_no_configuration_side_effects(
    tmp_path, fake_build
):
    output = tmp_path / "Applications/TOMC.app"
    existing_app(output)
    previous = files(output)
    protected = tmp_path / ".tomc"
    protected.mkdir()
    (protected / "memory.sqlite3").write_bytes(b"existing user database")
    (protected / "ui_settings.json").write_bytes(b'{"language":"zh"}')
    before = files(protected)
    result = installer.install(output, replace=True)
    backup = Path(result["backup"])
    assert backup.parent == output.parent
    assert files(backup) == previous
    assert (output / "Contents/new-app").read_bytes() == b"new launcher"
    assert files(protected) == before
    assert not list(tmp_path.rglob(".tomc-app-build-*"))
    assert not (tmp_path / "Library/LaunchAgents").exists()


def test_failed_build_never_replaces_existing_app(tmp_path, fake_build, monkeypatch):
    output = tmp_path / "TOMC.app"
    existing_app(output)
    before = files(tmp_path)

    def fail(app, runtime):
        app.mkdir()
        raise ValueError("native runtime check failed")

    monkeypatch.setattr(installer, "build_bundle", fail)
    with pytest.raises(ValueError, match="native runtime check"):
        installer.install(output, replace=True)
    assert files(tmp_path) == before
    assert not list(tmp_path.glob(".tomc-app-build-*"))


def test_failed_publish_restores_previous_app(tmp_path, fake_build, monkeypatch):
    output = tmp_path / "TOMC.app"
    existing_app(output)
    before = files(tmp_path)
    rename = installer.os.rename

    def fail_publish(source, destination):
        if Path(source).parent.name.startswith(".tomc-app-build-"):
            raise OSError("simulated publish failure")
        rename(source, destination)

    monkeypatch.setattr(installer.os, "rename", fail_publish)
    with pytest.raises(OSError, match="publish failure"):
        installer.install(output, replace=True)
    assert files(tmp_path) == before


def test_new_destination_appearing_during_build_is_not_replaced(tmp_path, fake_build, monkeypatch):
    output = tmp_path / "TOMC.app"
    build = installer.build_bundle

    def race(app, runtime):
        result = build(app, runtime)
        existing_app(output)
        return result

    monkeypatch.setattr(installer, "build_bundle", race)
    with pytest.raises(ValueError, match="destination changed"):
        installer.install(output, replace=True)
    assert (output / "Contents/old-app").exists()
    assert not (output / "Contents/new-app").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS native launcher integration")
def test_native_bundle_runs_isolated_runtime_check_without_writing_user_data(tmp_path):
    pytest.importorskip("PySide6")
    pytest.importorskip("shiboken6")
    clang = shutil.which("clang")
    if not clang or subprocess.run([clang, "--version"], capture_output=True).returncode:
        pytest.skip("Native launcher integration requires a working clang compiler")
    if not (Path(sysconfig.get_path("include")) / "Python.h").is_file():
        pytest.skip("Native launcher integration requires Python development headers")
    library_dir = sysconfig.get_config_var("LIBDIR")
    library_name = sysconfig.get_config_var("LDLIBRARY")
    if not library_dir or not library_name:
        pytest.skip("Native launcher integration requires a shared Python library")
    library = Path(library_dir) / library_name
    if not library.is_file() or library.suffix not in {".dylib", ""}:
        pytest.skip("Native launcher integration requires a shared Python dylib/framework")
    output = tmp_path / "Apps with ' quotes 目录 🍀/TOMC.app"
    user_home = tmp_path / "empty-home"
    user_home.mkdir()
    result = installer.install(output)
    assert result["backup"] is None
    executable = output / "Contents/MacOS/TOMC"
    info = plistlib.loads((output / "Contents/Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == installer.BUNDLE_ID
    assert info["LSUIElement"] is True
    # Finder has no active venv or dependable shell PATH. Embedded Python should
    # still find exactly the validated runtime and ignore an injected PYTHONPATH.
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "tomc.py").write_text("raise RuntimeError('wrong package loaded')\n")
    checked = subprocess.run(
        [str(executable), installer.CHECK_ARGUMENT],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(poison),
            "TOMC_MEMORY_PATH": str(user_home / "memory.sqlite3"),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    status = json.loads(checked.stdout)
    assert status["status"] == "ok"
    assert Path(status["source"]) == installer.ROOT / "src/tomc/usage_widget_qt.py"
    assert files(user_home) == {}
    assert "not a standalone distribution" in (output / "Contents/Resources/README.txt").read_text()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS dependency checks")
def test_missing_compiler_is_reported_before_creating_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.shutil, "which", lambda name: None)
    output = tmp_path / "not-created/TOMC.app"
    with pytest.raises(ValueError, match="clang"):
        installer.install(output)
    assert not output.parent.exists()
