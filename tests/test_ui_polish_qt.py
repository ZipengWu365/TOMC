"""0.3.1 desktop polish: plain status words, estimate labels, menu order and the pet capsule."""

import os
import re
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from tomc import savings, status_text, usage_widget_qt  # noqa: E402
from tomc.context_library_qt import (  # noqa: E402
    request_activity_sentence,
    request_activity_text,
    request_activity_tooltip,
)
from tomc.request_activity import RequestActivity  # noqa: E402
from tomc.savings_qt import money_caption, money_phrase, money_short, money_tip  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402

# Codes the producers emit that once leaked into the UI, plus one nobody mapped.
NAMED = [
    "short_history",
    "unsupported_prompt_options",
    "model_budget_unavailable",
    "model_window_boundary_backoff",
    "below_char_threshold",
]
CODES = sorted(set(NAMED) | set(status_text.REASONS))
CODE_SHAPE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def pet(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    UiLanguage(path).set_language("zh")
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    monkeypatch.setattr(savings, "load_detected", lambda path=None: {})
    monkeypatch.setattr(app, "quit", lambda: None)
    widget = usage_widget_qt.Companion(path, test_mode=True, connect_quota=False)
    widget.timer.stop()
    yield widget
    widget.close()
    widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("state", ["passthrough", "failed"])
@pytest.mark.parametrize("code", CODES + ["brand_new_code_from_a_future_gateway"])
def test_no_raw_status_code_reaches_visible_text(code, state, language):
    record = {"state": state, "sent": True, "reason": code}
    for text in (
        request_activity_text(record, language),
        request_activity_sentence(record, language),
    ):
        assert code not in text
        assert not CODE_SHAPE.search(text), text
    # The code itself is kept for the curious, in the tooltip only.
    assert code in request_activity_tooltip(record, language)


@pytest.mark.parametrize("code", NAMED)
def test_review_codes_have_their_own_plain_words(code):
    assert status_text.reason_text(code, "zh") and status_text.reason_text(code, "en")
    assert "宿主" not in status_text.reason_text(code, "zh")


def test_unknown_code_reads_sent_unchanged():
    record = {"state": "passthrough", "sent": True, "reason": "brand_new_code"}
    assert request_activity_sentence(record, "zh") == "已原样发送"
    assert request_activity_sentence(record, "en") == "Sent unchanged"
    assert "brand_new_code" in request_activity_tooltip(record, "en")


def test_no_mapping_uses_host_jargon():
    for zh, en in status_text.REASONS.values():
        assert "宿主" not in zh and "代理请求" not in zh
        assert not CODE_SHAPE.search(en)


def test_dashboard_status_is_one_dot_and_one_plain_sentence(pet, app):
    activity = RequestActivity(pet.store.path)
    activity.start("r-1", "codex", "s")
    activity.finish("r-1", state="passthrough", reason="short_history")
    activity.sent("r-1")
    pet.refresh()
    details = pet.details
    assert details.request_status.text() == "对话还短，不需要压缩"
    assert "short_history" in details.request_status.toolTip()
    assert details.status_dot.text() == "●"
    texts = [w.text() for w in details.findChildren(QLabel) + details.findChildren(QPushButton)]
    assert not [text for text in texts if "short_history" in text or "未取得会话事件" in text]
    # The old three-line footer is gone: no separate session-mode line remains.
    assert not hasattr(details, "mode_status")
    pet.session_store.update_settings(enabled=False)
    pet.refresh_session_state()
    assert details.request_status.text() == "TOMC 已暂停，不会压缩新请求"


@pytest.mark.parametrize(
    ("value", "zh", "en"),
    [
        (3.391, "按标价估算 ≈ $3.39", "≈ $3.39 at list price (estimate)"),
        (0.001, "按标价估算 <$0.01", "<$0.01 at list price (estimate)"),
        (None, "", ""),
    ],
)
def test_money_wording_is_always_an_estimate_and_hidden_when_unknown(value, zh, en):
    assert money_phrase(value, "zh") == zh
    assert money_phrase(value, "en") == en
    assert money_short(None) == ""
    assert "估算" in money_caption("zh") and "estimate" in money_caption("en")
    assert money_tip("zh") == "不是账单；有缓存或订阅时实际更少"
    assert money_tip("en") == "Not a bill; less with caching or a subscription"


def test_dashboard_money_label_says_estimate(pet):
    usage = UsageStore(pet.store.path)
    usage.record(
        {
            "usable": True,
            "input_tokens": 1_000_000,
            "memory_tokens": 0,
            "reduced_tokens": 1_000_000,
            "counter": "fixture",
        }
    )
    pet.pricing = {"rate": 2.0, "label": "Fixture", "model": "fixture", "mode": "input"}
    pet.details.refresh_report()
    assert "估算" in pet.details.money_caption.text()
    assert pet.details.money.text() == "≈ $2.00"
    assert "不是账单" in pet.details.money.toolTip()
    pet.set_ui_language("en")
    assert "estimate" in pet.details.money_caption.text()
    assert "Not a bill" in pet.details.money.toolTip()


def test_pricing_page_shows_the_dashboard_figure_in_the_same_words(pet, tmp_path):
    from tomc import pricing_qt

    UsageStore(pet.store.path).record(
        {
            "usable": True,
            "input_tokens": 1_000_000,
            "memory_tokens": 0,
            "reduced_tokens": 1_000_000,
            "counter": "fixture",
        }
    )
    reference = {
        "key": "anthropic:fixture:standard",
        "provider": "anthropic",
        "model": "fixture",
        "label": "Fixture",
        "variant": "standard",
        "input": 2.0,
        "cached": 0.2,
        "output": 8.0,
    }
    pet.pricing = {**reference, "mode": "input", "rate": 2.0, "host": "claude"}
    pet.details.refresh_report()
    original = pricing_qt.all_rates
    pricing_qt.all_rates = lambda: [reference]
    try:
        sheet = pricing_qt.ReferenceSheet(pet, settings_path=tmp_path / "pricing.json")
    finally:
        pricing_qt.all_rates = original
    assert pet.details.money.text() == "≈ $2.00"
    assert sheet.preview.text() == "累计 · 按标价估算 ≈ $2.00"
    assert sheet.host.itemText(sheet.host.findData("codex")) == "Codex"
    assert "模型与估价" not in sheet.basis.toPlainText()
    sheet.close()


def test_menu_keeps_quit_last_and_share_hook_is_hidden_until_wired(pet):
    actions = [action for action in pet.pet_menu.actions() if not action.isSeparator()]
    assert actions[-1] is pet.quit_action
    assert not pet.share_action.isVisible() and pet.details.share_button.isHidden()
    calls = []
    pet.set_share_handler(lambda: calls.append(True))
    assert pet.share_action.isVisible() and not pet.details.share_button.isHidden()
    pet.share_action.trigger()
    pet.details.share_button.click()
    assert calls == [True, True]
    actions = [action for action in pet.pet_menu.actions() if not action.isSeparator()]
    assert actions[-1] is pet.quit_action


def test_the_pet_menu_opens_this_weeks_card_with_the_demo_watermark_in_test_mode(pet, app):
    pet.set_share_handler(pet.open_share_card)
    pet.share_action.trigger()
    dialog = pet._share_card_dialog
    assert dialog.isVisible() and not dialog.image.isNull()
    assert dialog.card_data["language"] == "zh" and dialog.card_data["demo"] is True
    dialog.close()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize(
    ("saved", "zh", "en"),
    [
        (82_000, "今日 −82K", "Today −82K"),
        (1_234_567, "今日 −1.23M", "Today −1.23M"),
        (950, "今日 −950", "Today −950"),
        (0, "", ""),
        (-4_000, "", ""),
        (None, "", ""),
    ],
)
def test_capsule_text_shows_only_real_savings_today(saved, zh, en):
    assert (
        usage_widget_qt.capsule_text(saved, SimpleNamespace(tr=lambda a, b, **v: a.format(**v)))
        == zh
    )
    assert (
        usage_widget_qt.capsule_text(saved, SimpleNamespace(tr=lambda a, b, **v: b.format(**v)))
        == en
    )


def test_pet_capsule_sits_below_the_head_and_idle_is_not_faint(pet):
    assert pet.capsule.isHidden()  # nothing saved yet: no fake number
    UsageStore(pet.store.path).record(
        {
            "usable": True,
            "input_tokens": 100_000,
            "memory_tokens": 18_000,
            "reduced_tokens": 82_000,
            "counter": "fixture",
        }
    )
    pet.refresh()
    assert pet.capsule.text() == "今日 −82K"
    assert not pet.capsule.isHidden()
    assert pet.capsule.geometry().top() >= pet.art.geometry().bottom()
    assert pet.materialization.opacity() >= 0.8
    pet.set_ui_language("en")
    assert pet.capsule.text() == "Today −82K"


def test_session_notice_never_shows_a_raw_session_id(pet):
    notice = pet.session_notice
    raw = "0f6c2a3e-9d41-4b5e-a1f7-3c8e2d9b7a10"
    notice.present({"host": "claude", "session_id": raw, "enabled": True})
    assert raw not in notice.detail.text() and raw not in notice.detail.toolTip()
    assert "未命名对话" in notice.detail.text()
    pet.set_ui_language("en")
    assert "Untitled chat" in notice.detail.text()
    notice.hide()


def test_error_state_clears_stale_model_rows_and_chart(pet):
    UsageStore(pet.store.path).record(
        {
            "usable": True,
            "input_tokens": 10_000,
            "memory_tokens": 2_000,
            "reduced_tokens": 8_000,
            "counter": "fixture",
        }
    )
    pet.pricing = {"rate": 2.0, "label": "Fixture", "model": "fixture", "mode": "input"}
    pet.details.refresh_report()
    assert pet.details.model_rows.count() and pet.details.chart.days
    pet.details.show_error()
    assert pet.details.model_rows.count() == 0 and not pet.details.chart.days
    assert pet.details.money_column.isHidden() and pet.details.chart.isHidden()
