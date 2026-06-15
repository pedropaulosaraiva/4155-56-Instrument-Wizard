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
    QFrame,
    QHBoxLayout,
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
from wizard_4155_4156.extra_widgets.setup_metadata_dialog import (
    SetupMetadataDialog,
)
from wizard_4155_4156.styles.stylesheets import (
    config_preview_tree_stylesheet,
    error_bar_stylesheet,
    meas_status_label_stylesheet,
    recent_panel_header_stylesheet,
    runs_empty_label_stylesheet,
    runs_list_stylesheet,
    runs_page_stylesheet,
    runs_panel_stylesheet,
    runs_panel_title_stylesheet,
    runs_primary_button_stylesheet,
    runs_secondary_button_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage

_ID_ROLE = Qt.ItemDataRole.UserRole


class RunsPageView(BasePage):
    """Three-pane browser: setups | executions | detail."""

    page_activated = Signal()
    setup_selected = Signal(int)
    execution_selected = Signal(int)
    create_setup_requested = Signal(str, str)             # name, description
    edit_setup_metadata_requested = Signal(int, str, str)  # id, name, desc
    delete_setup_requested = Signal(int)
    delete_execution_requested = Signal(int)
    insert_sample_execution_requested = Signal(int)       # setup id
    view_execution_data_requested = Signal(int)           # execution id
    apply_setup_requested = Signal(int)                   # setup id (hardware)
    apply_run_fetch_requested = Signal(int)               # setup id (hardware)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(runs_page_stylesheet())
        self._setup_rows: dict[int, SetupRow] = {}
        self._hardware_ready = False
        self._setup_ui()
        self._update_button_state()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API (called by presenter) ────────────────────────────────────

    def display_setups(self, rows: list[SetupRow]) -> None:
        self._setup_rows = {row.id: row for row in rows}
        self._setups.clear()
        self._setups_title.setText(f"Setups ({len(rows)})")
        if not rows:
            self._add_placeholder(
                self._setups,
                "No setups yet.\nSave the current configuration to create one.",
            )
        for row in rows:
            self._setups.addItem(self._make_setup_item(row))
        # Selection cleared by clear(); dependent panes reset.
        self.display_executions([])
        self.display_setup_detail(None, "")
        self._update_button_state()

    def select_setup(self, setup_id: int) -> None:
        """Programmatically select the setup row with the given id."""
        for i in range(self._setups.count()):
            item = self._setups.item(i)
            if item.data(_ID_ROLE) == setup_id:
                self._setups.setCurrentItem(item)
                return

    def display_executions(self, rows: list[ExecRow]) -> None:
        self._executions.clear()
        self._exec_title.setText(f"Executions ({len(rows)})")
        if not rows:
            self._add_placeholder(
                self._executions,
                "No executions.\nUse “Insert sample” to add one.",
            )
        for row in rows:
            self._executions.addItem(self._make_exec_item(row))
        self._update_button_state()

    def display_setup_detail(
        self, config: Optional[dict], summary: str
    ) -> None:
        self._detail.clear()
        self._summary.setText(summary)
        self._summary.setVisible(bool(summary))
        if config:
            self._populate_tree(self._detail, config)
            self._detail.expandToDepth(0)

    def set_hardware_ready(self, ready: bool) -> None:
        """Connected + idle ⇒ the run buttons may be used (with a selection)."""
        self._hardware_ready = ready
        self._update_button_state()

    def display_hardware_status(self, text: str) -> None:
        self._hw_status.setText(text)

    def display_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(bool(text))

    def display_status(self, text: str) -> None:
        self._status.setText(text)

    def display_empty(self, message: str) -> None:
        self._setup_rows = {}
        self._setups.clear()
        self._setups_title.setText("Setups (0)")
        self._add_placeholder(self._setups, message)
        self.display_executions([])
        self.display_setup_detail(None, "")
        self._status.setText(message)
        self._update_button_state()

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addLayout(self._build_hardware_bar())

        self._error = QLabel("")
        self._error.setStyleSheet(error_bar_stylesheet())
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        root.addWidget(self._error)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(14)
        splitter.addWidget(self._build_setups_pane())
        splitter.addWidget(self._build_executions_pane())
        splitter.addWidget(self._build_detail_pane())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 4)
        splitter.setSizes([320, 320, 460])
        root.addWidget(splitter, stretch=1)

        self._status = QLabel("No project open.")
        self._status.setStyleSheet(meas_status_label_stylesheet())
        root.addWidget(self._status)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        title = QLabel("🗄️  Measurement Runs")
        title.setStyleSheet(recent_panel_header_stylesheet())
        row.addWidget(title)
        row.addStretch()
        self._btn_create = QPushButton("➕  Save current config as setup")
        self._btn_create.setStyleSheet(runs_primary_button_stylesheet())
        self._btn_create.clicked.connect(self._on_create_clicked)
        row.addWidget(self._btn_create)
        return row

    def _build_hardware_bar(self) -> QHBoxLayout:
        """Run the *selected* setup on the connected instrument."""
        row = QHBoxLayout()
        row.setSpacing(8)
        caption = QLabel("Run selected setup on hardware:")
        caption.setStyleSheet(meas_status_label_stylesheet())
        row.addWidget(caption)

        self._btn_apply = QPushButton("🛠️  Apply setup")
        self._btn_apply.setStyleSheet(runs_secondary_button_stylesheet())
        self._btn_apply.clicked.connect(self._on_apply_clicked)
        self._btn_run = QPushButton("▶️  Apply setup, Run & Fetch")
        self._btn_run.setStyleSheet(runs_primary_button_stylesheet())
        self._btn_run.clicked.connect(self._on_run_clicked)
        row.addWidget(self._btn_apply)
        row.addWidget(self._btn_run)
        row.addStretch()

        self._hw_status = QLabel("Disconnected")
        self._hw_status.setStyleSheet(meas_status_label_stylesheet())
        row.addWidget(self._hw_status)
        return row

    def _build_setups_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("runs_panel")
        pane.setStyleSheet(runs_panel_stylesheet())
        col = QVBoxLayout(pane)
        col.setContentsMargins(14, 12, 14, 14)
        col.setSpacing(8)

        head = QHBoxLayout()
        self._setups_title = QLabel("Setups (0)")
        self._setups_title.setStyleSheet(runs_panel_title_stylesheet())
        head.addWidget(self._setups_title)
        head.addStretch()
        self._btn_edit = self._mini_button("✏️ Edit", self._on_edit_clicked)
        self._btn_delete_setup = self._mini_button(
            "🗑️ Delete", self._on_delete_setup_clicked
        )
        head.addWidget(self._btn_edit)
        head.addWidget(self._btn_delete_setup)
        col.addLayout(head)

        self._setups = QListWidget()
        self._setups.setStyleSheet(runs_list_stylesheet())
        self._setups.setWordWrap(True)
        self._setups.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._setups.currentItemChanged.connect(self._on_setup_row_changed)
        col.addWidget(self._setups, stretch=1)
        return pane

    def _build_executions_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("runs_panel")
        pane.setStyleSheet(runs_panel_stylesheet())
        col = QVBoxLayout(pane)
        col.setContentsMargins(14, 12, 14, 14)
        col.setSpacing(8)

        head = QHBoxLayout()
        self._exec_title = QLabel("Executions (0)")
        self._exec_title.setStyleSheet(runs_panel_title_stylesheet())
        head.addWidget(self._exec_title)
        head.addStretch()
        self._btn_sample = self._mini_button(
            "⚡ Insert sample", self._on_sample_clicked
        )
        self._btn_view = self._mini_button(
            "📈 View data", self._on_view_clicked
        )
        self._btn_delete_exec = self._mini_button(
            "🗑️ Delete", self._on_delete_exec_clicked
        )
        head.addWidget(self._btn_sample)
        head.addWidget(self._btn_view)
        head.addWidget(self._btn_delete_exec)
        col.addLayout(head)

        self._executions = QListWidget()
        self._executions.setStyleSheet(runs_list_stylesheet())
        self._executions.setWordWrap(True)
        self._executions.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._executions.currentItemChanged.connect(
            self._on_execution_row_changed
        )
        col.addWidget(self._executions, stretch=1)
        return pane

    def _build_detail_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("runs_panel")
        pane.setStyleSheet(runs_panel_stylesheet())
        col = QVBoxLayout(pane)
        col.setContentsMargins(14, 12, 14, 14)
        col.setSpacing(8)

        title = QLabel("Setup detail")
        title.setStyleSheet(runs_panel_title_stylesheet())
        col.addWidget(title)
        self._summary = QLabel("")
        self._summary.setStyleSheet(meas_status_label_stylesheet())
        self._summary.setWordWrap(True)
        self._summary.setVisible(False)
        col.addWidget(self._summary)
        self._detail = QTreeWidget()
        self._detail.setStyleSheet(config_preview_tree_stylesheet())
        self._detail.setColumnCount(2)
        self._detail.setHeaderLabels(["Field", "Value"])
        self._detail.setAlternatingRowColors(True)
        self._detail.setRootIsDecorated(True)
        col.addWidget(self._detail, stretch=1)
        return pane

    # ── Item factories ───────────────────────────────────────────────────────

    @staticmethod
    def _make_setup_item(row: SetupRow) -> QListWidgetItem:
        created = row.creation_date.strftime("%d/%m/%Y")
        label = (
            f"{row.name}\n"
            f"   {row.type_label} · {row.instrument_model} · "
            f"{row.execution_count} run(s) · created {created}"
        )
        item = QListWidgetItem(label)
        item.setData(_ID_ROLE, row.id)
        return item

    @staticmethod
    def _make_exec_item(row: ExecRow) -> QListWidgetItem:
        tag = "  ⚡sample" if row.is_synthetic else ""
        stamp = row.execution_date.strftime("%d/%m/%Y %H:%M")
        label = (
            f"{row.name}{tag}\n"
            f"   {stamp} · {row.instrument_model} · "
            f"{row.variable_count} var(s)"
        )
        item = QListWidgetItem(label)
        item.setData(_ID_ROLE, row.id)
        return item

    @staticmethod
    def _add_placeholder(listw: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(Qt.GlobalColor.gray)
        listw.addItem(item)

    def _mini_button(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(runs_secondary_button_stylesheet())
        btn.clicked.connect(slot)
        return btn

    # ── Internal selection helpers ───────────────────────────────────────────

    def _current_setup_id(self) -> Optional[int]:
        item = self._setups.currentItem()
        if item is None:
            return None
        data = item.data(_ID_ROLE)
        return None if data is None else int(data)

    def _current_execution_id(self) -> Optional[int]:
        item = self._executions.currentItem()
        if item is None:
            return None
        data = item.data(_ID_ROLE)
        return None if data is None else int(data)

    def _update_button_state(self) -> None:
        has_setup = self._current_setup_id() is not None
        has_exec = self._current_execution_id() is not None
        self._btn_edit.setEnabled(has_setup)
        self._btn_delete_setup.setEnabled(has_setup)
        self._btn_sample.setEnabled(has_setup)
        self._btn_view.setEnabled(has_exec)
        self._btn_delete_exec.setEnabled(has_exec)
        can_run = has_setup and self._hardware_ready
        self._btn_apply.setEnabled(can_run)
        self._btn_run.setEnabled(can_run)

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
        dlg = SetupMetadataDialog(title="Save setup", parent=self)
        if dlg.exec():
            self.create_setup_requested.emit(
                dlg.get_name(), dlg.get_description()
            )

    def _on_edit_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        row = self._setup_rows.get(setup_id)
        dlg = SetupMetadataDialog(
            title="Edit setup",
            name=row.name if row else "",
            description=row.description if row else "",
            parent=self,
        )
        if dlg.exec():
            self.edit_setup_metadata_requested.emit(
                setup_id, dlg.get_name(), dlg.get_description()
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

    def _on_apply_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is not None:
            self.apply_setup_requested.emit(setup_id)

    def _on_run_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is not None:
            self.apply_run_fetch_requested.emit(setup_id)

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
