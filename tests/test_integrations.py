"""No live model calls: test connector failure semantics and official adapter delegation."""

import io
import json
import subprocess
import sys
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from tomc import compile_memory
from tomc.adapters.llmlingua import AdapterUnavailable, LLMLinguaAdapter
from tomc.adapters.reader import APIReader, ReaderError


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setenv("TOMC_READER_API_KEY", "test-placeholder")
    monkeypatch.setenv("TOMC_READER_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("TOMC_READER_MODEL", "mock-reader")
    monkeypatch.setattr("tomc.adapters.reader.time.sleep", lambda _: None)
    r = APIReader(retries=1)
    r._opener = Mock()
    return r


def test_reader_config_is_required(monkeypatch):
    monkeypatch.delenv("TOMC_READER_API_KEY", raising=False)
    with pytest.raises(ReaderError, match="configuration_missing"):
        APIReader()


def test_reader_success_and_retry(reader):
    body = {
        "model": "mock-v2",
        "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 4},
    }
    reader._opener.open.side_effect = [
        URLError("private detail"),
        io.BytesIO(json.dumps(body).encode()),
    ]
    response = reader.complete([{"role": "user", "content": "private prompt"}])
    assert response.text == "answer" and response.model == "mock-v2"
    assert reader._opener.open.call_count == 2


def test_auth_error_is_sanitized_and_never_retried(reader):
    reader._opener.open.side_effect = HTTPError(
        "https://private.invalid", 401, "secret response", {}, None
    )
    with pytest.raises(ReaderError) as error:
        reader.complete([])
    assert error.value.category == "authentication"
    assert reader._opener.open.call_count == 1
    assert "secret" not in str(error.value) and "private" not in str(error.value)
    assert "test-placeholder" not in repr(reader)


def test_reader_retry_limit(reader):
    reader._opener.open.side_effect = HTTPError("https://private.invalid", 429, "body", {}, None)
    with pytest.raises(ReaderError, match="rate_limit"):
        reader.complete([])
    assert reader._opener.open.call_count == 2


def test_adapter_does_not_fake_an_unavailable_model():
    with pytest.raises(AdapterUnavailable):
        compile_memory("abc", "q", strategy=LLMLinguaAdapter())


def test_official_longllmlingua_options_and_budget_disclosure():
    official = Mock()
    official.compress_prompt.return_value = {"compressed_prompt": "one two three"}
    result = compile_memory(
        "one two\nthree four", "q", 2, LLMLinguaAdapter(official, variant="longllmlingua")
    )
    assert result.compiled_memory == "one two"
    assert result.diagnostics["post_clipped"]
    assert official.compress_prompt.call_args.kwargs["rank_method"] == "longllmlingua"


def test_cli_defaults_to_paper_memory_in_a_different_working_directory(tmp_path):
    conversation = tmp_path / "conversation.json"
    conversation.write_text(json.dumps([{"role": "user", "content": "A = 1\nA = 2"}]))
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tomc",
            "compile",
            str(conversation),
            "--query",
            "current A",
            "--budget",
            "64",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["diagnostics"]["selected_strategy"] == "tomc_raw"
    assert result["ledger"][0]["value"] == "2"
    assert "A = 1" in result["raw_fallback"] and "A = 2" in result["raw_fallback"]
    assert "[VERIFIER]" not in result["compiled_memory"]


def test_cli_bad_json_reports_clean_error(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text("{ private content")
    completed = subprocess.run(
        [sys.executable, "-m", "tomc", "compile", str(source), "--query", "q"],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2 and "private content" not in completed.stderr
