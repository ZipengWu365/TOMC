"""The local savings analysis and the anonymous feedback report built from it."""

import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from tomc.analysis import (
    MAX_COMMENT,
    MAX_CONVERSATIONS,
    MAX_URL,
    analysis_report,
    coverage_group,
    feedback_filename,
    feedback_markdown,
    feedback_page,
    feedback_payload,
    feedback_url,
)
from tomc.context_library import ContextLibrary
from tomc.request_activity import RequestActivity
from tomc.usage import UsageStore

REFERENCE = {"rate": 2.0, "label": "Fixture model", "model": "fixture", "mode": "input"}
NAMES = {
    ("codex", "thread-a"): {"title": "Fix the gateway bug", "folder": "private-repo"},
    ("claude", "session-b"): {"title": "润色论文引言", "folder": "draft-folder"},
}
SECRETS = (
    "Fix the gateway bug",
    "润色论文引言",
    "private-repo",
    "draft-folder",
    "thread-a",
    "session-b",
    "Retry the failing gateway test",
    "检查引言的引用",
)


@pytest.fixture(autouse=True)
def isolated_hosts(tmp_path, monkeypatch):
    """Names come from fixtures, never the real Codex or Claude Code homes."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))


def compress(path, host, session, before, after, context):
    request_id = str(uuid.uuid4())
    activity = RequestActivity(path)
    activity.start(request_id, host, session)
    activity.finish(
        request_id,
        state="prepared",
        before_tokens=before,
        after_tokens=after,
        context_input_tokens=context,
    )
    UsageStore(path).record(
        {
            "request_id": request_id,
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": "fixture",
        }
    )


def unchanged(path, host, session, reason, state="passthrough"):
    request_id = str(uuid.uuid4())
    activity = RequestActivity(path)
    activity.start(request_id, host, session)
    activity.finish(request_id, state=state, reason=reason)


def snapshot(path, host, session, task):
    prepared = SimpleNamespace(
        compilation=SimpleNamespace(
            compiled_memory=f"Evidence for {task}.",
            stats=SimpleNamespace(
                token_budget=1000, input_tokens=2000, output_tokens=500, tokenizer="fixture"
            ),
        )
    )
    ContextLibrary(path).save(
        prepared, task=task, source="automatic_request", host=host, session_id=session
    )


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "memory.sqlite3"
    compress(path, "codex", "thread-a", 50_000, 30_000, context=150_000)  # 40% smaller
    compress(path, "codex", "thread-a", 40_000, 39_800, context=8_000)  # 0.5%
    compress(path, "claude", "session-b", 10_000, 9_000, context=1_200_000)  # 10%
    snapshot(path, "codex", "thread-a", "Retry the failing gateway test")
    snapshot(path, "claude", "session-b", "检查引言的引用")
    unchanged(path, "codex", "thread-a", "history_below_threshold")
    unchanged(path, "codex", "thread-a", "native_compaction")
    unchanged(path, "claude", "session-b", "subagent_request")
    unchanged(path, "codex", "thread-a", "client_disconnected", state="failed")
    unchanged(path, "codex", "thread-a", "a_reason_from_a_newer_gateway")
    return path


def report_for(path, period="all", **options):
    return analysis_report(path, period, names=NAMES, reference=REFERENCE, detected={}, **options)


def test_conversations_and_kinds_of_work_ranked_by_tokens_saved(db):
    report = report_for(db)
    first, second = report["conversations"]
    assert (first["title"], first["category"], first["host"]) == (
        "Fix the gateway bug",
        "coding",
        "codex",
    )
    assert (first["tokens_saved"], first["compressions"], first["contexts"]) == (20_200, 2, 1)
    assert first["money"] == pytest.approx(20_200 * 2.0 / 1_000_000)
    assert (second["title"], second["category"], second["tokens_saved"]) == (
        "润色论文引言",
        "paper",
        1_000,
    )
    totals = report["totals"]
    assert totals["tokens_saved"] == 21_200 and totals["compressions"] == 3
    assert totals["conversations"] == 2 and totals["unattributed_tokens"] == 0
    assert [row["category"] for row in report["categories"]] == ["coding", "paper"]
    assert {row["host"]: row["compressions"] for row in report["hosts"]} == {
        "codex": 2,
        "claude": 1,
    }


def test_coverage_reductions_and_stages(db):
    report = report_for(db)
    assert {row["group"]: row["requests"] for row in report["coverage"]} == {
        "compressed": 3,
        "host_managed": 1,
        "short": 1,
        "unsupported": 1,
        "auxiliary": 1,
        "switched_off": 0,
        "failed": 1,
    }
    assert report["totals"]["requests"] == 8
    assert report["totals"]["compressed_share"] == pytest.approx(3 / 8)
    assert [row["requests"] for row in report["reductions"]] == [1, 0, 0, 1, 1, 0]
    assert [row["compilations"] for row in report["stages"]] == [1, 0, 1, 1]


@pytest.mark.parametrize(
    ("state", "reason", "group"),
    [
        ("prepared", None, "compressed"),
        ("prepared", "replayed_prefix", "compressed"),
        ("passthrough", "native_compaction_active", "host_managed"),
        ("passthrough", "history_fits_memory_budget", "short"),
        ("passthrough", "subagent_request", "auxiliary"),
        ("passthrough", "session_disabled", "switched_off"),
        ("passthrough", "a_reason_from_a_newer_gateway", "unsupported"),
        ("failed", "upstream_failed", "failed"),
        ("passthrough", "client_disconnected", "failed"),
    ],
)
def test_coverage_groups(state, reason, group):
    assert coverage_group(state, reason) == group


def test_period_leaves_out_older_activity(db):
    later = datetime.now(timezone.utc) + timedelta(days=30)
    report = report_for(db, "7d", now=later)
    assert report["conversations"] == [] and report["categories"] == []
    assert report["totals"]["tokens_saved"] == 0
    assert report["totals"]["requests"] == 0 and report["totals"]["compressed_share"] is None
    assert not any(row["requests"] for row in report["reductions"])
    assert not any(row["compilations"] for row in report["stages"])


def test_missing_database_is_an_empty_report_and_is_not_created(tmp_path):
    path = tmp_path / "absent.sqlite3"
    report = report_for(path)
    assert report["conversations"] == [] and report["totals"]["tokens_saved"] == 0
    assert not path.exists()


def test_feedback_keeps_kinds_and_counts_without_names_folders_tasks_or_ids(db):
    report = report_for(db)
    payload = feedback_payload(report, comment="  Works well  ", system="Windows")
    markdown = feedback_markdown(payload)
    with closing(sqlite3.connect(db)) as connection:
        ids = [row[0] for row in connection.execute("SELECT request_id FROM tomc_request_activity")]
    ids += [record["id"] for record in ContextLibrary(db).list()]
    for secret in (*SECRETS, *ids):
        assert secret not in markdown
    assert [row["label"] for row in payload["conversations"]] == ["coding #1", "paper #1"]
    assert set(payload["conversations"][0]) == {
        "label",
        "category",
        "host",
        "compressions",
        "contexts",
        "tokens_saved",
    }
    assert payload["comment"] == "Works well" and "## Comment\n\nWorks well" in markdown
    assert payload["totals"]["money_usd"] == pytest.approx(0.0424)
    data = markdown.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(data) == payload


def test_feedback_uses_corrected_kinds_and_bounds_free_text(db):
    report = report_for(db)
    key = report["conversations"][1]["key"]
    payload = feedback_payload(report, categories={key: "writing"}, comment="x" * 5000)
    assert [row["label"] for row in payload["conversations"]] == ["coding #1", "writing #1"]
    assert [row["category"] for row in payload["categories"]] == ["coding", "writing"]
    assert len(payload["comment"]) == MAX_COMMENT
    # Only known codes are reported; anything else becomes "other".
    payload = feedback_payload(report, categories={key: "a private project name"})
    assert payload["conversations"][1]["category"] == "other"
    assert "a private project name" not in feedback_markdown(payload)


def test_feedback_lists_at_most_twenty_conversations_but_counts_all(db):
    report = report_for(db)
    template = report["conversations"][0]
    report["conversations"] = [
        {**template, "key": ("other-host", f"t{i}"), "host": "other-host"} for i in range(25)
    ]
    payload = feedback_payload(report)
    assert len(payload["conversations"]) == MAX_CONVERSATIONS
    assert payload["categories"] == [
        {
            "category": "coding",
            "conversations": 25,
            "compressions": 50,
            "tokens_saved": 25 * 20_200,
        }
    ]
    assert {row["host"] for row in payload["conversations"]} == {"other"}


def test_feedback_link_fills_the_github_new_file_page(db):
    markdown = feedback_markdown(feedback_payload(report_for(db)))
    name = feedback_filename("2026-10-24")
    assert re.fullmatch(r"feedback/reports/2026-10-24-[0-9a-f]{8}\.md", name)
    assert name != feedback_filename("2026-10-24")
    parts = urlsplit(feedback_url(markdown, name))
    assert (parts.scheme, parts.netloc, parts.path) == (
        "https",
        "github.com",
        "/ZipengWu365/TOMC/new/main",
    )
    assert parse_qs(parts.query) == {"filename": [name], "value": [markdown]}
    assert feedback_url("x" * MAX_URL, name) is None
    page = urlsplit(feedback_page(name))
    assert page.path == "/ZipengWu365/TOMC/new/main"
    assert parse_qs(page.query) == {"filename": [name]}
