"""Smoke checks must not silently move downloads into a user's home directory."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def smoke_module():
    spec = importlib.util.spec_from_file_location("plugin_smoke", ROOT / "scripts/plugin_smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runtime_downloads_default_to_disposable_smoke_root(tmp_path, monkeypatch):
    for name in ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR", "UV_PYTHON"):
        monkeypatch.delenv(name, raising=False)
    env = smoke_module().runtime_environment(tmp_path, tmp_path / "memory.sqlite3")
    assert Path(env["UV_CACHE_DIR"]).is_relative_to(tmp_path)
    assert Path(env["UV_PYTHON_INSTALL_DIR"]).is_relative_to(tmp_path)
    assert not Path(env["UV_CACHE_DIR"]).exists()
    assert env["TOMC_MEMORY_PATH"] == str(tmp_path / "memory.sqlite3")


def test_runtime_preserves_explicit_paths_without_inheriting_unrelated_environment(
    tmp_path, monkeypatch
):
    overrides = {
        "UV_CACHE_DIR": str(tmp_path / "existing uv cache"),
        "UV_PYTHON_INSTALL_DIR": str(tmp_path / "Python 环境"),
        "UV_PYTHON": str(tmp_path / "Python 环境" / "python"),
    }
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("TOMC_MEMORY_PATH", "caller-notebooks.sqlite3")
    monkeypatch.setenv("UNRELATED_ENV_VAR", "not-for-mcp")
    monkeypatch.setenv("UV_INDEX_URL", "not-for-mcp")
    env = smoke_module().runtime_environment(tmp_path, tmp_path / "smoke.sqlite3")
    assert env == {**overrides, "TOMC_MEMORY_PATH": str(tmp_path / "smoke.sqlite3")}


def test_runtime_resolves_relative_directories_before_changing_working_directory(
    tmp_path, monkeypatch
):
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    monkeypatch.setenv("UV_CACHE_DIR", "cache")
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", "Python 环境")
    monkeypatch.setenv("UV_PYTHON", "3.12")
    root = tmp_path / "disposable smoke root"
    env = smoke_module().runtime_environment(root, root / "memory.sqlite3")
    assert env["UV_CACHE_DIR"] == str(caller / "cache")
    assert env["UV_PYTHON_INSTALL_DIR"] == str(caller / "Python 环境")
    assert env["UV_PYTHON"] == "3.12"
