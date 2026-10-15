"""Install preflight must fail before changing a user's plugin configuration."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installer(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "tomc_installer", ROOT / "plugins/codex/install.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = tmp_path / "TOMC 安装 package"
    for name in (
        ".agents/plugins/marketplace.json",
        "plugins/tomc-memory/.codex-plugin/plugin.json",
        "plugins/tomc-memory/skills/tomc-memory/SKILL.md",
        "plugins/tomc-memory/src/server.py",
        "plugins/tomc-memory/pyproject.toml",
        "plugins/tomc-memory/uv.lock",
    ):
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "__file__", str(package / "install.py"))
    monkeypatch.setenv("PATH", "")
    uv = tmp_path / ("UV 环境.exe" if os.name == "nt" else "UV 环境")
    codex = tmp_path / ("Codex CLI.exe" if os.name == "nt" else "Codex CLI")
    for tool in (uv, codex):
        tool.write_text("test executable", encoding="utf-8")
        tool.chmod(0o755)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="supported", stderr="")

    monkeypatch.setattr(module.subprocess, "run", run)
    return module, package, uv, codex, calls


def test_check_leaves_existing_configuration_and_store_untouched(installer, tmp_path):
    module, package, uv, codex, calls = installer
    config = package / "plugins/tomc-memory/mcp.json"
    config.write_text('{"existing": true}\n', encoding="utf-8")
    store = tmp_path / "试用 notebooks" / "memory.sqlite3"
    assert (
        module.main(["--check", "--uv", str(uv), "--codex", str(codex), "--store", str(store)]) == 0
    )
    assert config.read_text(encoding="utf-8") == '{"existing": true}\n'
    assert not store.parent.exists()
    assert calls == [
        [str(uv), "--version"],
        [str(codex), "plugin", "marketplace", "add", "--help"],
        [str(codex), "plugin", "add", "--help"],
    ]


def test_explicit_tools_install_without_path_and_preserve_unicode_arguments(installer, tmp_path):
    module, package, uv, codex, calls = installer
    store = tmp_path / "独立 notebooks" / "memory.sqlite3"
    assert module.main(["--uv", str(uv), "--codex", str(codex), "--store", str(store)]) == 0
    server = json.loads((package / "plugins/tomc-memory/mcp.json").read_text(encoding="utf-8"))[
        "mcpServers"
    ]["tomc"]
    assert server["command"] == str(uv)
    assert server["args"] == [
        "run",
        "--locked",
        "--directory",
        str(package / "plugins/tomc-memory"),
        "src/server.py",
    ]
    assert server["env"] == {"TOMC_MEMORY_PATH": str(store)}
    assert calls[-2:] == [
        [str(codex), "plugin", "marketplace", "add", str(package)],
        [str(codex), "plugin", "add", "tomc-memory@tomc-local"],
    ]
    assert not store.exists()


@pytest.mark.parametrize("mode", [[], ["--check"]])
def test_old_codex_fails_before_writing_or_registering(installer, monkeypatch, capsys, mode):
    module, package, uv, codex, calls = installer

    def unsupported(command, **kwargs):
        calls.append(command)
        if command[0] == str(codex):
            raise subprocess.CalledProcessError(2, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", unsupported)
    assert module.main([*mode, "--uv", str(uv), "--codex", str(codex)]) == 1
    assert not (package / "plugins/tomc-memory/mcp.json").exists()
    assert all(command[-1] in {"--help", "--version"} for command in calls)
    assert "does not support the required plugin installation commands" in capsys.readouterr().out


@pytest.mark.parametrize("option", ["--uv", "--codex"])
def test_invalid_explicit_tool_fails_before_configuration(installer, tmp_path, option):
    module, package, uv, codex, calls = installer
    arguments = ["--uv", str(uv), "--codex", str(codex)]
    arguments[arguments.index(option) + 1] = str(tmp_path / "missing executable")
    assert module.main(arguments) == 1
    assert not (package / "plugins/tomc-memory/mcp.json").exists()
    assert all(command[-1] == "--version" for command in calls)


def test_missing_uv_explains_installation_and_path_option(installer, capsys):
    module, package, _, codex, calls = installer
    assert module.main(["--codex", str(codex)]) == 1
    output = capsys.readouterr().out
    assert "--uv" in output and "docs.astral.sh/uv/getting-started/installation/" in output
    assert not (package / "plugins/tomc-memory/mcp.json").exists()
    assert not calls


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable permission bit")
def test_non_executable_uv_is_rejected(installer):
    module, package, uv, codex, calls = installer
    uv.chmod(0o644)
    assert module.main(["--uv", str(uv), "--codex", str(codex)]) == 1
    assert not (package / "plugins/tomc-memory/mcp.json").exists()
    assert not calls


def test_configure_only_does_not_need_or_invoke_codex(installer, capsys):
    module, package, uv, _, calls = installer
    assert module.main(["--configure-only", "--uv", str(uv)]) == 0
    assert (package / "plugins/tomc-memory/mcp.json").exists()
    assert calls == [[str(uv), "--version"]]
    assert "codex plugin add tomc-memory@tomc-local" in capsys.readouterr().out


def test_incomplete_package_fails_before_tool_probes(installer, capsys):
    module, package, uv, codex, calls = installer
    (package / ".agents/plugins/marketplace.json").unlink()
    assert module.main(["--check", "--uv", str(uv), "--codex", str(codex)]) == 1
    assert "Incomplete TOMC installation" in capsys.readouterr().out
    assert not calls


def test_explicit_home_relative_paths_are_expanded(installer, monkeypatch):
    module, package, uv, codex, _ = installer
    monkeypatch.setenv("HOME", str(uv.parent))
    monkeypatch.setenv("USERPROFILE", str(uv.parent))
    assert module.main(["--uv", f"~/{uv.name}", "--codex", f"~/{codex.name}"]) == 0
    server = json.loads((package / "plugins/tomc-memory/mcp.json").read_text(encoding="utf-8"))[
        "mcpServers"
    ]["tomc"]
    assert server["command"] == str(uv)
