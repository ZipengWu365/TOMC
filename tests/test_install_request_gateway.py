import importlib.util
import json
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


def test_refuse_other_upstream(home_runtime):
    home, runtime = home_runtime
    (home / ".codex/config.toml").write_text('openai_base_url="https://custom.example/v1"')
    with pytest.raises(ValueError, match="custom Codex"):
        module.plan_activation(home, runtime)


def test_refuse_overwriting_post_install_edits(home_runtime):
    home, runtime = home_runtime
    result = module.install(module.plan_activation(home, runtime))
    path = home / ".codex/config.toml"
    path.write_text(path.read_text() + "\n# user edit\n")
    with pytest.raises(ValueError, match="has changed"):
        module.restore(home, result["receipt"])
    assert "# user edit" in path.read_text()


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
    module.restore(home, result["receipt"])
    assert not (pet / "context_library.py").exists()
    assert (pet / "usage_widget_qt.py").read_text() == "# old pet without context browser"


def test_rollback_rechecks_each_target_before_replacing(home_runtime, monkeypatch):
    home, runtime = home_runtime
    result = module.install(module.plan_activation(home, runtime))
    codex = home / ".codex/config.toml"
    write = module._atomic_write

    def concurrent_edit(path, contents):
        write(path, contents)
        codex.write_text("# concurrent user edit")

    monkeypatch.setattr(module, "_atomic_write", concurrent_edit)
    with pytest.raises(ValueError, match="during rollback"):
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
