"""Offscreen savings dashboard: per-model money, trend, and handoff/export actions."""

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from tomc import pricing_catalog, savings, usage_widget_qt  # noqa: E402
from tomc.context_library import ContextLibrary  # noqa: E402
from tomc.request_activity import RequestActivity  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402
from tomc.usage_widget_qt import Companion, load_preview_fonts  # noqa: E402

VERIFIED = "2026-10-18T00:00:00+00:00"
CATALOG = {
    "schema": 1,
    "providers": {
        "openai": {
            "verified_at": VERIFIED,
            "rates": [
                {
                    "provider": "openai",
                    "model": f"gpt-6-{name}",
                    "label": f"gpt-6-{name}",
                    "variant": "standard-short",
                    "input": price,
                    "cached": price / 10,
                    "output": price * 5,
                }
                for name, price in (("astra", 10.0), ("sol", 2.0), ("luna", 0.1))
            ],
        },
        "anthropic": {
            "verified_at": VERIFIED,
            "rates": [
                {
                    "provider": "anthropic",
                    "model": "claude-opus-5-5",
                    "label": "Claude Opus 5.5",
                    "variant": "standard",
                    "input": 4.0,
                    "cached": 0.2,
                    "output": 20.0,
                }
            ],
        },
    },
}


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    load_preview_fonts()
    yield app


def compiled(path, request_id, host, model, before, after):
    activity = RequestActivity(path)
    activity.start(request_id, host, "session")
    activity.finish(
        request_id,
        state="prepared",
        before_tokens=before,
        after_tokens=after,
        context_input_tokens=1000,
        model=model,
    )
    UsageStore(path).record(
        {
            "request_id": request_id,
            "usable": True,
            "input_tokens": before,
            "memory_tokens": after,
            "reduced_tokens": before - after,
            "counter": "regex-request-json-v1 (estimate)",
            "context_input_tokens": 1000,
        }
    )


def snapshot(path, title, host="codex", before=15_558, after=12_101):
    prepared = SimpleNamespace(
        compilation=SimpleNamespace(
            compiled_memory=f"Fixture evidence for {title}.",
            stats=SimpleNamespace(
                token_budget=12_000,
                input_tokens=before,
                output_tokens=after,
                tokenizer="fixture-estimate",
            ),
        )
    )
    return ContextLibrary(path).save(prepared, task=title, host=host, session_id="session")


def make_pet(app, path, monkeypatch, language="zh", reference=None):
    UiLanguage(path).set_language(language)
    monkeypatch.setattr(usage_widget_qt, "load_pricing", lambda: reference)
    pet = Companion(path, test_mode=True, connect_quota=False)
    pet.timer.stop()
    return pet


def close(app, pet):
    pet.close()
    pet.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture(autouse=True)
def hermetic_prices(monkeypatch):
    monkeypatch.setattr(pricing_catalog, "read_catalog", lambda path=None: CATALOG)
    monkeypatch.setattr(savings, "load_detected", lambda path=None: {})


def texts(widget):
    items = widget.findChildren(QLabel) + widget.findChildren(QPushButton)
    found = [item.text() for item in items] + [item.toolTip() for item in items]
    return [text.replace("中文", "") for text in found]


def test_dashboard_shows_tokens_money_and_each_model(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "gpt-6-astra", 100_000, 60_000)
    compiled(path, "b", "claude", "claude-opus-5-5", 50_000, 40_000)
    pet = make_pet(app, path, monkeypatch)
    try:
        pet.show_details()
        app.processEvents()
        details = pet.details
        assert details.caption.text() == "节省 tokens"
        assert details.total.text() == "50,000"
        assert details.money_caption.text() == "省下的钱"
        assert details.money.text() == "$0.44"
        rows = [details.model_rows.itemAt(i).layout() for i in range(details.model_rows.count())]
        cells = [[row.itemAt(j).widget().text() for j in range(row.count())] for row in rows]
        assert cells == [["gpt-6-astra", "40K", "$0.40"], ["Claude Opus 5.5", "10K", "$0.04"]]
        tip = rows[0].itemAt(0).widget().toolTip()
        assert "$10" in tip and "按请求记录的模型" in tip and "Codex" in tip
        assert details.basis.text() == "按各模型输入价"
        assert details.stats.text() == "2 次压缩 · 平均每次节省 25,000 tokens"
        assert details.chart_today.text() == "今天 50K"
        pet.set_ui_language("en")
        assert details.caption.text() == "Tokens saved"
        assert details.basis.text() == "At each model's input price"
        assert not [text for text in texts(details) if re.search(r"[㐀-鿿]", text)]
    finally:
        close(app, pet)


