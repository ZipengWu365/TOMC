"""Offscreen UI contracts against isolated databases, never the installed companion."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox  # noqa: E402

from tomc.context_library_qt import ContextLibraryDialog, SessionNotice  # noqa: E402
from tomc.session_store import SessionStore  # noqa: E402

STATUS = {
    host: {"label": "已配置", "runtime_verified": False, "detail": "fixture"}
    for host in ("codex", "claude_code")
}


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.clipboard().clear()
    for widget in instance.topLevelWidgets():
        widget.deleteLater()
    instance.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def isolated_hosts(tmp_path, monkeypatch):
    """Conversation names come from empty fixture hosts, never the real Codex/Claude homes."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))


def save_fixture(library, task="Continue the test task", before=2000, after=300):
    prepared = SimpleNamespace(
        compilation=SimpleNamespace(
            compiled_memory="Fixture historical evidence.\nKeep source IDs.",
            stats=SimpleNamespace(
                token_budget=500,
                input_tokens=before,
                output_tokens=after,
                tokenizer="fixture-estimate",
            ),
        )
    )
    return library.save(prepared, task=task, host="codex", session_id="session-a")


@pytest.fixture
def dialog(app, tmp_path):
    window = ContextLibraryDialog(tmp_path / "isolated.sqlite3", integrations=STATUS, pricing=None)
    window.language.set_language("zh")
    yield window
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_empty_browser_does_not_create_db_or_invent_records(dialog):
    assert not dialog.library.path.exists()
    assert dialog.conversation_list.count() == 0
    assert "还没有保存的上下文" in dialog.empty.text()
    assert "无法还原" in dialog.empty.text()
    assert not dialog.copy_button.isEnabled()
    assert dialog.enabled.isChecked() and dialog.save_contexts.isChecked()
    assert "连接待验证" in dialog.integration_labels["codex"].text()
    assert "尚未观察" in dialog.mode.text()


def test_search_preview_and_untruncated_self_contained_copy(dialog, app):
    save_fixture(dialog.library, "Alpha continuation")
    second = save_fixture(dialog.library, "Beta continuation")
    dialog.refresh()
    # One chat, named by its first task because the host has no name for it.
    assert dialog.conversation_list.count() == 1 and dialog.version_list.count() == 2
    assert dialog.conversation_title.text() == "Alpha continuation"
    dialog.search.setText("ALPHA")
    assert dialog.version_list.count() == 2  # A conversation-name match shows every version.
    dialog.search.setText("BETA")
    assert dialog.version_list.count() == 1
    assert dialog.selected_record["id"] == second["id"]
    assert dialog.memory.toPlainText() == second["memory"]
    dialog.copy_handoff()
    copied = app.clipboard().text()
    assert copied == dialog.library.handoff_prompt(
        second["id"], inline=True, language=dialog.language.code
    )
    assert second["memory"] in copied and "Beta continuation" in copied
    assert "未截断" in dialog.message.text()
    dialog.search.setText("absent title")
    assert not dialog.copy_button.isEnabled()
    assert "没有匹配" in dialog.empty.text()


def test_estimate_keeps_negative_change_separate_from_unmeasured_request(dialog):
    save_fixture(dialog.library, before=100, after=300)
    dialog.pricing = {"rate": 2, "label": "Fixture rate", "model": "fixture", "mode": "input"}
    dialog.refresh()
    assert "增加 200" in dialog.record_tokens.text()
    assert "参考输入金额增加 <$0.01" in dialog.record_cost.text()
    assert "请求用量：未关联" in dialog.request_status.text()


