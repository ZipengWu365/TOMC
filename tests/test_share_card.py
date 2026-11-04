"""The weekly share card: honest numbers, no conversation names, a watermark on demo data."""

import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tomc import share_card
from tomc.context_library import ContextLibrary
from tomc.request_activity import RequestActivity
from tomc.savings import savings_report
from tomc.share_card import card_data, card_strings, card_text, summary_line
from tomc.usage import UsageStore

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
MCP = "regex-v1 (estimate)"
GATEWAY = "regex-request-json-v1 (estimate)"
REFERENCE = {"rate": 2.0, "label": "Fixture model", "model": "fixture", "mode": "input"}
NEVER = ("水", "电", "树", "water", "electric", "tree", "kwh", "co2", "碳")
SECRETS = ("Fix the gateway bug", "private-repo", "thread-a", "Retry the failing gateway test")


@pytest.fixture(autouse=True)
def isolated_hosts(tmp_path, monkeypatch):
    """Conversation names come from fixtures, never the real Codex or Claude Code homes."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))


def seed(path, rows, now=NOW):
    """rows: (days ago, counter, tokens before, tokens after[, context input tokens])."""
    with closing(sqlite3.connect(path)) as db, db:
        UsageStore(path)._schema(db)
        for days_ago, counter, before, after, *context in rows:
            day = (now - timedelta(days=days_ago)).date().isoformat()
            db.execute(
                "INSERT INTO context_usage_daily VALUES (?,?,1,1,?,?,?) "
                "ON CONFLICT(day,counter) DO UPDATE SET calls=calls+1, "
                "usable_calls=usable_calls+1, increased_calls=increased_calls+excluded.increased_calls, "
                "input_tokens=input_tokens+excluded.input_tokens, "
                "memory_tokens=memory_tokens+excluded.memory_tokens",
                (day, counter, int(after > before), before, after),
            )
            db.execute(
                "INSERT INTO context_usage_events (recorded_at,counter,input_tokens,memory_tokens,"
                "usable,request_id,context_input_tokens) VALUES (?,?,?,?,1,NULL,?)",
                (f"{day}T12:00:00+00:00", counter, before, after, context[0] if context else None),
            )
    return path


def week(path, counter=MCP, count=12):
    """A normal week: savings every day, the most on day 3."""
    rows = [
        (i % 7, counter, 40_000 + 9_000 * (i % 7 == 3), 24_000, 120_000 if i == 0 else 30_000)
        for i in range(count)
    ]
    return seed(path, rows)


def data_for(path, **options):
    options.setdefault("now", NOW)
    options.setdefault("reference", REFERENCE)
    options.setdefault("detected", {})
    return card_data(path, options.pop("language", "zh"), **options)


def strings(data, **options):
    return "\n".join(card_strings(data, **options))


def assert_honest(data, **options):
    text = strings(data, **options)
    words = share_card.TEXT[data["language"]]
    assert words["fixed"] in text
    assert words["counter"].split("{")[0] in text
    assert not any(word in text.lower() for word in NEVER)
    assert "$0.00" not in text and "$0 " not in text
    return text


def test_empty_database_says_so_without_numbers(tmp_path):
    path = tmp_path / "absent.sqlite3"
    data = data_for(path)
    assert data["state"] == "empty" and data["tokens_saved"] == 0 and data["money"] is None
    assert not path.exists()
    text = assert_honest(data)
    assert "本周还没有记录" in text
    assert "%" not in text and "$" not in text
    assert "这 7 天还没有少发的记录" in text
    assert len(data["daily"]) == 7 and data["daily"][-1]["today"]
    assert data["range"] == "10/23–10/29"


def test_fewer_than_five_usable_records_gives_no_percentage(tmp_path):
    path = seed(tmp_path / "m.sqlite3", [(0, MCP, 10_000, 4_000)] * 3)
    data = data_for(path)
    assert data["state"] == "few" and data["share"] is None and data["usable"] == 3
    text = assert_honest(data)
    assert "样本太少" in text and "%" not in text
    assert "18K" in text and "≈" in text


def test_a_normal_week(tmp_path):
    path = week(tmp_path / "m.sqlite3")
    data = data_for(path)
    saved = sum(40_000 + 9_000 * (i % 7 == 3) - 24_000 for i in range(12))
    before = sum(40_000 + 9_000 * (i % 7 == 3) for i in range(12))
    assert data["state"] == "saved" and data["tokens_saved"] == saved
    assert data["share"] == pytest.approx(saved / before)
    assert data["money"] == pytest.approx(saved * 2.0 / 1_000_000)
    assert data["money_models"] == ["Fixture model"]
    assert data["preparations"] == 12 and data["source"] == "mcp"
    assert data["coverage"] == {"kind": "preparations", "total": 12, "done": 12}
    assert data["stage"] == 2  # about 210,000 tokens saved in total: past 100,000
    assert data["demo"] is False and data["other_sources"] == []
    days = data["daily"]
    assert [row["today"] for row in days] == [False] * 6 + [True]
    assert sum(row["tokens_saved"] for row in days) == saved
    text = assert_honest(data)
    assert "估算" in text and "按标价估算 ≈ $" in text
    assert "按 Fixture model 标价估算" in text
    assert "只统计 TOMC 工具调用" in text
    assert "12 次整理里 12 次变短" in text and "%（估算）" in text
    assert card_text(data)["number"] == "210K"


def test_single_source_matches_the_savings_dashboard(tmp_path):
    path = week(tmp_path / "m.sqlite3")
    data = data_for(path)
    report = savings_report(path, "7d", now=NOW, reference=REFERENCE, detected={})
    assert data["tokens_saved"] == report["tokens_saved"]
    assert data["money"] == pytest.approx(report["money"])
    assert data["preparations"] == report["preparations"]


def test_unknown_money_is_hidden_never_zero(tmp_path):
    path = week(tmp_path / "m.sqlite3")
    data = data_for(path, reference=None)
    assert data["money"] is None and data["money_models"] == []
    text = assert_honest(data)
    assert "$" not in text and "标价估算" not in text


def test_the_user_can_hide_money_and_model_but_not_the_fixed_footer(tmp_path):
    data = data_for(week(tmp_path / "m.sqlite3"))
    text = assert_honest(data, hide_money=True)
    assert "$" not in text and "Fixture model" not in text
    assert "上下文估算，不等于账单或额度节省" in text
    assert "≈ $" not in summary_line(data, hide_money=True)
    assert "≈ $" in summary_line(data)


def test_unpriced_tokens_are_named_not_counted(tmp_path):
    path = tmp_path / "m.sqlite3"
    for model in ("fixture-a", "fixture-a", "fixture-a", "fixture-a", "no-such-model"):
        compress(path, "codex", "thread-a", 50_000, 30_000, model=model)
    catalog = {
        "schema": 1,
        "providers": {
            "openai": {
                "verified_at": "2026-10-01",
                "rates": [
                    {
                        "model": "fixture-a",
                        "label": "Fixture A",
                        "provider": "openai",
                        "variant": "standard-short",
                        "input": 1.0,
                        "cached": 0.1,
                    }
                ],
            }
        },
    }
    data = card_data(
        path, "zh", now=datetime.now(timezone.utc), catalog=catalog, reference=None, detected={}
    )
    assert data["money"] == pytest.approx(80_000 * 1.0 / 1_000_000)
    assert data["unpriced_tokens"] == 20_000 and data["money_models"] == ["Fixture A"]
    text = assert_honest(data)
    assert "另有 ≈ 20K tokens 找不到标价，没算进金额" in text
    assert "按 Fixture A 标价估算" in text


@pytest.mark.parametrize(
    ("after", "state", "words"),
    [(10_000, "none_saved", "短对话本来就不需要压缩"), (12_000, "increased", "上下文增加")],
)
def test_no_saving_says_so_without_made_up_numbers(tmp_path, after, state, words):
    path = seed(tmp_path / "m.sqlite3", [(i % 7, MCP, 10_000, after) for i in range(8)])
    data = data_for(path)
    assert data["state"] == state and data["share"] is None and data["money"] is None
    text = assert_honest(data)
    assert "本周没省到" in text and words in text
    assert "%" not in text and "$" not in text
    # Unchanged or longer contexts are not counted as "got shorter".
    assert data["coverage"] == {"kind": "preparations", "total": 8, "done": 0}
    assert "8 次整理里 0 次变短" in text


def test_demo_counters_and_demo_flag_get_the_watermark(tmp_path):
    path = seed(tmp_path / "m.sqlite3", [(0, "demo-estimate", 106_000, 6_000)] * 6)
    data = data_for(path)
    assert data["demo"] is True
    assert card_text(data)["watermark"] == "演示数据 · DEMO DATA"
    assert "（演示数据）" in summary_line(data)
    forced = data_for(week(tmp_path / "real.sqlite3"), demo=True)
    assert forced["demo"] and card_text(forced, hide_money=True)["watermark"]
    plain = data_for(tmp_path / "real.sqlite3")
    assert card_text(plain)["watermark"] is None


def test_counting_sources_are_listed_separately_never_added(tmp_path):
    rows = [(i % 7, MCP, 3_000, 2_000) for i in range(10)]
    rows += [(i % 7, GATEWAY, 5_000, 2_000) for i in range(6)]
    data = data_for(seed(tmp_path / "m.sqlite3", rows))
    assert data["source"] == "mcp" and data["tokens_saved"] == 10_000
    assert data["preparations"] == 10
    assert data["other_sources"] == [
        {"source": "gateway", "label": "Windows 网关测试版", "tokens_saved": 18_000, "usable": 6}
    ]
    text = assert_honest(data)
    assert "另：Windows 网关测试版 ≈ 18K tokens，口径不同，不相加" in text
    assert "28K" not in text


def compress(path, host, session, before, after, model="fixture"):
    request_id = str(uuid.uuid4())
    activity = RequestActivity(path)
    activity.start(request_id, host, session)
    activity.finish(
        request_id, state="prepared", before_tokens=before, after_tokens=after, model=model
    )
    UsageStore(path).record(
        {
            "request_id": request_id,
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": GATEWAY,
        }
    )


def test_gateway_week_shows_work_types_and_coverage_never_names(tmp_path):
    path = tmp_path / "m.sqlite3"
    for _ in range(6):
        compress(path, "codex", "thread-a", 50_000, 30_000)
    for reason in ("history_below_threshold", "native_compaction"):
        request_id = str(uuid.uuid4())
        activity = RequestActivity(path)
        activity.start(request_id, "codex", "thread-a")
        activity.finish(request_id, state="passthrough", reason=reason)
    prepared = SimpleNamespace(
        compilation=SimpleNamespace(
            compiled_memory="Evidence for the fix.",
            stats=SimpleNamespace(
                token_budget=1000, input_tokens=2000, output_tokens=500, tokenizer="fixture"
            ),
        )
    )
    ContextLibrary(path).save(
        prepared,
        task="Retry the failing gateway test",
        source="automatic_request",
        host="codex",
        session_id="thread-a",
    )
    data = card_data(path, "zh", now=datetime.now(timezone.utc), reference=REFERENCE, detected={})
    assert data["source"] == "gateway" and data["state"] == "saved"
    assert data["coverage"] == {"kind": "requests", "total": 8, "done": 6}
    assert data["top_category"]["code"] == "coding" and data["top_category"]["share"] == 1.0
    text = assert_honest(data)
    assert "8 个请求里压缩了 6 个" in text and "编程开发 ≈ 100%" in text
    assert "数据来自 Windows 网关测试版" in text
    flat = repr(data)
    for secret in SECRETS:
        assert secret not in text and secret not in flat


def test_english_card(tmp_path):
    data = data_for(week(tmp_path / "m.sqlite3"), language="en")
    text = assert_honest(data)
    assert "≈ $" in text and "at list price (estimate)" in text
    assert "Context estimate, not a bill or quota saving" in text
    assert "(estimate)" in text
    assert not any("一" <= char <= "鿿" for char in text.replace("演示数据", ""))
    assert share_card.default_filename(data) == "TOMC-weekly-report-20261029.png"


def test_number_formats():
    assert [share_card.tokens_text(n) for n in (0, 999, 1_000, 12_345, 456_000, 1_234_567)] == [
        "0",
        "999",
        "1K",
        "12.3K",
        "456K",
        "1.23M",
    ]
    assert share_card.percent_text(0.004) == "<1%"
    assert share_card.money_text(0.001) == "<$0.01"


# ---- Qt rendering and the command line ----

qt = pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.clipboard().clear()


@pytest.mark.parametrize(
    ("size", "pixels"), [("portrait", (1080, 1350)), ("landscape", (1200, 630))]
)
def test_rendered_card_size_and_every_string(app, tmp_path, size, pixels):
    from tomc.share_card_qt import render_card

    data = data_for(week(tmp_path / "m.sqlite3"))
    drawn = []
    image = render_card(data, size, drawn=drawn)
    assert (image.width(), image.height()) == pixels
    assert set(card_strings(data)) <= set(drawn)
    assert any("估算" in line for line in drawn)
    assert "演示数据 · DEMO DATA" not in drawn


def test_rendered_demo_card_has_the_watermark_and_no_names(app, tmp_path):
    from tomc.share_card_qt import render_card

    path = tmp_path / "m.sqlite3"
    for _ in range(5):
        compress(path, "codex", "thread-a", 50_000, 30_000)
    data = card_data(
        path, "zh", now=datetime.now(timezone.utc), demo=True, reference=REFERENCE, detected={}
    )
    for size in ("portrait", "landscape"):
        drawn = []
        render_card(data, size, hide_money=True, drawn=drawn)
        assert "演示数据 · DEMO DATA" in drawn
        assert not any(secret in line for line in drawn for secret in SECRETS)


def test_share_dialog_previews_copies_and_hides_money(app, tmp_path):
    from tomc.share_card_qt import show_share_card

    path = week(tmp_path / "m.sqlite3")
    parent = SimpleNamespace(test_mode=True)
    dialog = show_share_card(None, path, language="zh", demo=parent.test_mode)
    try:
        assert dialog.card_data["demo"] and dialog.image.width() == 1080
        dialog.landscape.setChecked(True)
        assert dialog.image.width() == 1200
        dialog.copy_button.click()
        assert app.clipboard().image().width() == 1200
        assert dialog.hide_money.isEnabled() == (dialog.card_data["money"] is not None)
    finally:
        dialog.close()


def test_cli_writes_a_png(tmp_path, capsys, monkeypatch):
    from tomc.cli import main

    monkeypatch.setenv("HOME", str(tmp_path))
    path = week(tmp_path / "m.sqlite3")
    out = tmp_path / "cards"
    assert main(["share-card", "--store", str(path), "--out", str(out), "--lang", "en"]) == 0
    printed = capsys.readouterr().out.splitlines()
    files = list(out.glob("TOMC-weekly-report-*.png"))
    assert len(files) == 1 and printed[0] == str(files[0].resolve())
    assert files[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert printed[1].startswith("TOMC Memory, week of")
    target = tmp_path / "wide.png"
    main(["share-card", "--store", str(path), "--out", str(target), "--landscape", "--hide-money"])
    assert target.exists() and "$" not in capsys.readouterr().out


def test_cli_explains_a_missing_pyside6(tmp_path, capsys, monkeypatch):
    import sys

    from tomc.cli import main

    monkeypatch.setitem(sys.modules, "tomc.share_card_qt", None)
    with pytest.raises(SystemExit) as raised:
        main(["share-card", "--store", str(tmp_path / "m.sqlite3"), "--out", str(tmp_path)])
    assert raised.value.code == 2
    assert "tomc-memory[widget]" in capsys.readouterr().err
    assert not list(tmp_path.glob("*.png"))