def test_more_models_than_rows_are_grouped(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    for index, model in enumerate(("gpt-6-astra", "claude-opus-5-5", "gpt-6-sol", "gpt-6-luna")):
        compiled(path, f"r{index}", "codex", model, 50_000 - index * 10_000, 10_000)
    pet = make_pet(app, path, monkeypatch, language="en")
    try:
        details = pet.details
        names = [
            details.model_rows.itemAt(i).layout().itemAt(0).widget().text()
            for i in range(details.model_rows.count())
        ]
        assert names == ["gpt-6-astra", "Claude Opus 5.5", "2 others"]
        others = details.model_rows.itemAt(2).layout()
        assert others.itemAt(1).widget().text() == "30K"
    finally:
        close(app, pet)


def test_unpriced_savings_point_to_pricing(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "mystery-1", 9_000, 8_000)
    pet = make_pet(app, path, monkeypatch)
    opened = []
    monkeypatch.setattr(pet, "open_reference", lambda *args: opened.append(True))
    pet.details.price_button.clicked.disconnect()
    pet.details.price_button.clicked.connect(pet.open_reference)
    try:
        assert pet.details.money.text() == "—"
        assert pet.details.basis.text() == "选择参考模型后显示金额"
        row = pet.details.model_rows.itemAt(0).layout()
        assert row.itemAt(0).widget().text() == "未定价"
        pet.details.price_button.click()
        assert opened
    finally:
        close(app, pet)


def test_period_tabs_change_totals_and_trend_highlight(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "gpt-6-astra", 2_000, 1_000)
    day = str(datetime.now(timezone.utc).date() - timedelta(days=3))
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO context_usage_daily VALUES (?,?,?,?,?,?,?)",
            (day, "regex-v1 (estimate)", 1, 1, 0, 10_000, 5_000),
        )
    reference = {"model": "claude-opus-5-5", "label": "Claude Opus 5.5", "rate": 4.0}
    pet = make_pet(app, path, monkeypatch, reference=reference)
    try:
        details = pet.details
        today = str(datetime.now(timezone.utc).date())
        details.buttons["today"].click()
        assert details.total.text() == "1,000" and details.chart.start == today
        details.buttons["7d"].click()
        assert details.total.text() == "6,000"
        assert details.chart.start == str(datetime.now(timezone.utc).date() - timedelta(days=6))
        details.buttons["all"].click()
        assert details.chart.start is None and details.buttons["all"].isChecked()
        assert [d["tokens_saved"] for d in details.chart.days][-4] == 5_000
    finally:
        close(app, pet)