def test_global_processing_recording_and_session_controls_are_independent(dialog):
    dialog.sessions.register("codex", "a", title="One")
    dialog.sessions.register("claude", "b", title="Two")
    dialog.refresh()
    dialog.save_contexts.setChecked(False)
    assert dialog.sessions.settings() == {"enabled": True, "save_contexts": False}
    item = next(
        dialog.session_list.item(i)
        for i in range(dialog.session_list.count())
        if dialog.session_list.item(i).data(Qt.ItemDataRole.UserRole) == ("codex", "a")
    )
    item.setCheckState(Qt.CheckState.Unchecked)
    assert not dialog.sessions.effective_enabled("codex", "a")
    assert dialog.sessions.effective_enabled("claude", "b")
    dialog.enabled.setChecked(False)
    assert not dialog.sessions.effective_enabled("claude", "b")
    dialog.enabled.setChecked(True)
    assert not dialog.sessions.effective_enabled("codex", "a")


def test_notice_timeout_preserves_default_and_click_is_bound_to_displayed_session(app, tmp_path):
    store = SessionStore(tmp_path / "notice.sqlite3")
    store.register("codex", "a", title="Displayed session")
    notice = SessionNotice(store)
    notice.language.set_language("zh")
    notice.present(store.active())
    notice.timer.timeout.emit()
    assert not notice.isVisible()
    assert store.effective_enabled("codex", "a")
    notice.present(store.active())
    store.register("claude", "b", title="New active event")
    notice.toggle_button.click()
    assert not store.effective_enabled("codex", "a")
    assert store.effective_enabled("claude", "b")
    store.register("codex", "a", event="resume")
    notice.present(store.active())
    assert "已关闭" in notice.heading.text()
    assert notice.toggle_button.text() == "重新开启本会话"
    notice.keep_button.click()
    assert not store.effective_enabled("codex", "a")
    notice.present(store.active())
    notice.toggle_button.click()
    assert store.effective_enabled("codex", "a")
    notice.close()


def test_export_import_rename_delete_actions_use_selected_snapshot(dialog, tmp_path, monkeypatch):
    row = save_fixture(dialog.library)
    dialog.refresh()

    def rename(dialog):
        dialog.setTextValue("Renamed record")
        return 1

    monkeypatch.setattr(QInputDialog, "exec", rename)
    dialog.rename_context()
    assert dialog.library.get(row["id"])["title"] == "Renamed record"
    export_root = tmp_path / "portable"
    export_root.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(export_root))
    dialog.export_context()
    bundles = list(export_root.iterdir())
    assert len(bundles) == 1
    assert {p.name for p in bundles[0].iterdir()} == {
        "metadata.json",
        "CONTEXT.md",
        "START_HERE.md",
    }
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    dialog.delete_context()
    assert dialog.library.list() == []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(bundles[0]))
    dialog.import_bundle()
    assert dialog.selected_record["memory"] == row["memory"]
    assert dialog.selected_record["session_id"] is None
    assert "未绑定" in dialog.message.text()
    dialog.import_bundle()
    assert "未重复" in dialog.message.text()


