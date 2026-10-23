"""Pure recorder contracts; these tests never create a Qt application or UI."""

import argparse
import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tomc.pet_growth import growth_state


@pytest.fixture
def scripts(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(directory))
    result = {}
    for name in ("validate_pet_desktop", "validate_pet_stages"):
        spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result[name] = module
    return result


def test_real_recorder_identifies_displayed_report_not_newer_busy_request(scripts):
    pet = SimpleNamespace(active_report={"request_id": "displayed", "usable": True,
                                        "context_input_tokens": 100000},
                          preparing_request={"request_id": "newer-unrelated"},
                          request_animation_id="displayed", art=SimpleNamespace(level=3))
    identity = scripts["validate_pet_desktop"].animation_identity(pet, growth_state)
    assert identity == {"request_id": "displayed", "context_input_tokens": 100000,
                        "stage": 3, "expected_stage": 3, "length_known": True}


def test_duration_bounds_and_coverage_do_not_claim_missing_frames(scripts):
    script = scripts["validate_pet_desktop"]
    assert [script.duration_seconds(n) for n in (30, 300, 900)] == [30, 300, 900]
    for value in (0, 29, 901):
        with pytest.raises(argparse.ArgumentTypeError):
            script.duration_seconds(value)
    assert script.phase_coverage([0, .45, .9, None]) == {
        "active_frames": 3, "early": True, "middle": True, "late": True, "idle": True}
    assert not script.phase_coverage([.4, .5])["late"]
    assert not script.phase_coverage([])["idle"]


def test_atomic_utf8_report_preserves_previous_on_failure(scripts, tmp_path, monkeypatch):
    script = scripts["validate_pet_desktop"]
    path = tmp_path / "observation.json"
    script.write_report(path, {"language": "中文", "stage": 2})
    assert json.loads(path.read_text(encoding="utf-8"))["stage"] == 2
    before = path.read_bytes()

    def denied(*args):
        raise PermissionError("fixture")

    monkeypatch.setattr(script.os, "replace", denied)
    with pytest.raises(PermissionError):
        script.write_report(path, {"stage": 3})
    assert path.read_bytes() == before and not path.with_suffix(".json.tmp").exists()


def test_recorder_never_injects_compilation_or_calls_animation(scripts):
    source = Path(scripts["validate_pet_desktop"].__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert "collect" not in calls and "record" not in calls and "finish" not in calls
    # Flags may change only inside the explicit discoverability branch.
    branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                and ast.unparse(node.test) == "args.discoverable"]
    assert len(branches) == 1
    assert source.count("setWindowFlags(") == ast.unparse(branches[0]).count("setWindowFlags(")
    assert "app.quit()" in source and "lock.unlock()" in source


def test_gallery_auto_play_is_preview_only_and_records_per_stage_phases(scripts):
    source = Path(scripts["validate_pet_stages"].__file__).read_text(encoding="utf-8")
    assert '"--auto-play"' in source and '"preview_only": True' in source
    assert '"stage_coverage"' in source and '"context_input_tokens"' in source
    assert '"collected"' in source and '"collect"' in source
    assert "UsageStore" not in source and "RequestActivity" not in source