def test_records_copy_export_import_and_open(app, tmp_path, monkeypatch):
    path = tmp_path / "a" / "memory.sqlite3"
    path.parent.mkdir()
    first = snapshot(path, "Fix the cat stage")
    snapshot(path, "Design the dashboard", host="claude")
    pet = make_pet(app, path, monkeypatch)
    try:
        pet.show_details()
        app.processEvents()
        details = pet.details
        rows = [details.record_list.itemAt(i).widget() for i in range(details.record_list.count())]
        assert [row.title.text() for row in rows] == ["Design the dashboard", "Fix the cat stage"]
        assert rows[1].tokens.text() == "15.6K → 12.1K"
        assert rows[1].meta.text().startswith("Codex · ")
        assert not details.records_empty.isVisible()
        rows[1].copy_button.click()
        prompt = QApplication.clipboard().text()
        assert prompt == ContextLibrary(path).handoff_prompt(first["id"], language="zh")
        assert details.records_message.isVisible()
        assert details.records_message.text().startswith("已复制接续提示词")
        target = tmp_path / "exports"
        target.mkdir()
        monkeypatch.setattr(
            usage_widget_qt.QFileDialog, "getExistingDirectory", lambda *args: str(target)
        )
        rows = [details.record_list.itemAt(i).widget() for i in range(details.record_list.count())]
        rows[1].export_button.click()
        app.processEvents()
        bundles = list(target.iterdir())
        assert len(bundles) == 1 and (bundles[0] / "CONTEXT.md").is_file()
        assert details.isVisible() and str(bundles[0]) in details.records_message.text()
        details.open_record(first)
        assert pet.context_dialog.selected_record["id"] == first["id"]
    finally:
        close(app, pet)
    other = tmp_path / "b" / "memory.sqlite3"
    other.parent.mkdir()
    receiver = make_pet(app, other, monkeypatch, language="en")
    try:
        receiver.show_details()
        app.processEvents()
        assert receiver.details.records_empty.isVisible()
        monkeypatch.setattr(
            usage_widget_qt.QFileDialog, "getExistingDirectory", lambda *args: str(bundles[0])
        )
        receiver.details.import_button.click()
        app.processEvents()
        assert receiver.details.records_message.text() == (
            "Imported “Fix the cat stage”. Copy its prompt to continue."
        )
        imported = receiver.details.record_list.itemAt(0).widget()
        assert imported.title.text() == "Fix the cat stage"
        receiver.details.import_button.click()
        assert "already exists" in receiver.details.records_message.text()
    finally:
        close(app, receiver)


def test_cancelled_export_reopens_without_a_message(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    record = snapshot(path, "Keep me")
    pet = make_pet(app, path, monkeypatch)
    try:
        monkeypatch.setattr(usage_widget_qt.QFileDialog, "getExistingDirectory", lambda *a: "")
        pet.show_details()
        pet.details.export_record(record)
        app.processEvents()
        assert pet.details.isVisible() and not pet.details.records_message.isVisible()
        assert not list(Path(tmp_path).glob("task-*"))
    finally:
        close(app, pet)


def test_empty_dashboard_explains_where_records_come_from(app, tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    pet = make_pet(app, path, monkeypatch, language="en")
    try:
        pet.show_details()
        app.processEvents()
        details = pet.details
        assert details.total.text() == "0" and details.money.text() == "—"
        assert details.basis.text() == "No savings yet"
        assert details.stats.text() == "No compressions in this period"
        assert details.records_empty.isVisible()
        assert "Copy a prompt" in details.records_empty.text()
    finally:
        close(app, pet)


def test_analysis_link_opens_the_library_on_its_analysis_tab(app, tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-home"))
    path = tmp_path / "memory.sqlite3"
    compiled(path, "a", "codex", "gpt-6-astra", 100_000, 60_000)
    pet = make_pet(app, path, monkeypatch)
    try:
        pet.show_details()
        app.processEvents()
        assert pet.details.analysis_button.text() == "分析报告 ›"
        pet.details.analysis_button.click()
        app.processEvents()
        library = pet.context_dialog
        assert not pet.details.isVisible()
        assert library.tabs.currentWidget() is library.analysis_page
        assert library.analysis_page.report["totals"]["tokens_saved"] == 40_000
        library.close()
    finally:
        close(app, pet)


def test_escape_on_the_cat_closes_the_panel_and_never_quits(app, tmp_path, monkeypatch):
    pet = make_pet(app, tmp_path / "memory.sqlite3", monkeypatch)
    quits = []
    monkeypatch.setattr(usage_widget_qt.QApplication, "quit", lambda *args: quits.append(1))
    try:
        pet.show()
        pet.show_details()
        app.processEvents()
        assert pet.details.isVisible()
        QTest.keyClick(pet, Qt.Key.Key_Escape)
        assert not pet.details.isVisible() and pet.isVisible() and quits == []
        QTest.keyClick(pet, Qt.Key.Key_Escape)  # nothing open: still running
        assert pet.isVisible() and quits == []
    finally:
        close(app, pet)