def test_companion_observed_switch_prompts_once_and_closes_child_windows(
    app, tmp_path, monkeypatch
):
    from tomc import context_library_qt, usage_widget_qt

    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    monkeypatch.setattr(context_library_qt, "load_pricing", lambda: None)
    monkeypatch.setattr(context_library_qt, "integration_snapshot", lambda: STATUS)
    # The production companion quits its dedicated app. Keep pytest's shared Qt app alive.
    quit_requests = []
    monkeypatch.setattr(app, "quit", lambda: quit_requests.append(True))
    pet = usage_widget_qt.Companion(tmp_path / "pet.sqlite3", test_mode=True, connect_quota=False)
    pet.language.set_language("zh")
    pet.timer.stop()
    pet.session_store.register("codex", "a", title="One", event="SessionStart")
    pet.refresh_session_state()
    assert pet.session_notice.isVisible()
    sequence = pet.session_event_seq
    pet.session_notice.hide()
    pet.session_store.register("codex", "a", event="activity")
    pet.refresh_session_state()
    assert pet.session_event_seq == sequence and not pet.session_notice.isVisible()
    pet.session_store.register("claude", "b", title="Two", event="UserPromptSubmit")
    pet.refresh_session_state()
    assert pet.session_notice.isVisible() and pet.session_notice.target == ("claude", "b")
    pet.open_context_library()
    assert pet.context_dialog.isVisible()
    pet.close()
    assert not pet.context_dialog.isVisible() and not pet.session_notice.isVisible()
    assert not pet.session_notice.timer.isActive()
    assert quit_requests == [True]
    pet.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_request_preparation_animates_once_and_generation_is_not_compression(
    app, tmp_path, monkeypatch
):
    from tomc import usage_widget_qt

    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    monkeypatch.setattr(app, "quit", lambda: None)
    pet = usage_widget_qt.Companion(
        tmp_path / "request.sqlite3", test_mode=True, connect_quota=False
    )
    pet.language.set_language("zh")
    pet.timer.stop()
    calls = []
    collect = pet.art.collect

    def counted_collect():
        calls.append(True)
        collect()

    monkeypatch.setattr(pet.art, "collect", counted_collect)
    pet.request_activity.start("request-1", "codex", "a")
    pet.refresh()
    assert not calls and pet.preparing_request is not None
    assert "压缩中" in pet.number.text()
    pet.request_activity.finish(
        "request-1",
        state="prepared",
        reason="optimized",
        before_tokens=1000,
        after_tokens=500,
        context_input_tokens=900,
    )
    pet.refresh()
    assert pet.preparing_request is None and pet.art.phase is not None
    assert len(calls) == 1 and pet.art.level == 1
    # The completed preparation has a known context length; its bounded visual
    # runs once without treating downstream model generation as CPU preparation.
    pet.art.animation_timer.stop()
    pet.art.phase = None
    pet.finish_collection()
    assert "上下文已压缩" in pet.caption.text()
    assert pet.latest.text() == "压缩上下文 900 tokens"
    pet.hide_report()
    # Model generation/streaming occurs after CPU preparation; it must not stay busy.
    pet.request_activity.sent("request-1")
    pet.request_activity.usage("request-1", provider_input_tokens=720, provider_cached_tokens=100)
    pet.store.record(
        {
            "counter": "fixture",
            "usable": True,
            "input_tokens": 1000,
            "memory_tokens": 500,
            "reduced_tokens": 500,
            "request_id": "request-1",
            "context_input_tokens": 900,
        }
    )
    pet.refresh()
    assert len(calls) == 1 and pet.art.phase is None
    assert "720" in pet.details.request_status.toolTip()
    assert "不是" not in pet.details.request_status.toolTip()
    assert "账单" not in pet.details.request_status.toolTip()
    assert pet.store.summary()["preparations"] == 1
    pet.request_activity.start("request-2", "codex", "b")
    pet.request_activity.finish("request-2", state="passthrough", reason="session_disabled")
    pet.request_activity.sent("request-2")
    pet.refresh()
    assert "本会话已关闭" in pet.details.request_status.text()
    assert len(calls) == 1
    pet.close()
    pet.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_manager_distinguishes_configured_from_observed_proxy_usage(dialog):
    dialog.activity.start("request-demo", "claude", "s")
    dialog.activity.finish(
        "request-demo",
        state="passthrough",
        reason="history_fits_memory_budget",
        before_tokens=80,
        after_tokens=80,
    )
    dialog.refresh()
    assert "连接待验证" in dialog.integration_labels["claude_code"].text()
    assert "将原样转发" in dialog.activity_status.text()
    dialog.activity.sent("request-demo")
    dialog.activity.usage("request-demo", provider_input_tokens=120, provider_cached_tokens=0)
    dialog.refresh()
    assert "代理转发曾被观察" in dialog.integration_labels["claude_code"].text()
    assert "实测 provider 输入 120" in dialog.activity_status.text()
    assert "不是节省差额" not in dialog.activity_status.text()


