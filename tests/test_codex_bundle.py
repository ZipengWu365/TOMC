"""The Codex candidate must carry its runtime and resolve its local marketplace."""

import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def test_codex_marketplace_carries_same_runtime(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from build_codex_plugin import build_codex_bundle
    from build_plugin import build_bundle

    codex = build_codex_bundle(tmp_path / "codex")
    claude = build_bundle(tmp_path / "claude")
    with ZipFile(tmp_path / "codex" / codex["artifact"]) as archive:
        marketplace = json.loads(archive.read(".agents/plugins/marketplace.json"))
        location = marketplace["plugins"][0]["source"]["path"].removeprefix("./")
        manifest = json.loads(archive.read(location + "/.codex-plugin/plugin.json"))
        assert manifest["name"] == marketplace["plugins"][0]["name"]
        assert location + "/plugin.json" not in archive.namelist()
        assert location + "/skills/tomc-memory/SKILL.md" in archive.namelist()
        assert json.loads(archive.read(location + "/mcp.json"))["mcpServers"] == {}
        assert "install.py" in archive.namelist()
        with ZipFile(tmp_path / "claude" / claude["artifact"]) as other:
            for name in other.namelist():
                if name.startswith("src/") or name in {"uv.lock", "pyproject.toml", "LICENSE"}:
                    assert archive.read(location + "/" + name) == other.read(name)
        assert not any(".venv" in name or name.endswith(".sqlite3") for name in archive.namelist())


def test_codex_bundle_bytes_ignore_host_zip_creator_default(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_codex_plugin
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
        monkeypatch.setattr(build_codex_plugin, "ZipInfo", host_zip_info)
        directory = tmp_path / str(host_system)
        receipt = build_codex_plugin.build_codex_bundle(directory)
        assert created_defaults and set(created_defaults) == {host_system}
        artifacts.append((directory / receipt["artifact"]).read_bytes())

    assert artifacts[0] == artifacts[1]
