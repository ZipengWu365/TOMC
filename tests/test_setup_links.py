"""Cursor install-link protocol and preservation of existing setup configurations."""

import base64
import json
import os
import sys
from urllib.parse import parse_qs, urlsplit

import pytest

from tomc.cli import main
from tomc.setup import client_config, client_link


def decode_link(link):
    url = urlsplit(link.strip())
    assert url.scheme == "cursor"
    assert url.netloc == "anysphere.cursor-deeplink"
    assert url.path == "/mcp/install"
    query = parse_qs(url.query, strict_parsing=True)
    assert query["name"] == ["tomc"]
    assert set(query) == {"name", "config"}
    assert not any(char in url.query.split("config=", 1)[1] for char in "+/=")
    return json.loads(base64.b64decode(query["config"][0], validate=True).decode("utf-8"))


def test_cursor_link_preserves_current_configuration_and_unicode_paths(tmp_path, monkeypatch):
    interpreter = str(tmp_path / "Python 环境" / "bin" / "python")
    store = tmp_path / "记忆 notebooks" / "memory.sqlite3"
    monkeypatch.setattr(sys, "executable", interpreter)
    config = decode_link(client_link("cursor", store))
    assert config == json.loads(client_config("cursor", store))["mcpServers"]
    assert config["tomc"]["command"] == interpreter
    assert config["tomc"]["args"] == ["-m", "tomc", "mcp", "--store", str(store)]
    assert not store.exists()


def test_cursor_link_resolves_default_store_without_creating_it(tmp_path, monkeypatch):
    store = tmp_path / "default store" / "memory.sqlite3"
    monkeypatch.setenv("TOMC_MEMORY_PATH", str(store))
    config = decode_link(client_link("cursor"))
    assert config["tomc"]["args"][-1] == str(store)
    assert not store.exists()


def test_cli_cursor_link(tmp_path, capsys):
    store = tmp_path / "记忆 store" / "memory.sqlite3"
    assert main(["setup", "--client", "cursor", "--link", "--store", str(store)]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert decode_link(captured.out) == json.loads(client_config("cursor", store))["mcpServers"]
    assert not store.exists()


@pytest.mark.parametrize("client", ["claude", "json", "cursor"])
def test_existing_json_setup_is_unchanged(client, tmp_path, capsys):
    store = tmp_path / "memory.sqlite3"
    expected = {
        "mcpServers": {
            "tomc": {
                "command": os.path.abspath(sys.executable),
                "args": ["-m", "tomc", "mcp", "--store", str(store)],
            }
        }
    }
    assert main(["setup", "--client", client, "--store", str(store)]) == 0
    captured = capsys.readouterr()
    assert captured.out == json.dumps(expected, indent=2) + "\n"
    assert captured.err == ""


def test_existing_codex_setup_is_unchanged(tmp_path, capsys):
    store = tmp_path / "memory.sqlite3"
    command = os.path.abspath(sys.executable)
    args = ["-m", "tomc", "mcp", "--store", str(store)]
    assert main(["setup", "--client", "codex", "--store", str(store)]) == 0
    captured = capsys.readouterr()
    assert (
        captured.out
        == f"[mcp_servers.tomc]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n"
    )
    assert captured.err == ""


@pytest.mark.parametrize("client", ["codex", "claude", "json"])
def test_non_cursor_links_are_rejected(client, capsys):
    with pytest.raises(ValueError, match="--client cursor"):
        client_link(client)
    with pytest.raises(SystemExit) as error:
        main(["setup", "--client", client, "--link"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--link requires --client cursor" in captured.err