def test_configured_gateway_without_request_is_visible_and_not_claimed_connected(dialog):
    dialog.integrations = {
        **STATUS,
        "mode": {
            "id": "automatic_request_gateway",
            "configured_hosts": ["codex"],
            "gateway_service": "offline",
        },
    }
    dialog.refresh()
    assert "自动接入已配置" in dialog.mode.text()
    assert "重开客户端后等待请求" in dialog.mode.text()
    assert "服务不可达" in dialog.mode.text()
    assert "连接待验证" in dialog.integration_labels["codex"].text()
    dialog.integrations["mode"]["gateway_service"] = "online"
    dialog.refresh()
    assert "服务可达" in dialog.mode.text()
    assert "连接待验证" in dialog.integration_labels["codex"].text()


def test_health_check_is_short_loopback_only_and_does_not_claim_session_verified(monkeypatch):
    import json

    from tomc import context_library_qt, integration_status

    status = {
        "mode": {
            "id": "automatic_request_gateway",
            "gateway_port": 43187,
            "runtime_verified": False,
        }
    }
    monkeypatch.setattr(integration_status, "get_integration_status", lambda: status)
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size):
            assert size == 4096
            return json.dumps({"service": "tomc-gateway", "ready": True}).encode()

    class Opener:
        def open(self, url, timeout):
            calls.append((url, timeout))
            return Response()

    def builder(proxy):
        assert proxy.proxies == {}
        return Opener()

    monkeypatch.setattr(context_library_qt, "build_opener", builder)
    result = context_library_qt.integration_snapshot()
    assert calls == [("http://127.0.0.1:43187/health", 0.25)]
    assert result["mode"]["gateway_service"] == "online"
    assert result["mode"]["runtime_verified"] is False


def test_short_preparation_missed_between_polls_still_plays_one_completion_animation(
    app, tmp_path, monkeypatch
):
    from tomc import usage_widget_qt

    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: None)
    monkeypatch.setattr(app, "quit", lambda: None)
    pet = usage_widget_qt.Companion(tmp_path / "fast.sqlite3", test_mode=True, connect_quota=False)
    pet.language.set_language("zh")
    pet.timer.stop()
    calls = []
    monkeypatch.setattr(pet.art, "collect", lambda: calls.append(True))
    pet.request_activity.start("quick", "codex", "s")
    pet.request_activity.finish(
        "quick", state="prepared", reason="optimized", before_tokens=1000, after_tokens=500
    )
    pet.request_activity.sent("quick")
    pet.store.record(
        {
            "counter": "fixture",
            "usable": True,
            "input_tokens": 1000,
            "memory_tokens": 500,
            "reduced_tokens": 500,
            "request_id": "quick",
        }
    )
    pet.refresh()
    pet.refresh()
    assert calls == [True] and pet.preparing_request is None
    pet.close()
    pet.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_language_switch_updates_all_authored_text_without_resetting_filters(dialog):
    import re

    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QPushButton,
        QTabWidget,
    )

    row = save_fixture(dialog.library, "English fixture task")
    dialog.sessions.register("claude", "fixture-session", title="English session")
    dialog.activity.start("fixture-request", "claude", "fixture-session")
    dialog.activity.finish(
        "fixture-request",
        state="passthrough",
        reason="protected_system_history",
        before_tokens=200,
        after_tokens=200,
    )
    dialog.activity.sent("fixture-request")
    dialog.activity.usage("fixture-request", provider_input_tokens=250, provider_cached_tokens=100)
    dialog.refresh()
    dialog.search.setText("fixture")
    original = dialog.library.get(row["id"])
    dialog.language.set_language("en")
    assert dialog.search.text() == "fixture"
    assert dialog.selected_record["id"] == row["id"]
    assert dialog.library.get(row["id"]) == original
    assert dialog.copy_button.text() == "Copy handoff prompt"
    assert "Measured provider input 250" in dialog.activity_status.text()
    assert "tool definitions retained" in dialog.activity_status.text()
    texts = [dialog.windowTitle(), dialog.task.toPlainText()]
    for widget in (
        dialog.findChildren(QLabel)
        + dialog.findChildren(QPushButton)
        + dialog.findChildren(QCheckBox)
    ):
        texts.extend((widget.text(), widget.toolTip(), widget.accessibleName()))
    for widget in dialog.findChildren(QLineEdit):
        texts.append(widget.placeholderText())
    for widget in dialog.findChildren(QComboBox):
        texts.extend(widget.itemText(i) for i in range(widget.count()))
    for widget in dialog.findChildren(QListWidget):
        texts.extend(
            widget.item(i).text() + widget.item(i).toolTip() for i in range(widget.count())
        )
    for widget in dialog.findChildren(QTabWidget):
        texts.extend(widget.tabText(i) for i in range(widget.count()))
    assert not [text for text in texts if re.search(r"[\u3400-\u9fff]", text)]
    dialog.language.set_language("zh")
    assert dialog.copy_button.text() == "复制接续提示词"
    assert "实测 provider 输入 250" in dialog.activity_status.text()


