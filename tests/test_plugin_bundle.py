"""Check the distributable content and independence from checkout state."""

import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_only_contains_runtime_source(tmp_path, monkeypatch):
    # Load the script without requiring the scripts directory to be a package.
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_plugin", ROOT / "scripts/build_plugin.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    first = builder.build_bundle(tmp_path / "first")
    second = builder.build_bundle(tmp_path / "second")
    assert first["sha256"] == second["sha256"]
    with ZipFile(tmp_path / "first" / first["artifact"]) as archive:
        names = set(archive.namelist())
        assert {"uv.lock", "src/server.py", "src/tomc/_vendor/tomc2.py"} <= names
        assert "src/tomc/data/snapshot.json" in names
        assert not any(".venv" in n or n.endswith(".sqlite3") or ".env" in n for n in names)
        assert not any(n.startswith(("demo/", "benchmarks/", "tests/")) for n in names)
        assert archive.read("src/tomc/compiler.py") == (ROOT / "src/tomc/compiler.py").read_bytes()
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["server"]["entry_point"] in names
        assert manifest["server"]["type"] == "uv"
        assert "--locked" in manifest["server"]["mcp_config"]["args"]


def test_bundle_bytes_ignore_host_zip_creator_default(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_plugin

    artifacts = []
    for host_system in (0, 3):
        created_defaults = []

        def host_zip_info(*args, _host_system=host_system, **kwargs):
            item = ZipInfo(*args, **kwargs)
            item.create_system = _host_system
            created_defaults.append(item.create_system)
            return item

        monkeypatch.setattr(build_plugin, "ZipInfo", host_zip_info)
        directory = tmp_path / str(host_system)
        receipt = build_plugin.build_bundle(directory)
        assert created_defaults and set(created_defaults) == {host_system}
        artifacts.append((directory / receipt["artifact"]).read_bytes())

    assert artifacts[0] == artifacts[1]
