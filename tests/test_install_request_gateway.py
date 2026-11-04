import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import tomlkit

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "gateway_installer", SCRIPTS / "install_request_gateway.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def home_runtime(tmp_path):
    home, runtime = tmp_path / "home", tmp_path / "runtime"
    (home / ".codex/tomc").mkdir(parents=True)
    (home / ".claude").mkdir()
    (runtime / "src/tomc").mkdir(parents=True)
    (runtime / "src/tomc/request_gateway.py").write_text("# fixture")
    (home / ".codex/config.toml").write_text(
        '# comment\nmodel="existing"\napproval_policy="on-request"\n[plugins.test]\nenabled=true\n'
    )
    (home / ".claude/settings.json").write_text(
        json.dumps({"env": {"KEEP": "fixture"}, "permissions": {"allow": []}})
    )
    return home, runtime


def test_preview_preserves_settings_and_places_root_key(home_runtime):
    home, runtime = home_runtime
    before = (home / ".codex/config.toml").read_bytes()
    plan = module.plan_activation(home, runtime)
    assert (home / ".codex/config.toml").read_bytes() == before
    codex = next(c for c in plan.changes if c.relative == ".codex/config.toml")
    document = tomlkit.parse(codex.after.decode())
    assert document["openai_base_url"] == "http://127.0.0.1:43187/codex"
    assert document["model"] == "existing"
    assert document["approval_policy"] == "on-request"
    assert document["plugins"]["test"]["enabled"] is True
    assert codex.after.startswith(b"# comment")
    claude = json.loads(
        next(c.after for c in plan.changes if c.relative == ".claude/settings.json")
    )
    assert claude["env"]["KEEP"] == "fixture"
    assert claude["permissions"] == {"allow": []}


def test_activation_and_exact_rollback(home_runtime):
    home, runtime = home_runtime
    originals = {
        p: p.read_bytes() for p in (home / ".codex/config.toml", home / ".claude/settings.json")
    }
    result = module.install(module.plan_activation(home, runtime))
    assert result["status"] == "installed"
    assert module.plan_activation(home, runtime).changes == ()
    module.restore(home, result["receipt"])
    assert all(path.read_bytes() == contents for path, contents in originals.items())
    assert not (home / ".codex/tomc/gateway-routing.json").exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_backups_are_owner_only_and_host_files_keep_their_permissions(home_runtime):
    home, runtime = home_runtime
    codex = home / ".codex/config.toml"
    codex.chmod(0o644)
    result = module.install(module.plan_activation(home, runtime))
    backups = [p for p in Path(result["backup_directory"]).rglob("*") if p.is_file()]
    assert backups and all(p.stat().st_mode & 0o777 == 0o600 for p in backups)
    assert Path(result["backup_directory"]).stat().st_mode & 0o777 == 0o700
    assert codex.stat().st_mode & 0o777 == 0o644
    codex.write_text(codex.read_text() + "\n# host edit\n")
    module.restore(home, result["receipt"])
    assert codex.stat().st_mode & 0o777 == 0o644


def test_refuse_other_upstream(home_runtime):
    home, runtime = home_runtime
    (home / ".codex/config.toml").write_text('openai_base_url="https://custom.example/v1"')
    with pytest.raises(ValueError, match="custom Codex"):
        module.plan_activation(home, runtime)