def test_selected_language_controls_handoff_but_never_translates_user_text(dialog, app):
    row = save_fixture(dialog.library, "用户原任务：继续检查")
    dialog.library.rename(row["id"], "用户自己的中文标题")
    before = dialog.library.get(row["id"])
    dialog.refresh()
    dialog.language.set_language("en")
    dialog.copy_handoff()
    assert dialog.record_title.text() == before["title"]
    assert dialog.memory.toPlainText() == before["memory"]
    assert app.clipboard().text().startswith("Continue from this TOMC snapshot")
    assert before["task"] in app.clipboard().text()
    assert "Copied a complete handoff prompt" in dialog.message.text()
    dialog.language.set_language("zh")
    assert "已复制自包含" in dialog.message.text()
    dialog.copy_handoff()
    assert app.clipboard().text().startswith("从这份 TOMC 快照继续")
    assert dialog.library.get(row["id"]) == before


def test_empty_error_and_disabled_messages_retranslate_immediately(dialog, monkeypatch):
    dialog.language.set_language("en")
    assert "No saved contexts yet" in dialog.empty.text()
    assert "No session events received" in dialog.session_note.text()
    row = save_fixture(dialog.library)
    dialog.sessions.register("codex", "a", title="Test")
    dialog.refresh()
    dialog.language.set_language("zh")
    dialog.session_list.item(0).setCheckState(Qt.CheckState.Unchecked)
    dialog.language.set_language("en")
    assert dialog.message.text().startswith("TOMC is disabled")
    dialog.language.set_language("zh")

    def fail(*args, **kwargs):
        raise ValueError("fixture failure")

    monkeypatch.setattr(dialog.library, "handoff_prompt", fail)
    dialog.copy_handoff()
    assert dialog.message.text() == "复制失败：fixture failure"
    dialog.language.set_language("en")
    assert dialog.message.text() == "Copy failed: fixture failure"
    assert dialog.selected_record["id"] == row["id"]


def test_notice_uses_owner_language_and_keeps_bound_target_and_timer(dialog):
    dialog.sessions.register("codex", "a", title="用户会话标题")
    notice = SessionNotice(dialog.sessions, dialog)
    assert notice.language is dialog.language
    notice.present(dialog.sessions.active())
    remaining = notice.timer.remainingTime()
    dialog.sessions.register("claude", "b", title="Another session")
    dialog.language.set_language("en")
    assert notice.target == ("codex", "a")
    assert "TOMC is enabled" in notice.heading.text()
    assert "用户会话标题" in notice.detail.text()
    assert notice.toggle_button.text() == "Disable session"
    assert 0 <= notice.timer.remainingTime() <= remaining
    notice.toggle_button.click()
    assert not dialog.sessions.effective_enabled("codex", "a")
    assert dialog.sessions.effective_enabled("claude", "b")
    notice.close()


