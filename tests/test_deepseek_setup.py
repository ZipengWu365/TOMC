"""DSH overlays preserve Unicode/space paths and stay additive and secret-free."""

import json
import sys

from tomc.cli import main


def test_dsh_overlay_paths_and_no_side_effects(tmp_path, monkeypatch, capsys):
    interpreter = str(tmp_path / "Python 环境" / "python.exe")
    database = tmp_path / "task notes" / "memory.sqlite3"
    monkeypatch.setattr(sys, "executable", interpreter)
    assert main(["setup", "--client", "deepseek", "--store", str(database)]) == 0
    output = capsys.readouterr()
    assert not output.err
    patch = json.loads(output.out)
    assert len(patch) == 1 and set(patch[0]) == {"insert"}
    (row,) = patch[0]["insert"]
    assert row["name"] == "@deepseek-ai/dsh-mcp-client"
    assert row["config"]["serverName"] == "tomc"
    assert row["config"]["transport"] == "stdio"
    assert row["config"]["command"] == interpreter
    assert row["config"]["args"] == ["-m", "tomc", "mcp", "--store", str(database)]
    assert "env" not in row["config"]
    assert not database.exists()