def test_restore_removes_only_tomc_keys_and_keeps_later_host_edits(home_runtime, capsys):
    home, runtime = home_runtime
    result = module.install(module.plan_activation(home, runtime))
    codex, claude = home / ".codex/config.toml", home / ".claude/settings.json"
    # Codex records trust for a new project; Claude Code gains a new setting.
    codex.write_text(codex.read_text() + '\n[projects."/work/b"]\ntrust_level = "trusted"\n')
    settings = json.loads(claude.read_text())
    settings["model"] = "host-choice"
    claude.write_text(json.dumps(settings))
    assert module.restore(home, result["receipt"])["status"] == "restored"
    document = tomlkit.parse(codex.read_text())
    assert "openai_base_url" not in document
    assert document["model"] == "existing"
    assert document["projects"]["/work/b"]["trust_level"] == "trusted"
    assert document["plugins"]["test"]["enabled"] is True
    assert json.loads(claude.read_text()) == {
        "env": {"KEEP": "fixture"},
        "permissions": {"allow": []},
        "model": "host-choice",
    }
    assert not (home / ".codex/tomc/gateway-routing.json").exists()
    # Running it again is harmless, also from the command line.
    assert module.restore(home, result["receipt"])["status"] == "already_restored"
    capsys.readouterr()
    assert module.main(["--home", str(home), "--restore", result["receipt"]]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "already_restored"


def test_restore_direct_needs_no_receipt_and_is_idempotent(home_runtime, capsys):
    home, runtime = home_runtime
    module.install(module.plan_activation(home, runtime))
    codex = home / ".codex/config.toml"
    codex.write_text(codex.read_text() + '\n[projects."/work/c"]\ntrust_level = "trusted"\n')
    assert module.main(["--home", str(home), "--restore-direct"]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "restored"
    assert first["files"] == {".codex/config.toml": "restored", ".claude/settings.json": "restored"}
    assert "127.0.0.1" not in codex.read_text() and "/work/c" in codex.read_text()
    assert json.loads((home / ".claude/settings.json").read_text())["env"] == {"KEEP": "fixture"}
    assert module.main(["--home", str(home), "--restore-direct"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "already_restored"


def test_restore_direct_keeps_custom_endpoints_and_unknown_files(tmp_path):
    from tomc.direct_connection import restore_direct

    (tmp_path / ".codex").mkdir()
    (tmp_path / ".claude").mkdir()
    custom = 'openai_base_url = "https://proxy.example/v1"\n'
    (tmp_path / ".codex/config.toml").write_text(custom)
    (tmp_path / ".claude/settings.json").write_text('{"env": {"ANTHROPIC_BASE_URL": "x"}}')
    assert restore_direct(tmp_path)["status"] == "already_restored"
    assert (tmp_path / ".codex/config.toml").read_text() == custom
    (tmp_path / ".claude/settings.json").write_text("{not json")
    assert restore_direct(tmp_path)["files"][".claude/settings.json"] == (
        "unreadable_left_unchanged"
    )


def test_host_specific_install(home_runtime):
    home, runtime = home_runtime
    plan = module.plan_activation(home, runtime, hosts=("codex",))
    assert ".claude/settings.json" not in [c.relative for c in plan.changes]


@pytest.mark.parametrize(
    "hosts,restart", [(("claude",), False), (("codex",), True), (("codex", "claude"), True)]
)
def test_reload_marker_distinguishes_configuration_from_live_sessions(home_runtime, hosts, restart):
    home, runtime = home_runtime
    plan = module.plan_activation(home, runtime, hosts=hosts)
    marker = json.loads(
        next(c.after for c in plan.changes if c.relative.endswith("gateway-routing.json"))
    )
    assert marker["requires_client_restart"] is restart
    assert marker["existing_sessions_verified"] is False
    assert marker["client_reload"] == {
        host: "settings_env_hot_reload_supported"
        if host == "claude"
        else "restart_or_new_thread_required"
        for host in hosts
    }


def test_upgrade_from_pet_without_context_feature_includes_all_new_dependencies(home_runtime):
    home, runtime = home_runtime
    pet = home / ".codex/tomc/pet-current/src/tomc"
    pet.mkdir(parents=True)
    (pet / "usage_widget_qt.py").write_text("# old pet without context browser")
    for name in module.PET_MODULES:
        (runtime / "src/tomc" / name).write_text("# validated fixture module")
    result = module.install(module.plan_activation(home, runtime))
    assert (pet / "context_library.py").is_file()
    assert (pet / "session_store.py").is_file()
    assert (pet / "request_activity.py").is_file()
    assert (pet / "macos_ui.py").is_file()
    module.restore(home, result["receipt"])
    assert not (pet / "context_library.py").exists()
    assert (pet / "usage_widget_qt.py").read_text() == "# old pet without context browser"


def test_gateway_update_can_import_analysis_and_mac_modules_on_windows(home_runtime):
    pytest.importorskip("PySide6")
    home, runtime = home_runtime
    pet = home / ".codex/tomc/pet-current/src/tomc"
    pet.mkdir(parents=True)
    package = runtime / "src/tomc"
    source = SCRIPTS.parent / "src/tomc"
    for target in (package, pet):
        shutil.copytree(
            source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
        )
    added = ("analysis_qt.py", "analysis.py", "categories.py", "macos_ui.py")
    for name in added:
        (pet / name).unlink()
    (pet / "savings.py").write_text("# previous savings module\n", encoding="utf-8")
    module.install(module.plan_activation(home, runtime))
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


def test_rollback_rechecks_each_target_before_replacing(home_runtime, monkeypatch):
    home, runtime = home_runtime
    result = module.install(module.plan_activation(home, runtime))
    codex = home / ".codex/config.toml"
    write = module._atomic_write

    def concurrent_edit(path, contents):
        write(path, contents)
        codex.write_text("# concurrent user edit")

    monkeypatch.setattr(module, "_atomic_write", concurrent_edit)
    module.restore(home, result["receipt"])
    assert codex.read_text() == "# concurrent user edit"


def _load_script(name, filename):
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader(name, str(SCRIPTS / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_stage_rejects_recursive_destination_and_missing_source_without_creating_dirs(tmp_path):
    staging = _load_script("gateway_stager", "stage_request_gateway.py")
    source = tmp_path / "source"
    nested = source / "src/tomc/runtime"
    with pytest.raises(ValueError, match="inside"):
        staging.stage(source, nested)
    assert not nested.exists()
    with pytest.raises(ValueError, match="incomplete"):
        staging.stage(source, tmp_path / "runtime")
    assert not (tmp_path / "runtime").exists()


def test_stage_receipt_covers_requirements_and_does_not_activate_clients(tmp_path):
    import hashlib

    staging = _load_script("gateway_stager", "stage_request_gateway.py")
    source, target = tmp_path / "source", tmp_path / "staged"
    package = source / "src/tomc"
    package.mkdir(parents=True)
    (package / "request_gateway.py").write_text("# fixture gateway")
    (package / "data.json").write_text("{}")
    (source / "scripts").mkdir()
    for name in (
        "install_request_gateway.py",
        "install_context_workspace.py",
        "request_gateway_launcher.pyw",
    ):
        (source / "scripts" / name).write_text("# fixture script")
    (source / "requirements-gateway.txt").write_text("fixture==1")
    result = staging.stage(source, target)
    receipt = json.loads((target / "source-receipt.json").read_text())
    assert result["clients_activated"] is False
    assert any(row["path"] == "requirements-gateway.txt" for row in receipt["files"])
    for row in receipt["files"]:
        assert hashlib.sha256((target / row["path"]).read_bytes()).hexdigest() == row["sha256"]


@pytest.mark.parametrize("failure", ["status_write", "interrupt"])
def test_supervisor_does_not_orphan_child_on_status_failure_or_interruption(
    tmp_path, monkeypatch, failure
):
    launcher = _load_script("gateway_launcher", "request_gateway_launcher.pyw")
    actions = []

    class Child:
        pid = 4321

        def poll(self):
            return None

        def wait(self, timeout=None):
            if timeout is None:
                raise KeyboardInterrupt()
            actions.append(("wait", timeout))

        def terminate(self):
            actions.append("terminate")

    def launch(arguments, **options):
        assert (
            options["stdin"]
            == options["stdout"]
            == options["stderr"]
            == launcher.subprocess.DEVNULL
        )
        assert options["creationflags"] == getattr(launcher.subprocess, "CREATE_NO_WINDOW", 0)
        actions.append("start")
        return Child()

    monkeypatch.setattr(launcher.subprocess, "Popen", launch)
    if failure == "status_write":
        original_write = Path.write_text

        def fail_status(path, *args, **kwargs):
            if path.name.endswith(".status.tmp"):
                raise OSError("fixture disk failure")
            return original_write(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_status)
    with pytest.raises(OSError if failure == "status_write" else KeyboardInterrupt):
        launcher.supervise(tmp_path, tmp_path / "config.json")
    assert actions == ["start", "terminate", ("wait", 5)]
