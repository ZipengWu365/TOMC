import importlib.util
from pathlib import Path

import pytest

from tomc.request_activity import RequestActivity


@pytest.fixture
def validation(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location(
        "validate_codex_global", directory / "validate_codex_global.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_post_install_check_reads_only_the_explicit_test_thread(tmp_path, validation):
    path = tmp_path / "production_like.sqlite3"
    activity = RequestActivity(path)
    activity.start("test-request", "codex", "test-thread")
    activity.start("other-private-request", "codex", "another-thread")
    activity.start("different-host-request", "claude", "test-thread")
    activity.finish("test-request", state="prepared", before_tokens=100, after_tokens=80)
    activity.sent("test-request")
    activity.usage("test-request", provider_input_tokens=90, provider_cached_tokens=30)
    before = path.read_bytes()
    rows = validation.request_rows(path, "test-thread")
    assert [row["request_id"] for row in rows] == ["test-request"]
    assert rows[0]["provider_input_tokens"] == 90
    assert path.read_bytes() == before


def test_post_install_read_does_not_create_missing_store(tmp_path, validation):
    path = tmp_path / "not-installed" / "memory.sqlite3"
    assert validation.request_rows(path, "test-thread") == []
    assert not path.parent.exists()
