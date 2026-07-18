"""
views/pages/table_page.py
-------------------------
Table View page — pure View layer.

Lets the user browse a measurement dataset and export it.  A dataset is chosen
through three combo boxes (Setup → Execution → Format) and rendered in the
central area either as a spreadsheet-like table (CSV / XLSX formats) or as a
syntax-highlighted code snippet (Pure Python / NumPy+Matplotlib / C / MATLAB).
A single action button toggles between **Download** (table formats) and
**Copy** (code formats).

MVP rules
---------
- No model/presenter/DB imports — the presenter pushes combo items as plain
  ``(id, label)`` tuples (executions add a synthetic-run flag) and rendered
  content via ``display_*``; the view only emits user-intent signals.
- All QSS comes from stylesheets.py; no hex literals appear here.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.icons import (
    AppIcon24,
    accent_button_icon,
    app_icon,
)
from wizard_4155_4156.styles.stylesheets import (
    config_combo_stylesheet,
    data_table_stylesheet,
    error_bar_stylesheet,
    export_btn_stylesheet,
    section_title_stylesheet,
    table_code_view_stylesheet,
    table_empty_label_stylesheet,
    table_page_stylesheet,
    table_selector_label_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.code_highlighter import CodeHighlighter

_PAGE_EMPTY = 0
_PAGE_TABLE = 1
_PAGE_CODE = 2


class TablePageView(BasePage):
    """Setup/Execution/Format selectors above a table-or-code central area."""

    page_activated = Signal()
    setup_changed = Signal(int)
    execution_changed = Signal(int)
    format_changed = Signal(int)  # carries the format combo index
    action_requested = Signal()  # Download or Copy (presenter decides which)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(table_page_stylesheet())
        self._setup_ui()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel(tr_ui(CommandWizardText.TABLE_PAGE_TITLE))
        title.setStyleSheet(section_title_stylesheet())
        root.addWidget(title)

        root.addLayout(self._build_selectors())

        self._error = QLabel("")
        self._error.setStyleSheet(error_bar_stylesheet())
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        root.addWidget(self._error)

        root.addWidget(self._build_content(), stretch=1)

    def _build_selectors(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._setup_combo = self._make_combo()
        self._setup_combo.currentIndexChanged.connect(self._on_setup_changed)
        self._exec_combo = self._make_combo()
        self._exec_combo.currentIndexChanged.connect(self._on_exec_changed)
        self._format_combo = self._make_combo()
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        row.addWidget(self._label(CommandWizardText.TABLE_SETUP_LABEL))
        row.addWidget(self._setup_combo)
        row.addSpacing(12)
        row.addWidget(self._label(CommandWizardText.TABLE_EXEC_LABEL))
        row.addWidget(self._exec_combo)
        row.addSpacing(12)
        row.addWidget(self._label(CommandWizardText.TABLE_FORMAT_LABEL))
        row.addWidget(self._format_combo)
        row.addStretch()

        self._action_btn = QPushButton()
        self._action_btn.setStyleSheet(export_btn_stylesheet())
        self._action_btn.setIconSize(QSize(16, 16))
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.clicked.connect(self.action_requested.emit)
        self.set_action_mode("download")
        row.addWidget(self._action_btn)
        return row

    def _build_content(self) -> QWidget:
        self._stack = QStackedWidget()

        self._empty = QLabel(tr_ui(CommandWizardText.TABLE_EMPTY))
        self._empty.setStyleSheet(table_empty_label_stylesheet())
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._empty)  # _PAGE_EMPTY

        self._table = QTableWidget()
        self._table.setStyleSheet(data_table_stylesheet())
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._stack.addWidget(self._table)  # _PAGE_TABLE

        self._code = QPlainTextEdit()
        self._code.setReadOnly(True)
        self._code.setStyleSheet(table_code_view_stylesheet())
        self._code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = CodeHighlighter(self._code.document())
        self._stack.addWidget(self._code)  # _PAGE_CODE

        return self._stack

    # ── Display API (called by presenter) ────────────────────────────────────

    def display_setups(self, items: Sequence[tuple[int, str]]) -> None:
        self._reload_combo(self._setup_combo, items)

    def display_executions(
        self, items: Sequence[tuple[int, str, bool]]
    ) -> None:
        """Reload the execution combo; flagged (synthetic) entries get a
        bookmark icon in place of the old inline glyph."""
        combo = self._exec_combo
        combo.blockSignals(True)
        combo.clear()
        for value, label, synthetic in items:
            if synthetic:
                combo.addItem(app_icon(AppIcon24.BOOKMARK), label, value)
            else:
                combo.addItem(label, value)
        combo.blockSignals(False)

    def set_formats(self, labels: Sequence[str]) -> None:
        self._format_combo.blockSignals(True)
        self._format_combo.clear()
        for label in labels:
            self._format_combo.addItem(label)
        self._format_combo.blockSignals(False)

    def select_setup(self, setup_id: int) -> None:
        self._select_by_data(self._setup_combo, setup_id)

    def select_execution(self, execution_id: int) -> None:
        self._select_by_data(self._exec_combo, execution_id)

    def select_format(self, index: int) -> None:
        self._format_combo.blockSignals(True)
        self._format_combo.setCurrentIndex(index)
        self._format_combo.blockSignals(False)

    def current_setup_id(self) -> int | None:
        data = self._setup_combo.currentData()
        return None if data is None else int(data)

    def current_execution_id(self) -> int | None:
        data = self._exec_combo.currentData()
        return None if data is None else int(data)

    def current_format_index(self) -> int:
        return self._format_combo.currentIndex()

    def set_action_mode(self, mode: str) -> None:
        """Switch the action button persona: ``"download"`` or ``"copy"``."""
        if mode == "copy":
            text, icon = CommandWizardText.TABLE_BTN_COPY, AppIcon24.COPY
        else:
            text, icon = (
                CommandWizardText.TABLE_BTN_DOWNLOAD,
                AppIcon24.DOWNLOAD,
            )
        self._action_btn.setText(tr_ui(text))
        self._action_btn.setIcon(accent_button_icon(icon))

    def set_action_enabled(self, enabled: bool) -> None:
        self._action_btn.setEnabled(enabled)

    def display_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def display_empty(self, message: str) -> None:
        self._empty.setText(message)
        self._stack.setCurrentIndex(_PAGE_EMPTY)

    def display_table(self, data: dict[str, Sequence[float]]) -> None:
        if not data:
            self.display_empty(tr_ui(CommandWizardText.TABLE_EMPTY))
            return
        columns = list(data.keys())
        row_count = max((len(values) for values in data.values()), default=0)

        self._table.clear()
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setRowCount(row_count)
        for col, name in enumerate(columns):
            values = data[name]
            for row in range(row_count):
                # Non-finite points (e.g. blank cells in imported files) are
                # shown blank, matching the CSV/XLSX export convention.
                text = (
                    f"{values[row]:.6g}"
                    if row < len(values) and math.isfinite(values[row])
                    else ""
                )
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._table.setItem(row, col, item)
        self._stack.setCurrentIndex(_PAGE_TABLE)

    def display_code(self, text: str, language: str | None) -> None:
        self._highlighter.set_language(language)
        self._code.setPlainText(text)
        self._stack.setCurrentIndex(_PAGE_CODE)

    # ── Internal helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _make_combo() -> QComboBox:
        combo = QComboBox()
        combo.setStyleSheet(config_combo_stylesheet())
        return combo

    @staticmethod
    def _label(text: CommandWizardText) -> QLabel:
        label = QLabel(tr_ui(text))
        label.setStyleSheet(table_selector_label_stylesheet())
        return label

    @staticmethod
    def _reload_combo(
        combo: QComboBox, items: Sequence[tuple[int, str]]
    ) -> None:
        combo.blockSignals(True)
        combo.clear()
        for value, label in items:
            combo.addItem(label, value)
        combo.blockSignals(False)

    @staticmethod
    def _select_by_data(combo: QComboBox, value: int) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    # ── Qt slots → signals ───────────────────────────────────────────────────

    def _on_setup_changed(self) -> None:
        setup_id = self.current_setup_id()
        if setup_id is not None:
            self.setup_changed.emit(setup_id)

    def _on_exec_changed(self) -> None:
        execution_id = self.current_execution_id()
        if execution_id is not None:
            self.execution_changed.emit(execution_id)

    def _on_format_changed(self) -> None:
        index = self._format_combo.currentIndex()
        if index >= 0:
            self.format_changed.emit(index)
