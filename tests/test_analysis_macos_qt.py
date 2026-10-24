"""Mac analysis rendering and review controls, using synthetic reports only."""

import copy
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, QRect, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QVBoxLayout  # noqa: E402

from tomc import analysis_qt, macos_ui  # noqa: E402
from tomc.categories import CODES  # noqa: E402
from tomc.ui_language import UiLanguage  # noqa: E402


def synthetic_report():
    rows = [
        dict(
            key=("codex", f"synthetic-{i}"),
            host="codex",
            title=f"Synthetic conversation {i}: a long display name",
            folder="fixture",
            agent=None,
            category=category,
            tokens_saved=(9 - i) * 1000,
            money=(9 - i) / 100,
            compressions=3,
            contexts=2,
        )
        for i, category in enumerate(CODES)
    ]
    return dict(
        period="all",
        generated_utc="2026-10-24T12:00:00+00:00",
        mode="input",
        totals=dict(
            tokens_saved=45000,
            money=0.45,
            compressions=27,
            conversations=9,
            requests=40,
            compressed_share=27 / 40,
            unattributed_tokens=0,
        ),
        conversations=rows,
        categories=[
            dict(
                category=row["category"],
                tokens_saved=row["tokens_saved"],
                money=row["money"],
                conversations=1,
                compressions=3,
            )
            for row in rows
        ],
        hosts=[dict(host="codex", tokens_saved=45000, compressions=27)],
        models=[],
        coverage=[
            dict(group="compressed", requests=27),
            dict(group="host_managed", requests=8),
            dict(group="unsupported", requests=5),
        ],
        reductions=[
            dict(bucket=name, requests=3)
            for name in ("< 0%", "0–1%", "1–10%", "10–25%", "25–50%", ">=50%")
        ],
        stages=[dict(stage=i, compilations=i * 2) for i in range(1, 5)],
        daily=[dict(day=f"2026-10-{i:02}", tokens_saved=i * 120) for i in range(1, 25)],
    )


