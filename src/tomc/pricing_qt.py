"""Separate, on-demand reference sheet; the cat's small popover stays small."""

import json
from html import escape

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .cost_estimate import SETTINGS, dollars, explanation, input_value, is_english
from .impact_story import story_html
from .macos_ui import install_macos_style, is_macos, tokens
from .pricing_catalog import all_rates


class Choice(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if is_macos():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#81796D"), 1.3))
        x, y = self.width() - 13, self.height() // 2
        painter.drawLine(x - 3, y - 1, x, y + 2)
        painter.drawLine(x, y + 2, x + 3, y - 1)


class ReferenceSheet(QDialog):
    def __init__(self, owner, settings_path=None):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.language = getattr(owner, "language", None)
        self.applied = False
        self.notice = None
        self._mac = is_macos()
        self.path = settings_path or SETTINGS
        self.setWindowTitle("TOMC · 模型与估价")
        if self._mac:
            self.resize(840, 800)
            self.setMinimumSize(720, 660)
        else:
            self.resize(520, 530)
            self.setStyleSheet("""
            QDialog, QWidget { background: #FFFCF7; color: #443B35; font-family: 'Microsoft YaHei UI'; font-size: 11px; }
            QComboBox, QTextBrowser, QTableWidget { border: 1px solid #E5DFD4; border-radius: 5px; padding: 4px; }
            QComboBox { min-height: 22px; padding-left: 8px; }
            QComboBox::drop-down { border: none; width: 20px; }
            QPushButton { border: none; border-radius: 7px; background: #E4ECE5; padding: 7px 12px; color: #345743; }
            QPushButton:hover { background: #D6E3D8; }
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: #F0EDE5; border: none; border-radius: 6px; padding: 8px 20px; margin-right: 6px; }
            QTabBar::tab:selected { background: #E4ECE5; color: #345743; }
            QTableWidget { selection-background-color: #E4ECE5; selection-color: #345743; }
            QHeaderView::section { background: #F0EDE5; border: none; padding: 5px; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 0; }
            QScrollBar::handle:vertical { background: #D4CEC2; border-radius: 3px; min-height: 24px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(*(20, 18, 20, 16) if self._mac else (14, 12, 14, 12))
        if self._mac:
            outer.setSpacing(12)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        if self._mac:
            page_layout.setContentsMargins(16, 18, 16, 14)
            page_layout.setSpacing(12)
            self.reference_scroll = QScrollArea()
            self.reference_scroll.setWidgetResizable(True)
            self.reference_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            content = QWidget()
            layout = QVBoxLayout(content)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            self.reference_scroll.setWidget(content)
            page_layout.addWidget(self.reference_scroll, 1)
        else:
            layout = page_layout
        self.tabs.addTab(page, "模型与估价")
        row = QHBoxLayout()
        self.host = Choice()
        for name in ("claude", "codex", "cursor", "其他 / API"):
            self.host.addItem(name, name)
        self.provider = Choice()
        for key, name in (
            ("anthropic", "Claude 官方"),
            ("openai", "OpenAI / Codex"),
            ("deepseek", "DeepSeek"),
            ("cursor", "Cursor"),
        ):
            self.provider.addItem(name, key)
        self.host_label = QLabel("宿主")
        if self._mac:
            self.provider_label = QLabel()
            self.models_label = QLabel()
            self.mode_label = QLabel()
            controls = QGridLayout()
            controls.setHorizontalSpacing(14)
            controls.setVerticalSpacing(7)
            controls.setColumnStretch(0, 3)
            controls.setColumnStretch(1, 2)
            controls.addWidget(self.host_label, 0, 0)
            controls.addWidget(self.provider_label, 0, 1)
            controls.addWidget(self.host, 1, 0)
            controls.addWidget(self.provider, 1, 1)
            controls.addWidget(self.models_label, 2, 0)
            controls.addWidget(self.mode_label, 2, 1)
            layout.addLayout(controls)
        else:
            row.addWidget(self.host_label)
            row.addWidget(self.host)
            row.addWidget(self.provider, 1)
            layout.addLayout(row)
        self.models = Choice()
        self.models.setMinimumContentsLength(15)
        self.models.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.models.setMaxVisibleItems(12)
        if self._mac:
            controls.addWidget(self.models, 3, 0)
        else:
            layout.addWidget(self.models)
        self.mode = Choice()
        self.mode.addItem("按未缓存输入折算", "input")
        self.mode.addItem("按缓存读取折算", "cached")
        if self._mac:
            controls.addWidget(self.mode, 3, 1)
            for choice in (self.host, self.provider, self.models, self.mode):
                choice.setMinimumHeight(34)
                choice.setMinimumWidth(0)
                choice.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )
            self.models.setMinimumContentsLength(18)
            self.mode.setMinimumContentsLength(16)
        else:
            layout.addWidget(self.mode)
        self.preview = QLabel()
        if self._mac:
            self.preview.setObjectName("title")
            self.preview.setWordWrap(True)
        else:
            self.preview.setStyleSheet("font-size: 17px; color: #345743; font-weight: 600;")
        layout.addWidget(self.preview)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["参考模型 / 档位", "输入", "缓存读", "输出", "折算 USD"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        if self._mac:
            self.table.setMinimumHeight(170)
            self.table.setAlternatingRowColors(True)
            self.table.setWordWrap(False)
            self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
            self.table.verticalHeader().setDefaultSectionSize(34)
            header = self.table.horizontalHeader()
            header.setMinimumSectionSize(80)
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for column in range(1, 5):
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
                header.setDefaultAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
        else:
            self.table.setMinimumHeight(140)
            self.table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            self.table.horizontalHeader().setMaximumSectionSize(215)
            self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.select_table)
        layout.addWidget(self.table, 3 if self._mac else 0)
        self.units = QLabel()
        self.units.setWordWrap(True)
        layout.addWidget(self.units)
        self.basis = QTextBrowser()
        self.basis.setOpenExternalLinks(True)
        self.basis.setMinimumHeight(150 if self._mac else 125)
        layout.addWidget(self.basis, 2 if self._mac else 0)
        if self._mac:
            self.action_status = QLabel()
            self.action_status.setObjectName("muted")
            self.action_status.setWordWrap(True)
            self.action_status.setMinimumHeight(18)
            page_layout.addWidget(self.action_status)
        actions = QHBoxLayout()
        self.detected_button = QPushButton("使用已识别模型")
        self.detected_button.clicked.connect(self.use_detected)
        actions.addWidget(self.detected_button)
        if self._mac:
            actions.addStretch()
        self.save_button = QPushButton("应用参考模型")
        self.save_button.clicked.connect(self.save)
        if self._mac:
            self.save_button.setObjectName("primary")
        self.save_button.setEnabled(not owner.test_mode or settings_path is not None)
        if owner.test_mode and settings_path is None:
            self.save_button.setText("演示不保存设置")
        actions.addWidget(self.save_button)
        page_layout.addLayout(actions)
        story = QTextBrowser()
        story.setOpenExternalLinks(True)
        self.tabs.addTab(story, "绿洲的故事")
        self.story = story
        self.close_button = QPushButton("收起")
        self.close_button.clicked.connect(self.hide)
        outer.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)
        if self._mac:
            # Return in a combo/table must not invoke the first dialog button.
            for button in (self.detected_button, self.save_button, self.close_button):
                button.setAutoDefault(False)
                button.installEventFilter(self)
        self.rates = list(all_rates())
        self.evidence = "手选参考模型；未读取实际调用的模型、缓存和档位"
        self.provider.currentIndexChanged.connect(self.populate)
        self.models.currentIndexChanged.connect(self.manual_change)
        self.mode.currentIndexChanged.connect(self.update_preview)
        self.host.currentIndexChanged.connect(self.update_preview)
        pricing = owner.pricing or {}
        self.host.setCurrentIndex(max(0, self.host.findData(pricing.get("host", "claude"))))
        self.provider.setCurrentIndex(
            max(0, self.provider.findData(pricing.get("provider", "anthropic")))
        )
        self.populate()
        if pricing:
            self.models.setCurrentIndex(max(0, self.models.findData(pricing.get("key"))))
            self.mode.setCurrentIndex(max(0, self.mode.findData(pricing.get("mode", "input"))))
            self.evidence = pricing.get("evidence", self.evidence)
        if self.language is not None:
            self.language.changed.connect(self.retranslate)
        self.retranslate()
        if self._mac:
            install_macos_style(self, variant="window")
            self._refresh_macos_documents()

    def tr_text(self, zh, en):
        return en if is_english(self.language) else zh

    def _set_browser_html(self, browser, html):
        if self._mac:
            colors = tokens(self)
            browser.document().setDefaultFont(self.font())
            browser.document().setDocumentMargin(14)
            browser.document().setDefaultStyleSheet(
                f"body {{ color: {colors['text']}; }}"
                f"a {{ color: {colors['accent']}; }}"
                "p { margin-top: 10px; margin-bottom: 12px; line-height: 140%; }"
                "h3 { font-size: 20px; margin-top: 4px; margin-bottom: 14px; }"
            )
            browser._tomc_reference_html = html
        browser.setHtml(html)

    def _refresh_macos_documents(self):
        if not getattr(self, "_mac", False):
            return
        for browser in (getattr(self, "basis", None), getattr(self, "story", None)):
            if browser is None or not hasattr(browser, "_tomc_reference_html"):
                continue
            vertical = browser.verticalScrollBar().value()
            horizontal = browser.horizontalScrollBar().value()
            self._set_browser_html(browser, browser._tomc_reference_html)
            browser.verticalScrollBar().setValue(vertical)
            browser.horizontalScrollBar().setValue(horizontal)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._refresh_macos_documents()

    def eventFilter(self, watched, event):
        if (
            self._mac
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and watched.hasFocus()
            and watched.isEnabled()
        ):
            # These filters belong only to the three action buttons. Keep explicit
            # keyboard activation without making them implicit dialog-wide defaults.
            if not event.isAutoRepeat():
                watched.click()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def retranslate(self, *_):
        model_key = self.models.currentData()
        self.setWindowTitle(self.tr_text("TOMC · 模型与估价", "TOMC · Models & estimates"))
        self.tabs.setTabText(0, self.tr_text("模型与估价", "Models && estimates"))
        self.tabs.setTabText(1, self.tr_text("绿洲的故事", "The oasis story"))
        self.host_label.setText(self.tr_text("宿主", "Host"))
        if self._mac:
            self.provider_label.setText(self.tr_text("价格供应商", "Price provider"))
            self.models_label.setText(self.tr_text("参考模型与档位", "Reference model / tier"))
            self.mode_label.setText(self.tr_text("计价方式", "Pricing basis"))
        self.host.setItemText(3, self.tr_text("其他 / API", "Other / API"))
        self.provider.setItemText(0, self.tr_text("Claude 官方", "Anthropic / Claude"))
        self.mode.setItemText(0, self.tr_text("按未缓存输入折算", "Use uncached input rate"))
        self.mode.setItemText(1, self.tr_text("按缓存读取折算", "Use cache-read rate"))
        self.table.setHorizontalHeaderLabels(
            self.tr_text(
                ["参考模型 / 档位", "输入", "缓存读", "输出", "折算 USD"],
                ["Reference model / tier", "Input", "Cache read", "Output", "Value (USD)"],
            )
        )
        if self._mac:
            for column in range(self.table.columnCount()):
                self.table.horizontalHeaderItem(column).setTextAlignment(
                    (Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignRight)
                    | Qt.AlignmentFlag.AlignVCenter
                )
        self.units.setText(
            self.tr_text(
                "单价：USD / 百万 tokens · 折算使用当前统计范围；负值表示增加",
                "Rates: USD per million tokens. Values use the current range; negative values indicate an increase.",
            )
        )
        self.detected_button.setText(self.tr_text("使用已识别模型", "Use detected model"))
        self.close_button.setText(self.tr_text("收起", "Close"))
        self._set_browser_html(self.story, story_html(self.language))
        self.host.setAccessibleName(self.tr_text("参考模型宿主", "Reference model host"))
        self.provider.setAccessibleName(self.tr_text("参考价格供应商", "Reference price provider"))
        self.models.setAccessibleName(self.tr_text("参考模型与档位", "Reference model and tier"))
        self.mode.setAccessibleName(
            self.tr_text("参考输入计价口径", "Reference input pricing basis")
        )
        self.table.setAccessibleName(self.tr_text("参考费率对照表", "Reference rate comparison"))
        self.basis.setAccessibleName(
            self.tr_text("价格依据与估算限制", "Pricing evidence and estimate limitations")
        )
        self.story.setAccessibleName(
            self.tr_text("绿洲故事与研究依据", "Oasis story and research reference")
        )
        self.models.setToolTip(
            self.tr_text(
                "只选择参考价格，不切换宿主实际模型。",
                "Selects a reference price; it does not change the host's actual model.",
            )
        )
        self.detected_button.setToolTip(
            self.tr_text(
                "读取已有识别记录，不调用模型或联网检测。",
                "Reads an existing detection record; no model call or network lookup.",
            )
        )
        self.populate()
        self.models.blockSignals(True)
        self.models.setCurrentIndex(max(0, self.models.findData(model_key)))
        self.models.blockSignals(False)
        self.update_save_label()
        self.update_preview()

    def update_save_label(self):
        if not self.save_button.isEnabled():
            text = self.tr_text("演示不保存设置", "Demo: settings are not saved")
        elif self.applied:
            text = self.tr_text(
                "已应用 · 宿主额度下次启动切换", "Applied · Allowance host changes on restart"
            )
        else:
            text = self.tr_text("应用参考模型", "Apply reference model")
        if self._mac:
            status = text if self.applied or not self.save_button.isEnabled() else ""
            self.action_status.setText(status)
            self.action_status.setVisible(bool(status))
            self.save_button.setText(self.tr_text("应用参考模型", "Apply reference model"))
            self.save_button.setToolTip(text)
        else:
            self.save_button.setText(text)

    def delta(self):
        groups = (self.owner.summary or {}).get("by_counter", [])
        return groups[0]["reduced_tokens"] if len(groups) == 1 else None

    def manual_change(self):
        self.notice = None
        self.applied = False
        self.evidence = "手选参考模型；未读取实际调用的模型、缓存和档位"
        self.update_save_label()
        self.update_preview()

    def populate(self):
        self.models.blockSignals(True)
        self.models.clear()
        self.models.addItem(
            self.tr_text(
                "未确认 / Auto（不估算金额）", "Unconfirmed / Auto (no monetary estimate)"
            ),
            None,
        )
        self.rows = [r for r in self.rates if r["provider"] == self.provider.currentData()]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.rows))
        for index, rate in enumerate(self.rows):
            self.models.addItem(f"{rate['label']} · {rate['variant']}", rate["key"])
            values = [
                f"{rate['label']} · {rate['variant']}",
                rate["input"],
                rate["cached"],
                rate["output"],
                "",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem("—" if value is None else str(value))
                if self._mac:
                    item.setTextAlignment(
                        (Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignRight)
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                    if column == 0:
                        item.setToolTip(item.text())
                self.table.setItem(index, column, item)
        self.table.blockSignals(False)
        self.models.blockSignals(False)
        self.update_preview()

    def selected(self):
        row = next((r for r in self.rates if r["key"] == self.models.currentData()), None)
        if not row or row.get(self.mode.currentData()) is None:
            return None
        return {
            **row,
            "mode": self.mode.currentData(),
            "rate": row[self.mode.currentData()],
            "host": self.host.currentData(),
            "evidence": self.evidence,
        }

    def update_preview(self):
        pricing = self.selected()
        self.preview.setText(
            self.tr_text("当前范围参考价值  ", "Reference value for this range  ")
            + dollars(input_value(self.delta(), pricing))
        )
        text = escape(explanation(pricing, self.language)).replace("\n", "<br>")
        if self.notice:
            text = escape(self.tr_text(*self.notice)) + "<br><br>" + text
        if pricing and pricing.get("source"):
            url = escape(pricing["source"], quote=True)
            link = self.tr_text("查看官方定价依据 ↗", "View official pricing source ↗")
            text = text.replace(url, f'<a href="{url}">{link}</a>')
        self._set_browser_html(self.basis, text)
        for index, row in enumerate(getattr(self, "rows", [])):
            rate = row.get(self.mode.currentData())
            value = input_value(self.delta(), {"rate": rate}) if rate is not None else None
            self.table.item(index, 4).setText(
                ("−" if value is not None and value < 0 else "") + dollars(value)
            )

    def select_table(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.models.setCurrentIndex(self.models.findData(self.rows[row]["key"]))

    def use_detected(self):
        try:
            data = json.loads((SETTINGS.parent / "detected_models.json").read_text("utf-8"))
            row = data["hosts"][self.host.currentData()]
            evidence = row["evidence"] + " · 检查于 " + data["checked_at"]
            self.provider.setCurrentIndex(max(0, self.provider.findData(row.get("provider"))))
            match = next(
                (
                    r
                    for r in self.rows
                    if r["model"] == row.get("model")
                    and r["variant"] in ("standard", "standard-short", "listed")
                ),
                None,
            )
            self.models.setCurrentIndex(self.models.findData(match["key"]) if match else 0)
            self.evidence = evidence
            self.notice = None
            if not match:
                self.notice = (
                    "识别记录未匹配到参考费率，请手选参考模型。",
                    "The detection record has no matching reference rate. Select a model manually.",
                )
            self.update_preview()
        except (OSError, ValueError, KeyError, TypeError):
            self.notice = (
                "尚无安装时的模型识别记录，请手选参考模型。",
                "No saved model-detection record is available. Select a reference model manually.",
            )
            self.update_preview()

    def save(self):
        row = self.selected()
        settings = {
            "host": self.host.currentData(),
            "provider": self.provider.currentData(),
            "model": row["model"] if row else None,
            "variant": row["variant"] if row else None,
            "input_mode": self.mode.currentData(),
            "selection": "manual",
            "evidence": "用户选定的参考模型；不代表每次实际调用",
            "assumption": "按所选档位折算；未确认实际发送量、缓存命中或账单",
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), "utf-8")
        self.owner.last_signature = None
        self.owner.refresh()
        self.applied = True
        self.update_save_label()

    def open_tab(self, index=0):
        self.owner.details.hide()
        self.tabs.setCurrentIndex(index)
        self.update_preview()
        self.show()
        self.raise_()
