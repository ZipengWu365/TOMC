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


def test_reader_preserves_cache_counts_without_inventing_usage(reader):
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 12,
        "total_tokens": 112,
        "prompt_cache_hit_tokens": 80,
        "prompt_cache_miss_tokens": 20,
        "prompt_tokens_details": {"cached_tokens": 80, "audio_tokens": 0, "private": "omit"},
        "completion_tokens_details": {
            "reasoning_tokens": 5,
            "bad_tokens": True,
            "negative_tokens": -1,
        },
        "unknown": "private provider metadata",
    }
    body = {"choices": [{"message": {"content": "answer"}}], "usage": usage}
    reader._opener.open.return_value = io.BytesIO(json.dumps(body).encode())
    response = reader.complete([])
    assert response.usage == {
        "prompt_tokens": 100,
        "completion_tokens": 12,
        "total_tokens": 112,
        "prompt_cache_hit_tokens": 80,
        "prompt_cache_miss_tokens": 20,
        "prompt_tokens_details": {"cached_tokens": 80, "audio_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 5},
    }
    body.pop("usage")
    reader._opener.open.return_value = io.BytesIO(json.dumps(body).encode())
    assert reader.complete([]).usage == {}


@pytest.mark.parametrize("usage", [None, [], "private invalid usage"])
def test_reader_malformed_usage_is_sanitized_and_not_retried(reader, usage):
    body = {"choices": [{"message": {"content": "answer"}}], "usage": usage}
    reader._opener.open.return_value = io.BytesIO(json.dumps(body).encode())
    with pytest.raises(ReaderError, match="invalid_response") as error:
        reader.complete([])
    assert reader._opener.open.call_count == 1
    assert "private" not in str(error.value)


def test_multiturn_sends_prepared_requests_and_reselects_original_evidence(reader):
    from copy import deepcopy

    from examples.api_multiturn import run_turn

    history = [
        {
            "role": "user",
            "content": "\n".join(
                [
                    "framework = Flask",
                    "backup_framework copies framework",
                    "framework = FastAPI",
                    "The database migration failed because the invoices table was locked.",
                    *[
                        f"Planning note {i}: reviewed unrelated deployment discussion."
                        for i in range(30)
                    ],
                ]
            ),
        }
    ]
    original = deepcopy(history)
    first_task = "What are the current framework and backup_framework values?"
    second_task = "Why did the database migration fail?"
    sent = []
    answers = iter(
        ["framework = FastAPI; backup_framework = Flask", "The invoices table was locked."]
    )

    def respond(request, **kwargs):
        sent.append(json.loads(request.data))
        return io.BytesIO(
            json.dumps(
                {
                    "choices": [{"message": {"content": next(answers)}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 95, "prompt_tokens_details": {"cached_tokens": 32}},
                }
            ).encode()
        )

    reader._opener.open.side_effect = respond
    first = run_turn(
        history, first_task, budget=48, reader=reader, instructions="Reply in Chinese."
    )
    assert "invoices" not in sent[0]["messages"][1]["content"]
    assert "[STATE] backup_framework = Flask" in sent[0]["messages"][1]["content"]
    second = run_turn(
        history, second_task, budget=48, reader=reader, instructions="Reply in Chinese."
    )
    assert "invoices table was locked" in sent[1]["messages"][1]["content"]
    assert len(sent) == 2 and all(len(request["messages"]) == 2 for request in sent)
    assert all(
        request["messages"][0]["content"].startswith("Reply in Chinese.") for request in sent
    )
    assert history[:1] == original
    assert [m["role"] for m in history[1:]] == ["user", "assistant", "user", "assistant"]
    for report in (first, second):
        assert report["prepared_message_text_tokens"] < report["original_message_text_tokens"]
        assert report["provider_usage"]["prompt_tokens_details"]["cached_tokens"] == 32

    # Later updates must be recompiled; a failed request must not change history.
    history.append({"role": "user", "content": "framework = Django"})
    before_failure = deepcopy(history)
    reader._opener.open.side_effect = HTTPError("https://example.invalid", 401, "body", {}, None)
    with pytest.raises(ReaderError):
        run_turn(history, first_task, reader=reader)
    assert history == before_failure
    failed_payload = json.loads(reader._opener.open.call_args.args[0].data)
    assert "[STATE] framework = Django" in failed_payload["messages"][1]["content"]


def test_multiturn_dry_run_and_empty_budget_never_send(reader):
    from examples.api_multiturn import run_turn

    history = [{"role": "user", "content": "A long indivisible observation " * 50}]
    report = run_turn(history, "What happened?", budget=1024)
    assert report["mode"] == "dry-run" and report["provider_usage"] is None
    assert len(history) == 1
    with pytest.raises(ValueError, match="No complete record"):
        run_turn(history, "What happened?", budget=1, reader=reader)
    reader._opener.open.assert_not_called()
    assert len(history) == 1


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