@pytest.fixture
def host(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(analysis_qt, "is_macos", lambda: True)
    monkeypatch.setattr(macos_ui, "is_macos", lambda: True)
    window = QDialog()
    window.language = UiLanguage(tmp_path / "memory.sqlite3", window)
    window.language.set_language("en")
    window.messages = []
    window.show_message = lambda *args, **kwargs: window.messages.append((args, kwargs))
    macos_ui.install_macos_style(window)
    yield app, window
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_mac_charts_and_table_follow_appearance_without_changing_statistics(host, appearance):
    app, parent = host
    page = analysis_qt.AnalysisPage(parent)
    QVBoxLayout(parent).addWidget(page)
    page.report = synthetic_report()
    before = copy.deepcopy(page.report)
    page.render()
    parent.resize(1100, 800)
    parent.setProperty("tomcAppearance", appearance)
    parent.show()
    app.processEvents()
    colors = macos_ui.tokens(page)
    assert parent.palette().color(QPalette.ColorRole.Window) == QColor(colors["background"])
    assert parent.grab().toImage().pixelColor(0, 0) == QColor(colors["background"])
    assert page.table.palette().color(QPalette.ColorRole.Base) == QColor(colors["field"])
    assert not page.table.styleSheet()
    assert page.report == before
    assert page.conversation_donut.center == ("45K", "tokens saved")
    image = page.conversation_donut.grab().toImage()
    expected = QColor(colors["text"])
    ratio = image.devicePixelRatio()
    matching = 0
    for y in range(int(60 * ratio), int(90 * ratio)):
        for x in range(int(40 * ratio), int(125 * ratio)):
            if image.pixelColor(x, y) == expected:
                matching += 1
    assert matching > 10  # The central value is actually painted in the semantic text colour.
    assert page.table.item(0, 4).text() == "9,000"
    assert not page.coverage_bars.grab().isNull()


def test_mac_existing_charts_and_legends_repaint_after_appearance_changes(host):
    app, parent = host
    page = analysis_qt.AnalysisPage(parent)
    QVBoxLayout(parent).addWidget(page)
    page.report = synthetic_report()
    page.render()
    parent.resize(1100, 800)
    parent.show()
    before = copy.deepcopy(page.conversation_donut.parts)
    dot = page.conversation_legend.findChildren(analysis_qt._LegendDot)[0]
    observed = []
    for appearance in ("light", "dark", "light"):
        parent.setProperty("tomcAppearance", appearance)
        app.processEvents()
        image = dot.grab().toImage()
        ratio = image.devicePixelRatio()
        color = image.pixelColor(round(6 * ratio), round(6 * ratio))
        observed.append(color)
        assert color == analysis_qt.chart_color(dot, before[0][2])
        assert page.conversation_donut.parts == before
    assert observed[0] != observed[1] and observed[0] == observed[2]


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_mac_feedback_small_window_scrolls_and_keeps_confirmation_and_actions_visible(
    host, language, appearance
):
    app, parent = host
    parent.language.set_language(language)
    feedback = analysis_qt.FeedbackDialog(synthetic_report(), parent)
    feedback.setProperty("tomcAppearance", appearance)
    feedback.resize(720, 560)
    feedback.show()
    app.processEvents()
    background = QColor(macos_ui.tokens(feedback)["background"])
    assert feedback.palette().color(QPalette.ColorRole.Window) == background
    assert feedback.grab().toImage().pixelColor(0, 0) == background
    assert feedback.content_scroll.verticalScrollBar().maximum() > 0
    assert feedback.table.horizontalScrollBar().maximum() == 0
    # The privacy promise must be readable on arrival, without hiding the fixed actions.
    banner_area = QRect(
        feedback.anonymity.mapTo(feedback.content_scroll.viewport(), QPoint(0, 0)),
        feedback.anonymity.size(),
    )
    assert feedback.content_scroll.viewport().rect().contains(banner_area)
    assert feedback.anonymity.height() >= feedback.anonymity.heightForWidth(
        feedback.anonymity.width()
    )
    assert feedback.anonymity.geometry().bottom() < feedback.explanation.geometry().top()
    assert feedback.anonymity.palette().color(QPalette.ColorRole.WindowText) == QColor(
        macos_ui.tokens(feedback)["selection_text"]
    )
    heading_position = feedback.heading.pos()
    assert feedback.confirm.height() >= feedback.confirm.heightForWidth(feedback.confirm.width())
    for control in (
        feedback.confirm,
        feedback.copy_button,
        feedback.save_button,
        feedback.submit_button,
        feedback.close_button,
    ):
        area = QRect(control.mapTo(feedback, QPoint(0, 0)), control.size())
        assert feedback.rect().contains(area)
    assert feedback.confirm.geometry().bottom() < feedback.submit_button.geometry().top()
    for combo in feedback.combos:
        assert combo.width() >= combo.sizeHint().width()
        assert combo.height() >= combo.minimumHeight()
    scroll = feedback.content_scroll.verticalScrollBar()
    scroll.setValue(scroll.maximum())
    app.processEvents()
    assert feedback.heading.pos() == heading_position
    assert (
        feedback.preview.mapTo(
            feedback.content_scroll.viewport(), feedback.preview.rect().bottomLeft()
        ).y()
        <= feedback.content_scroll.viewport().height()
    )
    assert not feedback.grab().isNull()


def test_mac_feedback_stays_local_until_confirmed_and_explains_url_transfer(host, monkeypatch):
    app, parent = host
    opened = []
    monkeypatch.setattr(analysis_qt.QDesktopServices, "openUrl", opened.append)
    feedback = analysis_qt.FeedbackDialog(synthetic_report(), parent)
    assert "sent to GitHub in the link" in feedback.explanation.text()
    feedback.submit()
    feedback.close_button.click()
    assert opened == []
    feedback.combos[0].setCurrentIndex(feedback.combos[0].findData("paper"))
    feedback.comment.setPlainText("Synthetic review comment")
    before = feedback.markdown
    parent.setProperty("tomcAppearance", "dark")
    parent.language.set_language("zh")
    parent.language.set_language("en")
    app.processEvents()
    assert feedback.markdown == before and opened == []
    assert "Synthetic conversation" not in before
    assert feedback.combos[0].currentData() == "paper"
    monkeypatch.setattr(analysis_qt, "feedback_url", lambda *args: "https://example.test/review")
    feedback.confirm.setChecked(True)
    feedback.submit()
    assert len(opened) == 1
    assert "sent to GitHub in the link" in feedback.status.text()
    assert "nothing is submitted" not in parent.messages[-1][0][1]


@pytest.mark.parametrize("appearance", ["light", "dark"])
def test_feedback_opened_from_analysis_inherits_parent_appearance_in_modal_loop(
    host, monkeypatch, appearance
):
    app, parent = host
    page = analysis_qt.AnalysisPage(parent)
    QVBoxLayout(parent).addWidget(page)
    page.report = synthetic_report()
    page.render()
    parent.setProperty("tomcAppearance", appearance)
    parent.show()
    app.processEvents()
    observed = []
    original_exec = analysis_qt.FeedbackDialog.exec

    def inspect_modal(dialog):
        def inspect_and_close():
            observed.append(
                (
                    dialog.isVisible(),
                    dialog.property("tomcAppearance"),
                    dialog.grab().toImage().pixelColor(0, 0),
                    dialog.heading.palette().color(QPalette.ColorRole.WindowText),
                )
            )
            dialog.reject()

        QTimer.singleShot(0, inspect_and_close)
        return original_exec(dialog)

    monkeypatch.setattr(analysis_qt.FeedbackDialog, "exec", inspect_modal)
    page.open_feedback()
    colors = macos_ui.tokens(parent)
    assert observed == [(True, None, QColor(colors["background"]), QColor(colors["text"]))]


def test_windows_analysis_and_feedback_keep_legacy_presentation(host, monkeypatch):
    _, parent = host
    monkeypatch.setattr(analysis_qt, "is_macos", lambda: False)
    monkeypatch.setattr(macos_ui, "is_macos", lambda: False)
    parent.setStyleSheet("QWidget { color: #443B35; }")
    page = analysis_qt.AnalysisPage(parent)
    assert "background: #FFFFFF" in page.table.styleSheet()
    assert page.conversation_donut.width() == 150 and page.coverage_bars.row_height == 24
    feedback = analysis_qt.FeedbackDialog(synthetic_report(), parent)
    assert feedback.size().width() == 820 and feedback.size().height() == 720
    assert type(feedback.confirm) is QCheckBox
    assert feedback.comment.maximumHeight() == 80
    assert not hasattr(feedback, "content_scroll")
    assert "nothing is sent until you confirm there" in feedback.explanation.text()
