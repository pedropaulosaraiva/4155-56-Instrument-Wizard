"""
views/pages/table_page.py
-------------------------
Table View page — pure View layer.

Displays the data dict produced by a DataFetchTask (one numeric sequence per
variable name, e.g. ``{"V1": [...], "I1": [...]}``) as a simple table: one
column per variable, one row per sample index.

MVP rules
---------
- No model/presenter imports — data arrives through ``display_data``.
- All QSS comes from stylesheets.py; no hex literals appear here.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import (
    data_table_stylesheet,
    table_empty_label_stylesheet,
    table_page_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage


class TablePageView(BasePage):
    """Renders fetched measurement data as a column-per-variable table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(table_page_stylesheet())
        self._setup_ui()

    def _setup_ui(self) -> None:
        # Stacked layout: empty-state label OR the populated table.
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(24, 20, 24, 20)

        self._empty_label = QLabel(tr_ui(CommandWizardText.TABLE_EMPTY))
        self._empty_label.setStyleSheet(table_empty_label_stylesheet())
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._empty_label)

        self._table = QTableWidget()
        self._table.setStyleSheet(data_table_stylesheet())
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._stack.addWidget(self._table)

        self._stack.setCurrentWidget(self._empty_label)

    # ── Display API ────────────────────────────────────────────────────────

    def display_data(self, data: dict[str, Sequence[float]]) -> None:
        """Populate the table from a {variable: values} mapping."""
        if not data:
            self._stack.setCurrentWidget(self._empty_label)
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
                text = f"{values[row]:.6g}" if row < len(values) else ""
                item = QTableWidgetItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._table.setItem(row, col, item)

        self._stack.setCurrentWidget(self._table)
