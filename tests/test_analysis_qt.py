"""Offscreen contracts for the analysis page and the anonymous feedback dialog."""

import json
import os
import re
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from tomc import analysis_qt, savings  # noqa: E402
from tomc.context_library_qt import ContextLibraryDialog  # noqa: E402
from tomc.request_activity import RequestActivity  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402

CJK = re.compile(r"[㐀-鿿]")
STATUS = {
    host: {"label": "fixture", "runtime_verified": False, "detail": "fixture"}
    for host in ("codex", "claude_code")
}
PRICING = {"rate": 2.0, "label": "Fixture model", "model": "fixture", "mode": "input"}
NAMES = {"thread-a": "Fix the gateway bug", "thread-b": "Draft the release notes"}


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    instance.clipboard().clear()


@pytest.fixture(autouse=True)
def isolated_hosts(tmp_path, monkeypatch):
    """Conversation names come from a fixture Codex home, never the real one."""
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "session_index.jsonl").write_text(
        "".join(
            json.dumps({"id": thread, "thread_name": name}) + "\n" for thread, name in NAMES.items()
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))
    # Money uses the fixture reference rate, not this computer's detected host models.
    monkeypatch.setattr(savings, "load_detected", lambda path=None: {})


def compress(path, session, before, after):
    request_id = str(uuid.uuid4())
    activity = RequestActivity(path)
    activity.start(request_id, "codex", session)
    activity.finish(
        request_id,
        state="prepared",
        before_tokens=before,
        after_tokens=after,
        context_input_tokens=20_000,
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


@pytest.fixture
def dialog(app, tmp_path):
    path = tmp_path / "memory.sqlite3"
    compress(path, "thread-a", 50_000, 30_000)
    compress(path, "thread-b", 10_000, 9_000)
    window = ContextLibraryDialog(path, integrations=STATUS, pricing=PRICING)
    window.language.set_language("zh")
    window.resize(1000, 800)
    window.show()
    yield window
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def visible_texts(widget):
    items = widget.findChildren(QLabel) + widget.findChildren(QPushButton)
    return [item.text() for item in items] + [item.toolTip() for item in items]


def test_analysis_tab_ranks_conversations_and_follows_the_period(dialog, app):
    assert dialog.analysis_page.report is None  # computed only when opened
    dialog.analysis_button.click()
    app.processEvents()
    page = dialog.analysis_page
    assert dialog.tabs.currentWidget() is page
    assert page.summary.text() == "累计 · 2 个请求中压缩了 100%"
    # The privacy promise sits next to the button, not only at the bottom of the page.
    assert page.feedback_button.text() == "匿名提交反馈 ›"
    assert "反馈是匿名的" in page.anonymity.text()
    assert "不含对话名称、对话内容、文件夹或任何 ID" in page.anonymity.text()
    assert page.table.rowCount() == 2
    assert [page.table.item(row, 0).text() for row in range(2)] == list(NAMES.values())
    assert [page.table.item(row, 1).text() for row in range(2)] == ["编程开发", "写作与文案"]
    assert page.table.item(0, 4).text() == "20,000" and page.table.item(0, 5).text() == "$0.04"
    assert [name for name, *_ in page.conversation_donut.parts] == list(NAMES.values())
    assert page.category_donut.center == ("2", "种工作")
    assert page.coverage_bars.rows[0][:2] == ("已压缩", 2)
    dialog.set_period("today")
    assert page.report["period"] == "today" and page.summary.text().startswith("今天")
    dialog.language.set_language("en")
    app.processEvents()
    assert page.summary.text() == "Today · 100% of 2 requests compressed"
    assert page.table.item(1, 1).text() == "Writing & copy"
    assert not [text for text in visible_texts(page) if CJK.search(text)]


def test_copied_report_has_no_conversation_names(dialog, app):
    dialog.show_analysis()
    dialog.analysis_page.copy_button.click()
    copied = QApplication.clipboard().text()
    assert copied.startswith("# TOMC feedback report")
    assert not [name for name in (*NAMES, *NAMES.values()) if name in copied]
    assert "匿名" in dialog.message.text()


def test_feedback_dialog_lets_the_user_fix_kinds_then_opens_github(dialog, app, monkeypatch):
    dialog.show_analysis()
    feedback = analysis_qt.FeedbackDialog(dialog.analysis_page.report, dialog)
    try:
        assert "已匿名：只提交工作类型和数字" in feedback.anonymity.text()
        assert "不会提交：对话名称、对话内容" in feedback.anonymity.text()
        assert [feedback.table.item(row, 2).text() for row in range(2)] == [
            "coding #1",
            "writing #1",
        ]
        assert not feedback.submit_button.isEnabled()
        feedback.combos[1].setCurrentIndex(feedback.combos[1].findData("marketing"))
        assert feedback.table.item(1, 2).text() == "marketing #1"
        feedback.comment.setPlainText("Works well")
        preview = feedback.preview.toPlainText()
        assert "marketing #1" in preview and "Works well" in preview
        assert not [name for name in (*NAMES, *NAMES.values()) if name in preview]
        opened = []
        monkeypatch.setattr(analysis_qt.QDesktopServices, "openUrl", opened.append)
        feedback.submit_button.click()  # disabled: nothing opens before confirming
        assert opened == []
        feedback.confirm.setChecked(True)
        assert feedback.submit_button.isEnabled()
        feedback.submit_button.click()
        parts = urlsplit(opened[0].toString(opened[0].ComponentFormattingOption.FullyEncoded))
        assert parts.netloc == "github.com" and parts.path == "/ZipengWu365/TOMC/new/main"
        query = parse_qs(parts.query)
        assert query["filename"] == [feedback.filename]
        assert query["value"] == [preview]
        # A report too long for a link is copied, and the empty page opens instead.
        monkeypatch.setattr(analysis_qt, "feedback_url", lambda *args, **kwargs: None)
        feedback.submit_button.click()
        assert QApplication.clipboard().text() == preview
        query = parse_qs(urlsplit(opened[1].toString()).query)
        assert query == {"filename": [feedback.filename]}
        dialog.language.set_language("en")
        texts = [*visible_texts(feedback), feedback.confirm.text()]
        assert not [text for text in texts if CJK.search(text)]
    finally:
        feedback.close()
        feedback.deleteLater()


def test_empty_period_hides_the_table_and_feedback(app, tmp_path):
    window = ContextLibraryDialog(tmp_path / "empty.sqlite3", integrations=STATUS, pricing=PRICING)
    window.language.set_language("zh")
    try:
        window.show_analysis()
        page = window.analysis_page
        assert page.table.isHidden()
        assert page.table_note.text() == "这段时间还没有压缩过的对话。"
        assert not page.feedback_button.isEnabled() and not page.copy_button.isEnabled()
        assert not (tmp_path / "empty.sqlite3").exists()
    finally:
        window.close()
        window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