def test_open_confirmation_dialog_retranslates_buttons_without_changing_selection(
    dialog, monkeypatch
):
    row = save_fixture(dialog.library)
    dialog.refresh()

    def confirm(box):
        dialog.language.set_language("en")
        assert box.windowTitle() == "Delete local context"
        assert box.button(QMessageBox.StandardButton.Yes).text() == "Delete"
        assert box.button(QMessageBox.StandardButton.Cancel).text() == "Cancel"
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "exec", confirm)
    dialog.delete_context()
    assert dialog.library.get(row["id"])["memory"] == row["memory"]


def name_codex_thread(tmp_path, thread, name, cwd):
    import sqlite3
    from contextlib import closing

    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    with closing(sqlite3.connect(home / "state_5.sqlite")) as db, db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, name TEXT, title TEXT, "
            "cwd TEXT, agent_nickname TEXT, source TEXT)"
        )
        db.execute(
            "INSERT INTO threads VALUES (?,?,?,?,NULL,'user')", (thread, name, "first message", cwd)
        )


def compiled_request(dialog, request_id, before, after, model="gpt-6-astra"):
    from tomc.usage import UsageStore

    dialog.activity.start(request_id, "codex", "session-a")
    dialog.activity.finish(
        request_id,
        state="prepared",
        before_tokens=before,
        after_tokens=after,
        context_input_tokens=1000,
        model=model,
    )
    UsageStore(dialog.library.path).record(
        {
            "request_id": request_id,
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": "regex-request-json-v1 (estimate)",
        }
    )


@pytest.fixture
def fixed_prices(monkeypatch):
    from tomc import pricing_catalog, savings

    catalog = {
        "schema": 1,
        "providers": {
            "openai": {
                "verified_at": "2026-10-18T00:00:00+00:00",
                "rates": [
                    {
                        "provider": "openai",
                        "model": "gpt-6-astra",
                        "label": "gpt-6-astra",
                        "variant": "standard-short",
                        "input": 10.0,
                        "cached": 1.0,
                        "output": 50.0,
                    }
                ],
            }
        },
    }
    monkeypatch.setattr(pricing_catalog, "read_catalog", lambda path=None: catalog)
    monkeypatch.setattr(savings, "load_detected", lambda path=None: {})


def test_conversations_use_host_names_and_keep_internal_ids_out_of_view(dialog, tmp_path):
    from PySide6.QtWidgets import QLabel

    name_codex_thread(tmp_path, "session-a", "Fix the cat stage", r"C:\work\TOMC-memory-branding")
    first = save_fixture(dialog.library, "Check why the cat never advances")
    second = save_fixture(dialog.library, "Verify the stage animation")
    dialog.sessions.register("codex", "session-a", project=r"C:\work\TOMC-memory-branding")
    dialog.refresh()
    assert dialog.conversation_title.text() == "Fix the cat stage"
    assert "TOMC-memory-branding" in dialog.conversation_meta.text()
    assert dialog.conversation_list.item(0).toolTip() == "Fix the cat stage"
    assert dialog.version_list.count() == 2
    assert dialog.version_list.itemWidget(dialog.version_list.item(0)).title.text() == (
        "Verify the stage animation"
    )
    visible = [label.text() for label in dialog.findChildren(QLabel)]
    visible.append(dialog.task.toPlainText())
    for identifier in (first["id"], second["id"], "session-a"):
        assert not [text for text in visible if identifier in text]
    assert second["id"] in dialog.version_list.item(0).toolTip()
    assert "Fix the cat stage" in dialog.task.toPlainText()
    session = dialog.session_list.item(0)
    assert session.text().startswith("Fix the cat stage\n")


