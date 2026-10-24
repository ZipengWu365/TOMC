"""The Windows companion installer: plan, install, upgrade and uninstall, without touching Windows."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "install_windows_companion", ROOT / "scripts/install_windows_companion.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def layout(tmp_path):
    return installer.Layout(tmp_path / "home", tmp_path / "Startup", tmp_path / "Programs")


@pytest.fixture
def windows(monkeypatch):
    """Record what would reach Windows instead of doing it."""
    calls = {"envs": [], "shortcuts": {}, "started": [], "stopped": [], "run": []}

    def create_env(path, requirements):
        calls["envs"].append((Path(path), [str(item) for item in requirements]))
        (Path(path) / "Scripts").mkdir(parents=True, exist_ok=True)
        (Path(path) / "Scripts" / "python.exe").write_text("fixture", encoding="utf-8")

    def write_shortcut(path, target, arguments, folder, description, icon=None):
        calls["shortcuts"][str(path)] = {"target": str(target), "arguments": arguments}
        Path(path).write_text(json.dumps([str(target), arguments]), encoding="utf-8")

    monkeypatch.setattr(installer, "create_env", create_env)
    monkeypatch.setattr(installer, "write_shortcut", write_shortcut)
    monkeypatch.setattr(installer, "make_icon", lambda layout: False)
    monkeypatch.setattr(installer, "start", lambda path: calls["started"].append(str(path)))
    monkeypatch.setattr(
        installer, "stop_processes", lambda fragment: calls["stopped"].append(str(fragment)) or []
    )
    return calls


def test_preview_describes_a_fresh_install_and_changes_nothing(layout):
    actions = installer.plan(layout)
    assert actions["mode"] == "preview" and actions["version"] == installer.version()
    assert actions["environment"]["action"] == "create"
    assert actions["environment"]["packages"] == [installer.WIDGET]
    assert actions["runtime"]["action"] == "create"
    assert actions["shortcuts"] == [
        str(layout.programs / "TOMC.lnk"),
        str(layout.startup / "TOMC Cat.lnk"),
    ]
    assert actions["data_kept"] and actions["gateway"] == {"selected": False}
    assert not layout.home.exists()


def test_gateway_preview_lists_host_settings_and_problems(layout):
    actions = installer.plan(layout, gateway=True, hosts=("claude",), port=43299)
    gateway = actions["gateway"]
    assert gateway["hosts"] == ["claude"] and gateway["port"] == 43299
    assert gateway["changes_host_settings"] == [".claude/settings.json: env.ANTHROPIC_BASE_URL"]
    assert gateway["problems"] == []
    problems = installer.plan(layout, gateway=True)["gateway"]["problems"]
    assert any("Codex" in problem for problem in problems)  # no ~/.codex/config.toml yet
    layout.base.mkdir(parents=True)
    layout.routing.write_text("{}", encoding="utf-8")
    assert any("already set up" in p for p in installer.gateway_problems(layout, ("claude",)))


def test_gateway_refuses_custom_endpoints_before_installing_anything(layout):
    codex = layout.home / ".codex" / "config.toml"
    codex.parent.mkdir(parents=True)
    codex.write_text('model = "gpt-5"\n[projects."c:/x"]\nprofile = "nested"\n', encoding="utf-8")
    assert installer.gateway_problems(layout, ("codex",)) == []  # table keys are not top level
    codex.write_text(
        'openai_base_url = "https://proxy.example"\nmodel = "gpt-5"\n', encoding="utf-8"
    )
    assert any("custom endpoint" in p for p in installer.gateway_problems(layout, ("codex",)))
    codex.write_text('profile = "work"\n', encoding="utf-8")
    assert any("profile" in p for p in installer.gateway_problems(layout, ("codex",)))
    claude = layout.home / ".claude" / "settings.json"
    claude.parent.mkdir(parents=True)
    claude.write_text('{"env": {"ANTHROPIC_BASE_URL": "https://proxy.example"}}', encoding="utf-8")
    assert any("Claude Code" in p for p in installer.gateway_problems(layout, ("claude",)))
    claude.write_text('{"env": {}}', encoding="utf-8")
    assert installer.gateway_problems(layout, ("claude",)) == []


def test_gateway_config_keeps_the_validated_upstreams(layout):
    config = installer.gateway_config(layout, 43187)
    assert config["port"] == 43187
    assert config["store"] == str(layout.home / ".tomc" / "memory.sqlite3")
    assert config["routes"]["codex"] == {
        "upstream": "https://chatgpt.com/backend-api/codex",
        "compression": {"recent_messages": 6},
    }
    assert config["routes"]["claude"]["upstream"] == "https://api.anthropic.com"


def test_fresh_install_then_uninstall_leaves_only_the_users_data(layout, windows):
    data = layout.home / ".tomc" / "memory.sqlite3"
    data.parent.mkdir(parents=True)
    data.write_bytes(b"user data")
    receipt = installer.Receipt(layout)
    installer.install_cat(layout, receipt)
    assert windows["envs"] == [(layout.env, [installer.WIDGET])]
    assert (layout.runtime / "src/tomc/usage_widget_qt.py").is_file()
    assert (layout.runtime / "src/tomc/data/tomc-expression-1.png").is_file()
    assert not list((layout.runtime / "src/tomc").rglob("__pycache__"))
    assert layout.launcher.read_bytes() == (ROOT / "scripts/pet_launcher.pyw").read_bytes()
    menu, cat = str(layout.programs / "TOMC.lnk"), str(layout.startup / "TOMC Cat.lnk")
    for shortcut in (menu, cat):
        assert windows["shortcuts"][shortcut] == {
            "target": str(layout.pythonw),
            "arguments": f'"{layout.launcher}"',
        }
    assert windows["started"] == [menu]
    saved = json.loads(receipt.path.read_text(encoding="utf-8"))
    assert saved["kind"] == "tomc-windows-install" and saved["replaced"] == {}
    assert set(saved["created"]) == {
        str(layout.env),
        str(layout.runtime),
        str(layout.launcher),
        str(layout.icon),
        menu,
        cat,
    }
    report = installer.uninstall(layout, receipt.path)
    for path in (layout.env, layout.runtime, layout.launcher, Path(menu), Path(cat)):
        assert not path.exists()
    assert data.read_bytes() == b"user data" and report["data_kept"] == str(data.parent)
    assert str(layout.launcher) in windows["stopped"]


def test_upgrade_keeps_the_old_install_and_uninstall_restores_it_exactly(layout, windows):
    old = layout.runtime / "src/tomc/old_module.py"
    old.parent.mkdir(parents=True)
    old.write_text("old = True\n", encoding="utf-8")
    layout.launcher.write_text("# old launcher\n", encoding="utf-8")
    (layout.env / "Scripts").mkdir(parents=True)
    (layout.env / "Scripts" / "python.exe").write_text("existing", encoding="utf-8")
    layout.startup.mkdir(parents=True)
    (layout.startup / "TOMC Cat.lnk").write_bytes(b"old shortcut")
    assert installer.plan(layout)["runtime"]["action"].startswith("replace")
    receipt = installer.Receipt(layout)
    installer.install_cat(layout, receipt, start_after=False)
    assert not old.exists() and windows["started"] == []
    saved = json.loads(receipt.path.read_text(encoding="utf-8"))
    assert str(layout.env) not in saved["created"]  # an existing environment is reused
    assert set(saved["replaced"]) == {
        str(layout.runtime),
        str(layout.launcher),
        str(layout.startup / "TOMC Cat.lnk"),
    }
    installer.uninstall(layout, receipt.path)
    assert old.read_text(encoding="utf-8") == "old = True\n"
    assert layout.launcher.read_text(encoding="utf-8") == "# old launcher\n"
    assert (layout.startup / "TOMC Cat.lnk").read_bytes() == b"old shortcut"
    assert (layout.env / "Scripts" / "python.exe").is_file()
    assert not (layout.programs / "TOMC.lnk").exists()


def test_gateway_install_activates_after_health_and_uninstall_restores_hosts(
    layout, windows, monkeypatch
):
    activation = layout.base / "archive" / "session-update-fixture" / "receipt.json"

    def run(command, **kwargs):
        command = [str(part) for part in command]
        windows["run"].append(command)
        if "--activate" in command:
            return '{"mode": "activate"}\n' + json.dumps(
                {"status": "installed", "receipt": str(activation)}
            )
        return '{"mode": "preview"}'

    monkeypatch.setattr(installer, "run", run)
    monkeypatch.setattr(installer, "wait_healthy", lambda port: True)
    receipt = installer.Receipt(layout)
    receipt.save()
    gateway = installer.install_gateway(layout, receipt, hosts=("claude",), port=43299)
    runtime = Path(gateway["runtime"])
    assert (runtime / "src/tomc/request_gateway.py").is_file()
    config = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    assert config["port"] == 43299
    preview, activate = windows["run"]
    assert "--activate" not in preview and activate[-1] == "--activate"
    assert activate[activate.index("--hosts") + 1 :] == ["claude", "--activate"]
    shortcut = str(layout.startup / "TOMC Gateway.lnk")
    assert windows["shortcuts"][shortcut]["target"].endswith("pythonw.exe")
    assert f'--config "{runtime / "config.json"}"' in windows["shortcuts"][shortcut]["arguments"]
    assert windows["started"] == [shortcut]
    assert gateway["activation"] == str(activation)
    windows["run"].clear()
    report = installer.uninstall(layout, receipt.path)
    restore = windows["run"][0]
    assert restore[restore.index("--restore") + 1] == str(activation)
    assert "host settings" in report["restored"] and not runtime.exists()
    assert str(runtime) in windows["stopped"]


def test_unhealthy_gateway_never_changes_host_settings(layout, windows, monkeypatch):
    commands = []
    monkeypatch.setattr(installer, "run", lambda command, **kw: commands.append(command) or "{}")
    monkeypatch.setattr(installer, "wait_healthy", lambda port: False)
    receipt = installer.Receipt(layout)
    with pytest.raises(RuntimeError, match="did not answer"):
        installer.install_gateway(layout, receipt, hosts=("claude",), port=43299)
    assert all("--activate" not in [str(part) for part in command] for command in commands)


def test_uninstall_accepts_only_this_installations_receipts(layout, tmp_path):
    stray = tmp_path / "receipt.json"
    stray.write_text(json.dumps({"kind": "tomc-windows-install"}), encoding="utf-8")
    with pytest.raises(ValueError, match="archive"):
        installer.uninstall(layout, stray)
    other = layout.base / "archive" / "x" / "receipt.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"kind": "something-else"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a TOMC"):
        installer.uninstall(layout, other)


@pytest.mark.skipif(os.name != "nt", reason="the command line runs on Windows only")
def test_command_line_preview_changes_nothing(layout, capsys):
    assert (
        installer.main(
            [
                "--home",
                str(layout.home),
                "--startup",
                str(layout.startup),
                "--programs",
                str(layout.programs),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["mode"] == "preview"
    assert not layout.home.exists() and not layout.startup.exists()
