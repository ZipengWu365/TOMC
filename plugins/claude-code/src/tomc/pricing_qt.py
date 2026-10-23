"""Separate, on-demand reference sheet; the cat's small popover stays small."""

import json
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .cost_estimate import SETTINGS, dollars, explanation, input_value
from .impact_story import STORY
from .pricing_catalog import all_rates


class Choice(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#81796D"), 1.3))
        x, y = self.width()-13, self.height()//2
        painter.drawLine(x-3, y-1, x, y+2)
        painter.drawLine(x, y+2, x+3, y-1)


class ReferenceSheet(QDialog):
    def __init__(self, owner, settings_path=None):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.path = settings_path or SETTINGS
        self.setWindowTitle("TOMC · 模型与估价")
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
        outer.setContentsMargins(14, 12, 14, 12)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        page = QWidget()
        layout = QVBoxLayout(page)
        self.tabs.addTab(page, "模型与估价")
        row = QHBoxLayout()
        self.host = Choice()
        for name in ("claude", "codex", "cursor", "其他 / API"):
            self.host.addItem(name, name)
        self.provider = Choice()
        for key, name in (("anthropic", "Claude 官方"), ("openai", "OpenAI / Codex"),
                          ("deepseek", "DeepSeek"), ("cursor", "Cursor")):
            self.provider.addItem(name, key)
        row.addWidget(QLabel("宿主"))
        row.addWidget(self.host)
        row.addWidget(self.provider, 1)
        layout.addLayout(row)
        self.models = Choice()
        self.models.setMinimumContentsLength(15)
        self.models.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.models.setMaxVisibleItems(12)
        layout.addWidget(self.models)
        self.mode = Choice()
        self.mode.addItem("按未缓存输入折算", "input")
        self.mode.addItem("按缓存读取折算", "cached")
        layout.addWidget(self.mode)
        self.preview = QLabel()
        self.preview.setStyleSheet("font-size: 17px; color: #345743; font-weight: 600;")
        layout.addWidget(self.preview)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["参考模型 / 档位", "输入", "缓存读", "输出", "折算 USD"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(140)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setMaximumSectionSize(215)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.select_table)
        layout.addWidget(self.table)
        layout.addWidget(QLabel("单价：USD / 百万 tokens · 折算使用当前统计范围；负值表示增加"))
        self.basis = QTextBrowser()
        self.basis.setOpenExternalLinks(True)
        self.basis.setMinimumHeight(125)
        layout.addWidget(self.basis)
        actions = QHBoxLayout()
        detected = QPushButton("使用已识别模型")
        detected.clicked.connect(self.use_detected)
        actions.addWidget(detected)
        self.save_button = QPushButton("应用参考模型")
        self.save_button.clicked.connect(self.save)
        self.save_button.setEnabled(not owner.test_mode or settings_path is not None)
        if owner.test_mode and settings_path is None:
            self.save_button.setText("演示不保存设置")
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        story = QTextBrowser()
        story.setOpenExternalLinks(True)
        story.setHtml(STORY)
        self.tabs.addTab(story, "绿洲的故事")
        self.story = story
        close = QPushButton("收起")
        close.clicked.connect(self.hide)
        outer.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.rates = list(all_rates())
        self.evidence = "手选参考模型；未读取实际调用的模型、缓存和档位"
        self.provider.currentIndexChanged.connect(self.populate)
        self.models.currentIndexChanged.connect(self.manual_change)
        self.mode.currentIndexChanged.connect(self.update_preview)
        self.host.currentIndexChanged.connect(self.update_preview)
        pricing = owner.pricing or {}
        self.host.setCurrentIndex(max(0, self.host.findData(pricing.get("host", "claude"))))
        self.provider.setCurrentIndex(max(0, self.provider.findData(pricing.get("provider", "anthropic"))))
        self.populate()
        if pricing:
            self.models.setCurrentIndex(max(0, self.models.findData(pricing.get("key"))))
            self.mode.setCurrentIndex(max(0, self.mode.findData(pricing.get("mode", "input"))))
            self.evidence = pricing.get("evidence", self.evidence)
        self.update_preview()

    def delta(self):
        groups = (self.owner.summary or {}).get("by_counter", [])
        return groups[0]["reduced_tokens"] if len(groups) == 1 else None

    def manual_change(self):
        self.evidence = "手选参考模型；未读取实际调用的模型、缓存和档位"
        self.update_preview()

    def populate(self):
        self.models.blockSignals(True)
        self.models.clear()
        self.models.addItem("未确认 / Auto（不估算金额）", None)
        self.rows = [r for r in self.rates if r["provider"] == self.provider.currentData()]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.rows))
        for index, rate in enumerate(self.rows):
            self.models.addItem(f"{rate['label']} · {rate['variant']}", rate["key"])
            values = [f"{rate['label']} · {rate['variant']}", rate["input"], rate["cached"], rate["output"], ""]
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem("—" if value is None else str(value)))
        self.table.blockSignals(False)
        self.models.blockSignals(False)
        self.update_preview()

    def selected(self):
        row = next((r for r in self.rates if r["key"] == self.models.currentData()), None)
        if not row or row.get(self.mode.currentData()) is None:
            return None
        return {**row, "mode": self.mode.currentData(), "rate": row[self.mode.currentData()],
                "host": self.host.currentData(), "evidence": self.evidence}

    def update_preview(self):
        pricing = self.selected()
        self.preview.setText("当前范围参考价值  " + dollars(input_value(self.delta(), pricing)))
        text = escape(explanation(pricing)).replace("\n", "<br>")
        if pricing and pricing.get("source"):
            url = escape(pricing["source"], quote=True)
            text = text.replace(url, f'<a href="{url}">查看官方定价依据 ↗</a>')
        self.basis.setHtml(text)
        for index, row in enumerate(getattr(self, "rows", [])):
            rate = row.get(self.mode.currentData())
            value = input_value(self.delta(), {"rate": rate}) if rate is not None else None
            self.table.item(index, 4).setText(("−" if value is not None and value < 0 else "") + dollars(value))

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
            match = next((r for r in self.rows if r["model"] == row.get("model") and
                          r["variant"] in ("standard", "standard-short", "listed")), None)
            self.models.setCurrentIndex(self.models.findData(match["key"]) if match else 0)
            self.evidence = evidence
            self.update_preview()
            if not match:
                self.basis.setPlainText(self.evidence + "\n" + explanation(None))
        except (OSError, ValueError, KeyError, TypeError):
            self.basis.setPlainText("尚无安装时的模型识别记录，请手选参考模型。")

    def save(self):
        row = self.selected()
        settings = {"host": self.host.currentData(), "provider": self.provider.currentData(),
                    "model": row["model"] if row else None, "variant": row["variant"] if row else None,
                    "input_mode": self.mode.currentData(), "selection": "manual",
                    "evidence": "用户选定的参考模型；不代表每次实际调用",
                    "assumption": "按所选档位折算；未确认实际发送量、缓存命中或账单"}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), "utf-8")
        self.owner.last_signature = None
        self.owner.refresh()
        self.save_button.setText("已应用 · 宿主额度下次启动切换")

    def open_tab(self, index=0):
        self.owner.details.hide()
        self.tabs.setCurrentIndex(index)
        self.update_preview()
        self.show()
        self.raise_()