def test_dashboard_numbers_models_and_conversation_switch(dialog, fixed_prices):
    from tomc.context_library import ContextLibrary

    compiled_request(dialog, "request-1", 100_000, 60_000)
    compiled_request(dialog, "request-2", 30_000, 20_000)  # compressed, text not saved
    prepared = SimpleNamespace(
        compilation=SimpleNamespace(
            compiled_memory="Fixture evidence.",
            stats=SimpleNamespace(
                token_budget=500, input_tokens=9000, output_tokens=7000, tokenizer="fixture"
            ),
        )
    )
    ContextLibrary(dialog.library.path).save(
        prepared,
        task="Saved task",
        host="codex",
        session_id="session-a",
        preparation_id="request-1",
    )
    dialog.sessions.register("codex", "session-a")
    dialog.refresh()
    kpis = {key: value.text() for key, (value, _caption) in dialog.kpis.items()}
    assert kpis == {
        "tokens": "50,000",
        "money": "$0.50",
        "compressions": "2",
        "conversations": "1",
    }
    chips = [
        dialog.model_chips.itemAt(i).widget().text()
        for i in range(dialog.model_chips.count())
        if dialog.model_chips.itemAt(i).widget()
    ]
    assert chips == ["gpt-6-astra  50K · $0.50"]
    # The conversation counts every compressed request of the chat, saved or not.
    assert [chip.text() for chip in dialog.conversation_chips] == [
        "1 份上下文",
        "节省 50K tokens",
        "$0.50",
    ]
    assert "整个请求节省 40,000 tokens" in dialog.request_status.text()
    assert "上下文 9,000 → 7,000 tokens" in dialog.record_tokens.text()
    dialog.period_buttons["today"].click()
    assert dialog.period == "today" and dialog.kpis["tokens"][0].text() == "50,000"
    # Shown only for registered sessions, reflecting the stored switch.
    assert not dialog.conversation_enabled.isHidden() and dialog.conversation_enabled.isChecked()
    dialog.conversation_enabled.setChecked(False)
    assert not dialog.sessions.effective_enabled("codex", "session-a")
    assert dialog.message.text().startswith("本会话 TOMC 已关闭")
    assert not dialog.conversation_enabled.isChecked()


def test_export_carries_the_conversation_name_to_the_other_computer(
    dialog, app, tmp_path, monkeypatch
):
    import json

    name_codex_thread(tmp_path, "session-a", "Fix the cat stage", "/work/TOMC")
    row = save_fixture(dialog.library, "Check why the cat never advances")
    dialog.refresh()
    target = tmp_path / "usb"
    target.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(target))
    dialog.export_context()
    (bundle,) = target.iterdir()
    metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["conversation"] == {"title": "Fix the cat stage"}
    other = ContextLibraryDialog(tmp_path / "other.sqlite3", integrations=STATUS, pricing=None)
    try:
        other.language.set_language("zh")
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(bundle))
        other.import_bundle()
        assert other.selected_record["id"] == row["id"]
        assert other.conversation_title.text() == "Fix the cat stage"
        assert other.conversation_meta.text().startswith("导入 · 来自 Codex")
    finally:
        other.close()
        other.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize(
    "record",
    [
        None,
        {"state": "preparing"},
        {"state": "prepared"},
        {"state": "forwarded", "reason": "disabled_compatible_replay"},
        {"state": "passthrough", "sent": True, "reason": "session_disabled"},
        {"state": "passthrough", "reason": "no_current_user_task"},
        {"state": "failed", "reason": "upstream_failed"},
        {"stale": True},
    ],
)
def test_activity_helper_accepts_english_or_defaults_to_chinese(record):
    import re

    from tomc.context_library_qt import request_activity_text

    assert re.search(r"[\u3400-\u9fff]", request_activity_text(record))
    assert not re.search(r"[\u3400-\u9fff]", request_activity_text(record, "en"))
    if record and record.get("reason") == "no_current_user_task":
        assert "no_current_user_task" not in request_activity_text(record)
        assert "no_current_user_task" not in request_activity_text(record, "en")
