"""
views/pages/table_page.py
-------------------------
Table View page — pure View layer.

Lets the user browse a measurement dataset and export it.  A dataset is chosen
through three combo boxes (Setup → Execution → Format) and rendered in the
central area either as a spreadsheet-like table (CSV / XLSX formats) or as a
syntax-highlighted code snippet (Pure Python / NumPy+Matplotlib / C / MATLAB).
A single action button toggles between **Download** (table formats) and
**Copy** (code formats); table formats add a **Save All** button (zip of every
execution) plus a format-specific export-options row, and the table columns
can be drag-reordered (exports follow the visual order).

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

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
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
    global_option_checkbox_stylesheet,
    runs_secondary_button_stylesheet,
    table_code_view_stylesheet,
    table_empty_label_stylesheet,
    table_page_stylesheet,
    table_selector_label_stylesheet,
    unit_card_combo_stylesheet,
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
    action_requested = Signal()  # Export run or Copy (presenter decides)
    save_all_requested = Signal()  # export every run as a .zip
    csv_option_changed = Signal(str)  # "delimiter" | "decimal" | "quote"

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

        root.addLayout(self._build_selectors())
        root.addWidget(self._build_options_row())

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

    def _build_options_row(self) -> QWidget:
        """Format-specific export options (visible for CSV/XLSX only)."""
        self._options_row = QWidget()
        row = QHBoxLayout(self._options_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._delim_combo = self._make_option_combo()
        self._delim_combo.currentIndexChanged.connect(
            lambda _i: self.csv_option_changed.emit("delimiter")
        )
        self._decimal_combo = self._make_option_combo()
        self._decimal_combo.currentIndexChanged.connect(
            lambda _i: self.csv_option_changed.emit("decimal")
        )
        self._quote_combo = self._make_option_combo()
        self._quote_combo.currentIndexChanged.connect(
            lambda _i: self.csv_option_changed.emit("quote")
        )

        delim_label = self._label(CommandWizardText.TABLE_DELIM_LABEL)
        decimal_label = self._label(CommandWizardText.TABLE_DECIMAL_LABEL)
        quote_label = self._label(CommandWizardText.TABLE_QUOTE_LABEL)

        row.addWidget(delim_label)
        row.addWidget(self._delim_combo)
        row.addSpacing(12)
        row.addWidget(decimal_label)
        row.addWidget(self._decimal_combo)
        row.addSpacing(12)
        row.addWidget(quote_label)
        row.addWidget(self._quote_combo)
        row.addSpacing(16)

        self._datetime_check = QCheckBox(
            tr_ui(CommandWizardText.TABLE_DATETIME_CHECK)
        )
        self._datetime_check.setStyleSheet(
            global_option_checkbox_stylesheet()
        )
        self._datetime_check.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._datetime_check)
        row.addStretch()

        self._save_all_btn = QPushButton(
            tr_ui(CommandWizardText.TABLE_BTN_SAVE_ALL)
        )
        self._save_all_btn.setStyleSheet(runs_secondary_button_stylesheet())
        self._save_all_btn.setIcon(app_icon(AppIcon24.SAVE))
        self._save_all_btn.setIconSize(QSize(16, 16))
        self._save_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_all_btn.clicked.connect(self.save_all_requested.emit)
        row.addWidget(self._save_all_btn)

        self._csv_only = [
            delim_label,
            self._delim_combo,
            decimal_label,
            self._decimal_combo,
            quote_label,
            self._quote_combo,
        ]
        self._options_row.setVisible(False)
        return self._options_row

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
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self._on_section_moved)
        self._column_order: list[str] = []
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

    def set_csv_option_items(
        self,
        delimiters: Sequence[str],
        decimals: Sequence[str],
        quotes: Sequence[str],
    ) -> None:
        for combo, labels in (
            (self._delim_combo, delimiters),
            (self._decimal_combo, decimals),
            (self._quote_combo, quotes),
        ):
            combo.blockSignals(True)
            combo.clear()
            for label in labels:
                combo.addItem(label)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)

    def set_export_options_mode(self, mode: str) -> None:
        """Show the options row for ``"csv"`` (all options) or ``"xlsx"``
        (filename checkbox only); ``"hidden"`` hides the whole row."""
        self._options_row.setVisible(mode in ("csv", "xlsx"))
        for widget in self._csv_only:
            widget.setVisible(mode == "csv")

    def select_csv_options(
        self, delimiter_index: int, decimal_index: int, quote_index: int
    ) -> None:
        """Programmatically set the CSV dialect combos (no signals)."""
        for combo, index in (
            (self._delim_combo, delimiter_index),
            (self._decimal_combo, decimal_index),
            (self._quote_combo, quote_index),
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def show_csv_option_tooltip(self, which: str, text: str) -> None:
        """Balloon *text* under the combo named by *which* (rejected combo)."""
        combo = {
            "delimiter": self._delim_combo,
            "decimal": self._decimal_combo,
            "quote": self._quote_combo,
        }.get(which, self._delim_combo)
        QToolTip.showText(
            combo.mapToGlobal(QPoint(0, combo.height())), text, combo
        )

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

    def current_delimiter_index(self) -> int:
        return self._delim_combo.currentIndex()

    def current_decimal_index(self) -> int:
        return self._decimal_combo.currentIndex()

    def current_quote_index(self) -> int:
        return self._quote_combo.currentIndex()

    def datetime_in_filename(self) -> bool:
        return self._datetime_check.isChecked()

    def current_column_order(self) -> list[str]:
        """Column names in the current *visual* (drag-adjusted) order."""
        header = self._table.horizontalHeader()
        order: list[str] = []
        for visual in range(self._table.columnCount()):
            item = self._table.horizontalHeaderItem(
                header.logicalIndex(visual)
            )
            if item is not None:
                order.append(item.text())
        return order

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

    def set_save_all_visible(self, visible: bool) -> None:
        self._save_all_btn.setVisible(visible)

    def set_save_all_enabled(self, enabled: bool) -> None:
        self._save_all_btn.setEnabled(enabled)

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
        self._apply_column_order(columns)
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
    def _make_option_combo() -> QComboBox:
        combo = QComboBox()
        combo.setStyleSheet(unit_card_combo_stylesheet())
        return combo

    def _apply_column_order(self, columns: Sequence[str]) -> None:
        """Re-apply the remembered visual order after a table re-render."""
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        # Reset any stale visual mapping left over from the previous render.
        for logical in range(self._table.columnCount()):
            visual = header.visualIndex(logical)
            if visual != logical:
                header.moveSection(visual, logical)
        if set(self._column_order) == set(columns):
            name_to_logical = {name: i for i, name in enumerate(columns)}
            for target_visual, name in enumerate(self._column_order):
                visual = header.visualIndex(name_to_logical[name])
                if visual != target_visual:
                    header.moveSection(visual, target_visual)
        else:
            # Different variable set — forget the stale order.
            self._column_order = list(columns)
        header.blockSignals(False)

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

    def _on_section_moved(self, *_args) -> None:
        self._column_order = self.current_column_order()
