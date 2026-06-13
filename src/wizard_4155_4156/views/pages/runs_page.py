"""
views/pages/runs_page.py
------------------------
Measurement Runs page — a CRUD browser over the project database.

This is the new home for measurement *setups* and their *executions* (the
legacy ephemeral ``measurements_page.py`` is left untouched but unused).  Pure
View layer: it emits ``*_requested`` signals and renders state pushed in via
``display_*`` methods.  It imports only the Qt-free row DTOs
(``SetupRow``/``ExecRow``) — never the ORM — mirroring how the home page
imports ``ProjectData``.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.db.repository import ExecRow, SetupRow
from wizard_4155_4156.styles.stylesheets import (
    configure_measure_button_stylesheet,
    config_preview_tree_stylesheet,
    error_bar_stylesheet,
    export_btn_stylesheet,
    meas_status_label_stylesheet,
    recent_panel_header_stylesheet,
    runs_list_stylesheet,
    runs_page_stylesheet,
    runs_panel_title_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage

_ID_ROLE = Qt.ItemDataRole.UserRole


class RunsPageView(BasePage):
    """Three-pane browser: setups | executions | detail, with a toolbar."""

    page_activated = Signal()
    setup_selected = Signal(int)
    execution_selected = Signal(int)
    create_setup_requested = Signal(str, str)         # name, description
    edit_setup_metadata_requested = Signal(int, str, str)  # id, name, desc
    delete_setup_requested = Signal(int)
    delete_execution_requested = Signal(int)
    insert_sample_execution_requested = Signal(int)   # setup id
    view_execution_data_requested = Signal(int)       # execution id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(runs_page_stylesheet())
        self._setup_ui()
        self._update_button_state()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API (called by presenter) ────────────────────────────────────

    def display_setups(self, rows: list[SetupRow]) -> None:
        self._setups.clear()
        for row in rows:
            label = (
                f"{row.name}\n"
                f"   {row.type_label} · {row.instrument_model} · "
                f"{row.execution_count} run(s)"
            )
            item = QListWidgetItem(label)
            item.setData(_ID_ROLE, row.id)
            self._setups.addItem(item)
        # Selection cleared by clear(); dependent panes reset.
        self.display_executions([])
        self.display_setup_detail(None, "")
        self._update_button_state()

    def select_setup(self, setup_id: int) -> None:
        """Programmatically select the setup row with the given id."""
        for i in range(self._setups.count()):
            item = self._setups.item(i)
            if int(item.data(_ID_ROLE)) == setup_id:
                self._setups.setCurrentItem(item)
                return

    def display_executions(self, rows: list[ExecRow]) -> None:
        self._executions.clear()
        for row in rows:
            tag = "  (sample)" if row.is_synthetic else ""
            stamp = row.execution_date.strftime("%d/%m/%Y %H:%M")
            label = (
                f"{row.name}{tag}\n"
                f"   {stamp} · {row.instrument_model} · "
                f"{row.variable_count} var(s)"
            )
            item = QListWidgetItem(label)
            item.setData(_ID_ROLE, row.id)
            self._executions.addItem(item)
        self._update_button_state()

    def display_setup_detail(
        self, config: Optional[dict], summary: str
    ) -> None:
        self._detail.clear()
        self._summary.setText(summary)
        if config:
            self._populate_tree(self._detail, config)
            self._detail.expandToDepth(0)

    def display_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def display_status(self, text: str) -> None:
        self._status.setText(text)

    def display_empty(self, message: str) -> None:
        self._setups.clear()
        self.display_executions([])
        self.display_setup_detail(None, "")
        self._status.setText(message)
        self._update_button_state()

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        header = QLabel("Measurement Runs")
        header.setStyleSheet(recent_panel_header_stylesheet())
        root.addWidget(header)

        self._error = QLabel("")
        self._error.setStyleSheet(error_bar_stylesheet())
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        root.addWidget(self._error)

        root.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_setups_pane())
        splitter.addWidget(self._build_executions_pane())
        splitter.addWidget(self._build_detail_pane())
        splitter.setSizes([320, 320, 460])
        root.addWidget(splitter, stretch=1)

        self._status = QLabel("No project open.")
        self._status.setStyleSheet(meas_status_label_stylesheet())
        root.addWidget(self._status)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._btn_create = QPushButton("➕  Save current config as setup")
        self._btn_create.setStyleSheet(export_btn_stylesheet())
        self._btn_create.clicked.connect(self._on_create_clicked)

        self._btn_edit = QPushButton("✎  Edit metadata")
        self._btn_edit.setStyleSheet(configure_measure_button_stylesheet())
        self._btn_edit.setFixedHeight(34)
        self._btn_edit.clicked.connect(self._on_edit_clicked)

        self._btn_delete_setup = QPushButton("🗑  Delete setup")
        self._btn_delete_setup.setStyleSheet(
            configure_measure_button_stylesheet()
        )
        self._btn_delete_setup.setFixedHeight(34)
        self._btn_delete_setup.clicked.connect(self._on_delete_setup_clicked)

        self._btn_sample = QPushButton("⚡  Insert sample execution")
        self._btn_sample.setStyleSheet(configure_measure_button_stylesheet())
        self._btn_sample.setFixedHeight(34)
        self._btn_sample.clicked.connect(self._on_sample_clicked)

        bar.addWidget(self._btn_create)
        bar.addWidget(self._btn_edit)
        bar.addWidget(self._btn_delete_setup)
        bar.addWidget(self._btn_sample)
        bar.addStretch()
        return bar

    def _build_setups_pane(self) -> QWidget:
        pane = QWidget()
        col = QVBoxLayout(pane)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        title = QLabel("Setups")
        title.setStyleSheet(runs_panel_title_stylesheet())
        col.addWidget(title)
        self._setups = QListWidget()
        self._setups.setStyleSheet(runs_list_stylesheet())
        self._setups.currentItemChanged.connect(self._on_setup_row_changed)
        col.addWidget(self._setups, stretch=1)
        return pane

    def _build_executions_pane(self) -> QWidget:
        pane = QWidget()
        col = QVBoxLayout(pane)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("Executions")
        title.setStyleSheet(runs_panel_title_stylesheet())
        title_row.addWidget(title)
        title_row.addStretch()
        self._btn_view = QPushButton("View data")
        self._btn_view.setStyleSheet(configure_measure_button_stylesheet())
        self._btn_view.setFixedHeight(28)
        self._btn_view.clicked.connect(self._on_view_clicked)
        self._btn_delete_exec = QPushButton("Delete")
        self._btn_delete_exec.setStyleSheet(
            configure_measure_button_stylesheet()
        )
        self._btn_delete_exec.setFixedHeight(28)
        self._btn_delete_exec.clicked.connect(self._on_delete_exec_clicked)
        title_row.addWidget(self._btn_view)
        title_row.addWidget(self._btn_delete_exec)
        col.addLayout(title_row)

        self._executions = QListWidget()
        self._executions.setStyleSheet(runs_list_stylesheet())
        self._executions.currentItemChanged.connect(
            self._on_execution_row_changed
        )
        col.addWidget(self._executions, stretch=1)
        return pane

    def _build_detail_pane(self) -> QWidget:
        pane = QWidget()
        col = QVBoxLayout(pane)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        title = QLabel("Setup detail")
        title.setStyleSheet(runs_panel_title_stylesheet())
        col.addWidget(title)
        self._summary = QLabel("")
        self._summary.setStyleSheet(meas_status_label_stylesheet())
        self._summary.setWordWrap(True)
        col.addWidget(self._summary)
        self._detail = QTreeWidget()
        self._detail.setStyleSheet(config_preview_tree_stylesheet())
        self._detail.setColumnCount(2)
        self._detail.setHeaderLabels(["Field", "Value"])
        self._detail.setAlternatingRowColors(True)
        col.addWidget(self._detail, stretch=1)
        return pane

    # ── Internal selection helpers ───────────────────────────────────────────

    def _current_setup_id(self) -> Optional[int]:
        item = self._setups.currentItem()
        return None if item is None else int(item.data(_ID_ROLE))

    def _current_execution_id(self) -> Optional[int]:
        item = self._executions.currentItem()
        return None if item is None else int(item.data(_ID_ROLE))

    def _update_button_state(self) -> None:
        has_setup = self._current_setup_id() is not None
        has_exec = self._current_execution_id() is not None
        self._btn_edit.setEnabled(has_setup)
        self._btn_delete_setup.setEnabled(has_setup)
        self._btn_sample.setEnabled(has_setup)
        self._btn_view.setEnabled(has_exec)
        self._btn_delete_exec.setEnabled(has_exec)

    # ── Qt slots → signals ───────────────────────────────────────────────────

    def _on_setup_row_changed(self) -> None:
        self._update_button_state()
        setup_id = self._current_setup_id()
        if setup_id is not None:
            self.setup_selected.emit(setup_id)

    def _on_execution_row_changed(self) -> None:
        self._update_button_state()
        exec_id = self._current_execution_id()
        if exec_id is not None:
            self.execution_selected.emit(exec_id)

    def _on_create_clicked(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Save setup", "Setup name:"
        )
        if not ok or not name.strip():
            return
        desc, _ = QInputDialog.getText(
            self, "Save setup", "Description (optional):"
        )
        self.create_setup_requested.emit(name.strip(), desc.strip())

    def _on_edit_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        current = self._setups.currentItem().text().split("\n", 1)[0]
        name, ok = QInputDialog.getText(
            self, "Edit setup", "Setup name:", text=current
        )
        if not ok or not name.strip():
            return
        desc, _ = QInputDialog.getText(
            self, "Edit setup", "Description (optional):"
        )
        self.edit_setup_metadata_requested.emit(
            setup_id, name.strip(), desc.strip()
        )

    def _on_delete_setup_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        if self._confirm(
            "Delete setup",
            "Delete this setup and all its executions? This cannot be undone.",
        ):
            self.delete_setup_requested.emit(setup_id)

    def _on_sample_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is not None:
            self.insert_sample_execution_requested.emit(setup_id)

    def _on_view_clicked(self) -> None:
        exec_id = self._current_execution_id()
        if exec_id is not None:
            self.view_execution_data_requested.emit(exec_id)

    def _on_delete_exec_clicked(self) -> None:
        exec_id = self._current_execution_id()
        if exec_id is None:
            return
        if self._confirm(
            "Delete execution", "Delete this execution and its data?"
        ):
            self.delete_execution_requested.emit(exec_id)

    # ── Small helpers ────────────────────────────────────────────────────────

    def _confirm(self, title: str, text: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _populate_tree(
        self, parent: Any, data: Any, key: Optional[str] = None
    ) -> None:
        """Recursively render a config dict/list/scalar into the tree."""
        if isinstance(data, dict):
            # Top-level dict (key is None) attaches its keys straight to the
            # tree instead of an empty wrapper row.
            container = parent if key is None else QTreeWidgetItem(
                parent, [key, ""]
            )
            for k, v in data.items():
                self._populate_tree(container, v, str(k))
        elif isinstance(data, (list, tuple)):
            node = QTreeWidgetItem(parent, [key or "", f"[{len(data)}]"])
            for i, v in enumerate(data):
                self._populate_tree(node, v, str(i))
        else:
            QTreeWidgetItem(parent, [key or "", str(data)])
