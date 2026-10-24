"""Offscreen pet: each prepared request ID leaves queued/started/completed evidence once."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc import usage_widget_qt  # noqa: E402
from tomc.animation_receipts import AnimationReceipts  # noqa: E402
from tomc.context_library_qt import request_activity_text  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    load_preview_fonts()
    yield app


PRICING = {"rate": 15, "label": "Opus 5.5", "model": "fixture", "mode": "input"}


@pytest.fixture
def widget(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    UiLanguage(path).set_language("zh")
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: PRICING)
    widget = Companion(path, test_mode=True, connect_quota=False)
    widget.timer.stop()
    yield widget
    widget.close()
    widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def events(widget, request_id):
    return [
        (row["event"], row.get("stage"), row.get("reason"))
        for row in widget.receipts.read([request_id])
    ]


def prepare(widget, request_id, length):
    widget.request_activity.start(request_id, "codex", "fixture-session")
    widget.request_activity.finish(request_id, state="prepared", context_input_tokens=length)


def test_prepared_request_leaves_queued_started_completed_and_late_usage_is_skipped(
    widget, monkeypatch
):
    monkeypatch.setattr(widget.art, "collect", lambda: setattr(widget.art, "phase", 0))
    prepare(widget, "real-1", 250_000)
    widget.refresh_request_activity()
    assert events(widget, "real-1") == [("queued", None, None), ("started", 3, None)]
    widget.art.phase = None
    widget.finish_collection()
    widget.hide_report()
    assert events(widget, "real-1")[-1] == ("completed", 3, None)
    # The numeric usage receipt for the same request must not replay the animation.
    widget.enqueue_report(
        {
            "request_id": "real-1",
            "usable": True,
            "input_tokens": 300000,
            "memory_tokens": 90000,
            "reduced_tokens": 210000,
            "counter": "regex-request-json-v1",
            "context_input_tokens": 250_000,
        }
    )
    widget.start_collection()
    assert events(widget, "real-1")[-1] == ("skipped", 3, "already_animated")
    receipts = widget.receipts.read(["real-1"])
    assert all(row["demo"] is True for row in receipts)  # This fixture runs in test mode.
    assert {key for row in receipts for key in row} <= {
        "utc",
        "event",
        "request_id",
        "ui",
        "stage",
        "context_input_tokens",
        "reason",
        "demo",
    }


def test_shorter_next_request_steps_down_and_each_plays_once(widget, monkeypatch):
    monkeypatch.setattr(widget.art, "collect", lambda: setattr(widget.art, "phase", 0))
    for request_id, length in (("long", 1_200_000), ("short", 9_000)):
        prepare(widget, request_id, length)
    widget.refresh_request_activity()
    for request_id, stage in (("long", 4), ("short", 1)):
        assert ("started", stage, None) in events(widget, request_id)
        widget.art.phase = None
        widget.finish_collection()
        widget.hide_report()
        assert events(widget, request_id)[-1] == ("completed", stage, None)
    widget.refresh_request_activity()
    assert [event for event, _, _ in events(widget, "long")].count("started") == 1


def test_closing_mid_animation_is_recorded_and_a_new_ui_does_not_replay(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: PRICING)
    pet = Companion(path, test_mode=True, connect_quota=False)
    pet.timer.stop()
    monkeypatch.setattr(pet.art, "collect", lambda: setattr(pet.art, "phase", 0))
    prepare(pet, "cut", 50_000)
    pet.refresh_request_activity()
    pet.close()
    pet.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert [row["event"] for row in AnimationReceipts(tmp_path).read(["cut"])] == [
        "queued",
        "started",
        "interrupted",
    ]
    again = Companion(path, test_mode=True, connect_quota=False)
    again.timer.stop()
    try:
        again.refresh_request_activity()
        assert not again.pending_reports  # A restart never backfills old prepared events.
        assert [row["event"] for row in again.receipts.read(["cut"])].count("started") == 1
    finally:
        again.close()
        again.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_status_names_host_compaction_separately_from_tomc_work():
    state = {
        "state": "passthrough",
        "sent": True,
        "reason": "native_compaction_state",
        "protocol_detail": {"compaction_items": 1, "window": 2, "agent": "subagent"},
    }
    zh = request_activity_text(state, "zh")
    assert "宿主原生管理" in zh and "TOMC 本次未压缩" in zh
    assert "压缩代次 2" in zh and "1 个不透明状态项" in zh and "子代理" in zh
    en = request_activity_text(state, "en")
    assert (
        "Host-managed" in en and "compaction generation 2" in en and "1 opaque state item(s)" in en
    )
    compaction = {
        "state": "passthrough",
        "sent": True,
        "reason": "host_compaction_request",
        "protocol_detail": {"compaction_trigger": "auto", "compaction_phase": "pre_turn"},
    }
    assert request_activity_text(compaction, "en") == (
        "Request forwarded unchanged · The host's own compaction request; TOMC not involved"
        " · automatic, before the turn"
    )
    assert "自动，回合开始前" in request_activity_text(compaction, "zh")
    assert (
        request_activity_text({"state": "failed", "reason": "client_disconnected"}, "en")
        == "Request cancelled or disconnected by the host"
    )
    assert "上游连接或响应中断" in request_activity_text(
        {"state": "failed", "reason": "upstream_transport_failed"}, "zh"
    )
    # Historical rows written before the split keep their original wording.
    assert "Host native compaction retained" in request_activity_text(
        {"state": "passthrough", "sent": True, "reason": "native_compaction"}, "en"
    )
