"""Offscreen translation contracts using an isolated store and no model calls."""

import os
import re
import sqlite3
from copy import deepcopy
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QRect  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from tomc import usage_widget_qt  # noqa: E402
from tomc.session_store import SessionStore  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    load_preview_fonts()
    yield app


def record(store, counter="fixture", before=1000, after=200):
    store.record(
        {
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": counter,
        }
    )


@pytest.fixture
def widget(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    UiLanguage(path).set_language("zh")
    record(UsageStore(path))
    monkeypatch.setattr(
        usage_widget_qt,
        "load_pricing",
        lambda: {"rate": 15, "label": "Opus 5.5", "model": "fixture", "mode": "input"},
    )
    widget = Companion(path, test_mode=True, connect_quota=False)
    widget.timer.stop()
    yield widget
    widget.close()
    widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main_texts(widget):
    fields = [
        widget,
        widget.art,
        widget.card,
        widget.caption,
        widget.number,
        widget.latest,
        widget.close_button,
        widget.progress,
        widget.details,
    ]
    fields += widget.details.findChildren(QLabel) + widget.details.findChildren(QPushButton)
    texts = []
    for item in fields:
        texts.extend([item.toolTip(), item.accessibleName()])
        if isinstance(item, (QLabel, QPushButton)):
            texts.append(item.text())
    texts.extend(action.text() for action in widget.pet_menu.actions())
    # The two permanent language names intentionally remain readable in either language.
    return [text.replace("中文 / English", "").replace("中文", "") for text in texts]


def assert_english(widget):
    assert not [text for text in main_texts(widget) if re.search(r"[\u3400-\u9fff]", text)]


def test_background_session_switches_never_open_notices(widget, monkeypatch):
    notices = []
    monkeypatch.setattr(widget.session_notice, "present", notices.append)
    for event in ("model_request", "Stop", "PreToolUse", "activity", "setting"):
        for host in ("codex", "claude"):
            widget.session_store.register(host, event, event=event)
            widget.refresh_session_state()
    assert notices == []
    assert widget.session_store.settings()["enabled"] is True


def test_explicit_session_notices_once_per_host_and_id_preserve_policy(widget, monkeypatch):
    notices = []
    monkeypatch.setattr(
        widget.session_notice,
        "present",
        lambda row: notices.append((row["host"], row["session_id"])),
    )
    for host, session_id, event in (
        ("codex", "same-id", "SessionStart"),
        ("claude", "same-id", "UserPromptSubmit"),
        ("codex", "same-id", "UserPromptSubmit"),
        ("codex", "another-id", "SessionStart"),
        ("claude", "same-id", "SessionStart"),
    ):
        widget.session_store.register(host, session_id, event=event)
        widget.refresh_session_state()
        widget.set_ui_language("en")
    assert notices == [("codex", "same-id"), ("claude", "same-id"), ("codex", "another-id")]
    widget.session_store.set_enabled("codex", "another-id", False)
    widget.session_store.update_settings(enabled=False)
    widget.refresh_session_state()
    assert len(notices) == 3
    assert widget.session_store.settings()["enabled"] is False
    assert widget.session_store.get("codex", "another-id")["enabled"] is False


def test_user_submit_after_model_request_can_notify_without_identity_switch(widget, monkeypatch):
    notices = []
    monkeypatch.setattr(widget.session_notice, "present", notices.append)
    widget.session_store.register("codex", "a", event="model_request")
    widget.refresh_session_state()
    sequence = widget.session_event_seq
    widget.session_store.register("codex", "a", event="UserPromptSubmit")
    widget.refresh_session_state()
    assert widget.session_event_seq == sequence
    assert len(notices) == 1


@pytest.mark.parametrize("read_fails_initially", [False, True])
def test_session_notice_startup_baseline_does_not_replay_old_event(
    app, tmp_path, monkeypatch, read_fails_initially
):
    from tomc.context_library_qt import SessionNotice

    path = tmp_path / "startup.sqlite3"
    SessionStore(path).register("codex", "old", event="SessionStart")
    notices = []
    monkeypatch.setattr(SessionNotice, "present", lambda self, row: notices.append(row))
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    original = SessionStore.active
    if read_fails_initially:

        def locked(self):
            raise sqlite3.OperationalError("fixture")

        monkeypatch.setattr(SessionStore, "active", locked)
    pet = Companion(path, test_mode=True, connect_quota=False)
    pet.timer.stop()
    try:
        monkeypatch.setattr(SessionStore, "active", original)
        pet.refresh_session_state()
        pet.set_ui_language("en")
        assert notices == []
        pet.session_store.register("codex", "old", event="UserPromptSubmit")
        pet.refresh_session_state()
        assert len(notices) == 1
    finally:
        pet.close()
        pet.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_visible_language_switch_persists_without_touching_policy_or_replaying_animation(
    widget, app, monkeypatch
):
    sessions = SessionStore(widget.store.path)
    sessions.register("codex", "fixture-session")
    sessions.set_enabled("codex", "fixture-session", False)
    sessions.update_settings(save_contexts=False)
    policy = sessions.settings(), sessions.get("codex", "fixture-session")
    before = widget.store.path.read_bytes()
    played = []
    monkeypatch.setattr(widget.art, "collect", lambda: played.append(True))
    assert widget.details.language_buttons["en"].text() == "English"
    widget.details.language_buttons["en"].click()
    app.processEvents()
    assert widget.language.code == "en"
    assert UiLanguage(widget.store.path).code == "en"
    assert (sessions.settings(), sessions.get("codex", "fixture-session")) == policy
    assert widget.store.path.read_bytes() == before
    assert not played and not widget.pending_reports
    assert widget.details.total.text() == "800"
    assert widget.details.caption.text() == "Tokens saved"
    assert widget.details.money_caption.text() == "Money saved"
    assert widget.details.language_buttons["en"].isChecked()
    assert widget.details.library_button.text() == "All records ›"
    assert widget.details.price_button.text() == "Models && pricing ›"
    assert widget.library_action.text() == "Contexts && handoff"
    assert_english(widget)
    widget.details.language_buttons["zh"].click()
    assert widget.details.caption.text() == "节省 tokens"
    assert widget.details.total.text() == "800"


def test_dashboard_sums_counters_and_values_unattributed_savings_at_the_reference(widget):
    assert widget.details.total.text() == "800"
    # No request model or host is known, so the reference rate applies: 800 × $15 / 1M.
    assert widget.details.money.text() == "$0.01"
    record(widget.store, counter="another-counter")
    widget.refresh()
    assert widget.details.total.text() == "1,600"
    assert widget.details.money.text() == "$0.02"
    assert widget.details.stats.text() == "2 次压缩 · 平均每次节省 800 tokens"
    widget.set_ui_language("en")
    assert widget.details.stats.text() == "2 compressions · 800 tokens saved each on average"
    assert_english(widget)


def test_live_quota_host_and_error_states_retranslate(widget, monkeypatch):
    widget.details.set_quota(
        {
            "status": "ready",
            "windows": [
                {"bucket": "codex", "period": "5小时", "remaining": 72},
                {"bucket": "codex", "period": "本周", "remaining": 84},
            ],
        }
    )
    widget.set_ui_language("en")
    assert widget.details.quota_title.text() == "Codex 5 hours"
    assert widget.details.quota_value.text() == "72% left"
    assert "This week" in widget.details.quota_value.toolTip()
    assert_english(widget)
    widget.set_host("claude")
    assert widget.details.quota_title.text() == "Claude allowance"
    widget.set_ui_language("zh")
    assert widget.details.quota_title.text() == "Claude 额度"

    def failed(*args):
        raise sqlite3.OperationalError("fixture")

    monkeypatch.setattr(widget.store, "summary", failed)
    widget.set_ui_language("en")
    assert widget.details.total.text() == "Unavailable"
    assert widget.latest.text() == "Read failed · Retrying"
    assert_english(widget)


def test_request_and_missing_output_states_are_english(widget):
    widget.set_ui_language("en")
    widget.preparing_request = {"active_count": 2}
    widget.show_request_busy()
    assert widget.number.text() == "Checking"
    assert widget.latest.text() == "Checking 2 requests"
    widget.report_text({"usable": False})
    assert widget.number.text() == "No usable output"
    assert_english(widget)


def test_unknown_busy_waits_for_real_context_length_then_animates_once(widget, monkeypatch):
    assert widget.growth_opacity < 1
    assert widget.art.phase is None
    # Isolated fixture database only; the production event stream is never used.
    widget.request_activity.start("fixture-request", "codex", "fixture-session")
    widget.refresh_request_activity()
    assert widget.art.phase is None and widget.art.level == 1
    assert not widget.animated_request_ids
    assert widget.materialization.opacity() == 1
    widget.request_activity.finish(
        "fixture-request",
        state="prepared",
        reason="fixture",
        before_tokens=500000,
        after_tokens=200,
        context_input_tokens=15000,
    )
    widget.refresh_request_activity()
    assert widget.art.phase is not None and widget.art.level == 2
    animation_id = widget.request_animation_id
    seen_ids = list(widget.animated_request_ids)
    widget.set_ui_language("en")
    assert widget.art.phase is not None and widget.request_animation_id == animation_id
    assert list(widget.animated_request_ids) == seen_ids
    assert widget.materialization.opacity() == 1
    widget.art.animation_timer.stop()
    widget.art.phase = None
    widget.finish_collection()
    assert widget.caption.text() == "Context compressed"
    assert widget.number.text() == "Stage 2/4"
    assert widget.latest.text() == "Compressed 15,000 tokens"
    widget.hide_report()
    assert widget.art.phase is None and widget.request_animation_id is None
    assert widget.art.level == 2
    assert widget.materialization.opacity() == usage_widget_qt.request_stage(15000)["opacity"]
    played = []
    monkeypatch.setattr(widget.art, "collect", lambda: played.append(True))
    widget.store.record(
        {
            "request_id": "fixture-request",
            "usable": True,
            "input_tokens": 500000,
            "memory_tokens": 200,
            "reduced_tokens": 499800,
            "counter": "regex-request-json-v1",
            "context_input_tokens": 15000,
        }
    )
    widget.refresh()
    assert not played and widget.art.level == 2
    # The numeric receipt states the saving directly, with the compressed context length.
    assert widget.caption.text() == "Demo · Saved"
    assert widget.number.text() == "499,800 tokens"
    assert widget.latest.text() == "Compressed 15,000 tokens"
    assert "not" not in widget.card.toolTip().lower()


def test_dashboard_scrolls_without_clipping_on_a_short_screen(widget, app, monkeypatch):
    widget.set_ui_language("en")
    monkeypatch.setattr(
        widget.details,
        "screen",
        lambda: SimpleNamespace(availableGeometry=lambda: QRect(0, 0, 600, 360)),
    )
    widget.show_details()
    app.processEvents()
    widget.details.resize_to_content()
    app.processEvents()
    assert widget.details.height() <= 360 - 24
    assert widget.details.scroll_area.verticalScrollBar().maximum() > 0
    body = widget.details.body
    assert body.height() >= usage_widget_qt.Details.layout_height(body.layout(), body.width())
    assert widget.details.language_buttons["en"].isVisible()
    assert widget.details.quit_button.isVisible()


@pytest.mark.parametrize(
    "length,level",
    [(0, 1), (9999, 1), (10000, 2), (99999, 2), (100000, 3), (999999, 3), (1000000, 4)],
)
def test_current_context_length_selects_stage_not_cumulative_totals(
    widget, monkeypatch, length, level
):
    summary = deepcopy(widget.summary)
    summary["growth"] = [
        {"counter": "first-counter", "net_tokens": 90000000, "peak_net_tokens": 90000000},
        {"counter": "second-counter", "net_tokens": 90000000, "peak_net_tokens": 90000000},
    ]
    summary["last_preparation"]["context_input_tokens"] = length
    monkeypatch.setattr(widget.store, "summary", lambda period: summary)
    celebrations = []
    monkeypatch.setattr(widget.oasis, "start", lambda: celebrations.append(True))
    widget.last_signature = None
    widget.refresh()
    state = usage_widget_qt.growth_state(summary, widget.language)
    assert not state["mixed"] and state["level"] == level
    assert widget.details.stage.text() == f"Lv.{level}"
    assert widget.art.level == level
    assert widget.details.progress.value() == round(state["progress"] * 1000)
    assert not widget.details.progress.isHidden()
    assert widget.materialization.opacity() == state["opacity"]
    widget.set_ui_language("en")
    assert widget.details.stage.text() == f"Lv.{level}"
    assert_english(widget)
    assert not celebrations


def test_each_queued_report_uses_its_own_length_and_restores_latest_idle(widget, monkeypatch):
    lengths = [1000000, 9999, 100000, 10000]
    reports = [
        {
            "usable": True,
            "input_tokens": 2000000,
            "memory_tokens": 200,
            "reduced_tokens": 1999800,
            "counter": "regex-request-json-v1",
            "context_input_tokens": length,
            "request_id": f"queued-{i}",
            "animate_prepared": True,
        }
        for i, length in enumerate(lengths)
    ]
    seen = []

    def collect():
        seen.append(widget.art.level)
        widget.art.phase = 0

    monkeypatch.setattr(widget.art, "collect", collect)
    widget.pending_reports.extend(reports)
    widget.start_collection()
    for index, level in enumerate([4, 1, 3, 2]):
        assert widget.art.level == level
        if index == 0:
            widget.set_ui_language("en")
            assert widget.art.level == 4 and widget.art.phase == 0
        widget.art.phase = None
        widget.finish_collection()
        widget.hide_report()
    assert seen == [4, 1, 3, 2]
    assert widget.art.level == 1  # Latest actual store entry is the 1,000-token fixture.


def test_unknown_replay_reports_counts_without_playing_another_compilation(widget, monkeypatch):
    played = []
    monkeypatch.setattr(widget.art, "collect", lambda: played.append(True))
    widget.pending_reports.append(
        {
            "request_id": "replay",
            "usable": True,
            "input_tokens": 2000000,
            "memory_tokens": 200,
            "reduced_tokens": 1999800,
            "counter": "regex-request-json-v1",
            "context_input_tokens": None,
        }
    )
    widget.start_collection()
    assert not played and not widget.animated_request_ids
    assert widget.art.level == 1
    assert widget.details.stage.text() == "长度待定"


def test_startup_does_not_replay_previously_prepared_request(widget, monkeypatch):
    widget.request_activity.start("historical", "codex", "fixture-session")
    widget.request_activity.finish("historical", state="prepared", context_input_tokens=1000000)
    widget.prepared_cursor = widget.request_activity.prepared_cursor()
    played = []
    monkeypatch.setattr(widget.art, "collect", lambda: played.append(True))
    widget.refresh_request_activity()
    assert not played and not widget.pending_reports
    assert widget.prepared_cursor == 1


def test_all_concurrent_preparations_play_once_even_with_other_request_busy(widget, monkeypatch):
    played = []

    def collect():
        played.append((widget.active_report["request_id"], widget.art.level))
        widget.art.phase = 0

    monkeypatch.setattr(widget.art, "collect", collect)
    for index, length in enumerate((20000, 200000, 2000000)):
        request_id = f"concurrent-{index}"
        widget.request_activity.start(request_id, "codex", "fixture-session")
        widget.request_activity.finish(request_id, state="prepared", context_input_tokens=length)
    widget.request_activity.start("still-preparing", "claude", "other-session")
    widget.refresh_request_activity()
    assert len(widget.pending_reports) == 2
    for expected in (2, 3, 4):
        assert widget.art.level == expected and widget.art.phase == 0
        widget.art.phase = None
        widget.finish_collection()
        assert widget.report_timer.isActive()
        widget.refresh_request_activity()
        assert widget.report_timer.isActive()  # Busy polling must not stop queue advancement.
        widget.hide_report()
    assert played == [(f"concurrent-{i}", level) for i, level in enumerate((2, 3, 4))]
    widget.refresh_request_activity()
    assert len(played) == 3 and widget.art.level == 1


def test_mcp_burst_over_old_retention_limit_plays_every_event(widget, monkeypatch):
    played = []

    def collect():
        played.append(widget.active_report["seq"])
        widget.art.phase = 0

    monkeypatch.setattr(widget.art, "collect", collect)
    for _ in range(70):
        record(widget.store, before=20000, after=10000)
    widget.refresh()
    for _ in range(70):
        assert widget.art.phase == 0
        widget.art.phase = None
        widget.finish_collection()
        widget.hide_report()
    assert len(played) == len(set(played)) == 70
    widget.refresh()
    assert len(played) == 70


def test_numeric_receipts_merge_with_prepared_queue_and_late_receipts_do_not_replay(
    widget, monkeypatch
):
    played = []

    def collect():
        played.append(widget.active_report["request_id"])
        widget.art.phase = 0

    monkeypatch.setattr(widget.art, "collect", collect)
    prepared = {
        "request_id": "paired",
        "usable": True,
        "stage_only": True,
        "context_input_tokens": 15000,
    }
    receipt = {
        "request_id": "paired",
        "usable": True,
        "input_tokens": 2000000,
        "memory_tokens": 500,
        "reduced_tokens": 1999500,
        "counter": "regex-request-json-v1",
        "context_input_tokens": 15000,
    }
    widget.enqueue_report(prepared)
    widget.enqueue_report(receipt)
    assert len(widget.pending_reports) == 1
    widget.start_collection()
    assert played == ["paired"] and widget.art.level == 2
    widget.enqueue_report(receipt)
    assert not widget.pending_reports
    widget.art.phase = None
    widget.finish_collection()
    widget.hide_report()
    # More than 128 intervening IDs must not evict the exactly-once decision.
    widget.animated_request_ids.update(f"later-{index}" for index in range(150))
    widget.enqueue_report(receipt)
    widget.start_collection()
    assert played == ["paired"]


def test_transient_usage_read_failure_preserves_real_animation_queue(widget, monkeypatch):
    widget.pending_reports.extend(
        [
            {
                "request_id": str(index),
                "usable": True,
                "stage_only": True,
                "context_input_tokens": 15000,
            }
            for index in range(2)
        ]
    )
    monkeypatch.setattr(widget.art, "collect", lambda: setattr(widget.art, "phase", 0))
    widget.start_collection()

    def unavailable(*args):
        raise sqlite3.OperationalError("fixture")

    monkeypatch.setattr(widget.store, "summary", unavailable)
    widget.refresh()
    assert widget.art.phase == 0 and widget.active_report["request_id"] == "0"
    assert len(widget.pending_reports) == 1


@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("receipt_length, expected", [(None, 15000), (100000, 100000)])
def test_numeric_receipt_preserves_known_prepared_length(
    widget, monkeypatch, active, receipt_length, expected
):
    monkeypatch.setattr(widget.art, "collect", lambda: setattr(widget.art, "phase", 0))
    widget.enqueue_report(
        {"request_id": "paired", "usable": True, "stage_only": True, "context_input_tokens": 15000}
    )
    if active:
        widget.start_collection()
    widget.enqueue_report(
        {
            "request_id": "paired",
            "usable": True,
            "input_tokens": 2000000,
            "memory_tokens": 500,
            "reduced_tokens": 1999500,
            "counter": "regex-request-json-v1",
            "context_input_tokens": receipt_length,
        }
    )
    if not active:
        widget.start_collection()
    widget.restore_displayed_stage()
    assert widget.active_report["context_input_tokens"] == expected
    assert widget.art.level == (2 if expected == 15000 else 3)
    assert widget.art.phase == 0


def test_locked_startup_cursors_retry_baseline_without_replaying_history(
    app, tmp_path, monkeypatch
):
    path = tmp_path / "locked.sqlite3"
    record(UsageStore(path))
    activity = usage_widget_qt.RequestActivity(path)
    activity.start("old", host="codex")
    activity.finish("old", state="prepared", reason="optimized", context_input_tokens=15000)
    original_prepared = usage_widget_qt.RequestActivity.prepared_cursor
    original_usage = UsageStore.event_cursor

    def locked(*args):
        raise sqlite3.OperationalError("fixture locked")

    monkeypatch.setattr(usage_widget_qt.RequestActivity, "prepared_cursor", locked)
    monkeypatch.setattr(UsageStore, "event_cursor", locked)
    pet = Companion(path, test_mode=True, connect_quota=False)
    pet.timer.stop()
    try:
        assert pet.prepared_cursor is None and pet.event_cursor is None
        monkeypatch.setattr(usage_widget_qt.RequestActivity, "prepared_cursor", original_prepared)
        monkeypatch.setattr(UsageStore, "event_cursor", original_usage)
        played = []
        monkeypatch.setattr(pet.art, "collect", lambda: played.append(True))
        pet.refresh()
        assert pet.prepared_cursor == activity.prepared_cursor()
        assert pet.event_cursor == pet.store.event_cursor()
        assert not played and not pet.pending_reports and pet.active_report is None
        activity.start("new", host="codex")
        activity.finish("new", state="prepared", reason="optimized", context_input_tokens=15000)
        pet.refresh()
        assert played == [True] and pet.active_report["request_id"] == "new"
    finally:
        pet.close()
        pet.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_activity_read_failure_clears_stale_busy_and_preserves_animation(widget, monkeypatch):
    widget.preparing_request = {"request_id": "busy", "context_input_tokens": None}
    widget.show_request_busy()

    def unavailable(*args):
        raise sqlite3.OperationalError("fixture")

    monkeypatch.setattr(widget.request_activity, "active", unavailable)
    widget.refresh_request_activity()
    assert widget.preparing_request is None
    assert widget.number.text() == "状态未知"
    assert widget.art.phase is None and widget.art.level == 1
    assert widget.materialization.opacity() == 0.35
    widget.pending_reports.extend(
        [
            {
                "request_id": str(index),
                "usable": True,
                "stage_only": True,
                "context_input_tokens": 15000,
            }
            for index in range(2)
        ]
    )
    monkeypatch.setattr(widget.art, "collect", lambda: setattr(widget.art, "phase", 0))
    widget.refresh_request_activity()
    assert widget.art.phase == 0 and widget.art.level == 2
    widget.preparing_request = {"request_id": "busy"}
    widget.refresh_request_activity()
    assert widget.preparing_request is None
    assert widget.active_report["request_id"] == "0" and len(widget.pending_reports) == 1
    assert widget.art.phase == 0 and widget.art.level == 2
    assert widget.materialization.opacity() == 1
