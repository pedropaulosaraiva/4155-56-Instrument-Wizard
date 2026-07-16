"""
views/pages/runs_page.py
------------------------
Measurement Runs page — a CRUD browser over the project database.

This is the home for measurement *setups* and their *executions*.  Pure
View layer: it emits ``*_requested`` signals and renders state pushed in via
``display_*`` methods.  It imports only the Qt-free row DTOs
(``SetupRow``/``ExecRow``) — never the ORM — mirroring how the home page
imports ``ProjectData``.

Layout: a top toolbar (Save current config as setup · Apply Setup · Apply
Setup and Run) over a three-pane splitter (setups | runs | setup detail).
Per-element actions live in a three-dot (⋮) ellipsis menu in each panel header.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.db.repository import ExecRow, SetupRow
from wizard_4155_4156.extra_widgets.description_dialog import DescriptionDialog
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.icons import (
    AppIcon24,
    accent_button_icon,
    app_icon,
)
from wizard_4155_4156.styles.stylesheets import (
    error_bar_stylesheet,
    runs_list_stylesheet,
    runs_menu_button_stylesheet,
    runs_page_stylesheet,
    runs_panel_stylesheet,
    runs_panel_title_stylesheet,
    runs_primary_button_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.action_menu import ActionMenu
from wizard_4155_4156.views.widgets.setup_detail_panel import SetupDetailPanel

_ID_ROLE = Qt.ItemDataRole.UserRole
_T = CommandWizardText


class RunsPageView(BasePage):
    """Three-pane browser: setups | runs | detail."""

    page_activated = Signal()
    setup_selected = Signal(int)
    execution_selected = Signal(int)
    create_setup_requested = Signal()  # presenter prompts
    edit_setup_metadata_requested = Signal(int)  # setup id
    delete_setup_requested = Signal(int)
    delete_execution_requested = Signal(int)
    insert_sample_execution_requested = Signal(int)  # setup id
    view_execution_data_requested = Signal(int)  # execution id
    apply_setup_requested = Signal(int)  # setup id (hardware)
    apply_run_fetch_requested = Signal(int)  # setup id (hardware)
    copy_to_config_requested = Signal(int)  # setup id (copy)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(runs_page_stylesheet())
        self._setup_rows: dict[int, SetupRow] = {}
        self._exec_rows: dict[int, ExecRow] = {}
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
        self._setups_title.setText(
            tr_ui(_T.RUNS_SETUPS_TITLE).format(count=len(rows))
        )
        if not rows:
            self._add_placeholder(self._setups, tr_ui(_T.RUNS_SETUPS_EMPTY))
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
        self._exec_rows = {row.id: row for row in rows}
        self._executions.clear()
        self._exec_title.setText(
            tr_ui(_T.RUNS_RUNS_TITLE).format(count=len(rows))
        )
        if not rows:
            self._add_placeholder(self._executions, tr_ui(_T.RUNS_RUNS_EMPTY))
        for row in rows:
            self._executions.addItem(self._make_exec_item(row))
        self._update_button_state()

    def display_setup_detail(
        self, config: Optional[dict], summary: str
    ) -> None:
        self._detail.display(config, summary)

    def set_hardware_ready(self, ready: bool) -> None:
        """Connected + idle: run buttons may be used.

        Only meaningful when a setup is also selected.
        """
        self._hardware_ready = ready
        self._update_button_state()

    def display_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.setVisible(bool(text))

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(14)

        root.addLayout(self._build_toolbar())

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

    def _build_toolbar(self) -> QHBoxLayout:
        """Save-as-setup (left) · Apply Setup / Apply Setup and Run (right)."""
        row = QHBoxLayout()
        row.setSpacing(8)

        self._btn_create = QPushButton(tr_ui(_T.RUNS_BTN_CREATE))
        self._btn_create.setIcon(accent_button_icon(AppIcon24.PLUS))
        self._btn_create.setIconSize(QSize(16, 16))
        self._btn_create.setStyleSheet(runs_primary_button_stylesheet())
        self._btn_create.clicked.connect(self._on_create_clicked)
        row.addWidget(self._btn_create)
        row.addStretch()

        self._btn_apply = QPushButton(tr_ui(_T.MEAS_BTN_APPLY_SETUP))
        self._btn_apply.setIcon(accent_button_icon(AppIcon24.TOOL))
        self._btn_apply.setIconSize(QSize(16, 16))
        self._btn_apply.setStyleSheet(runs_primary_button_stylesheet())
        self._btn_apply.clicked.connect(self._on_apply_clicked)
        self._btn_run = QPushButton(tr_ui(_T.RUNS_BTN_APPLY_RUN))
        self._btn_run.setIcon(accent_button_icon(AppIcon24.PLAY))
        self._btn_run.setIconSize(QSize(16, 16))
        self._btn_run.setStyleSheet(runs_primary_button_stylesheet())
        self._btn_run.clicked.connect(self._on_run_clicked)
        row.addWidget(self._btn_apply)
        row.addWidget(self._btn_run)
        return row

    def _build_setups_pane(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("runs_panel")
        pane.setStyleSheet(runs_panel_stylesheet())
        col = QVBoxLayout(pane)
        col.setContentsMargins(14, 12, 14, 14)
        col.setSpacing(8)

        head = QHBoxLayout()
        self._setups_title = QLabel(
            tr_ui(_T.RUNS_SETUPS_TITLE).format(count=0)
        )
        self._setups_title.setStyleSheet(runs_panel_title_stylesheet())
        head.addWidget(self._setups_title)
        head.addStretch()
        self._setups_menu_btn = self._make_menu_button(self._show_setups_menu)
        head.addWidget(self._setups_menu_btn)
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
        self._exec_title = QLabel(tr_ui(_T.RUNS_RUNS_TITLE).format(count=0))
        self._exec_title.setStyleSheet(runs_panel_title_stylesheet())
        head.addWidget(self._exec_title)
        head.addStretch()
        self._runs_menu_btn = self._make_menu_button(self._show_runs_menu)
        head.addWidget(self._runs_menu_btn)
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
        self._detail = SetupDetailPanel()
        col.addWidget(self._detail, stretch=1)
        return pane

    # ── Ellipsis (⋮) menus ───────────────────────────────────────────────────

    def _make_menu_button(self, slot) -> QToolButton:
        btn = QToolButton()
        btn.setText("⋮")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setStyleSheet(runs_menu_button_stylesheet())
        btn.clicked.connect(slot)
        return btn

    def _show_setups_menu(self) -> None:
        """Built fresh on each open so availability reflects the selection."""
        has_setup = self._current_setup_id() is not None
        reason = "" if has_setup else tr_ui(_T.RUNS_NEED_SETUP)
        menu = ActionMenu(self)
        menu.add_item(
            tr_ui(_T.RUNS_MENU_EDIT_META),
            icon=app_icon(AppIcon24.EDIT_PENCIL),
            callback=self._on_edit_clicked,
            available=has_setup,
            unavailable_reason=reason,
        )
        menu.add_item(
            tr_ui(_T.RUNS_MENU_EDIT_AS_NEW),
            icon=app_icon(AppIcon24.EDIT),
            callback=self._on_copy_clicked,
            available=has_setup,
            unavailable_reason=reason,
        )
        menu.add_item(
            tr_ui(_T.RUNS_MENU_SEE_DESC),
            icon=app_icon(AppIcon24.INFO),
            callback=self._on_see_setup_description,
            available=has_setup,
            unavailable_reason=reason,
        )
        menu.add_separator()
        menu.add_item(
            tr_ui(_T.RUNS_MENU_DELETE_SETUP),
            icon=app_icon(AppIcon24.TRASH),
            callback=self._on_delete_setup_clicked,
            available=has_setup,
            unavailable_reason=reason,
        )
        menu.popup_under(self._setups_menu_btn)

    def _show_runs_menu(self) -> None:
        has_setup = self._current_setup_id() is not None
        has_exec = self._current_execution_id() is not None
        need_setup = tr_ui(_T.RUNS_NEED_SETUP)
        need_run = tr_ui(_T.RUNS_NEED_RUN)
        menu = ActionMenu(self)
        menu.add_item(
            tr_ui(_T.RUNS_MENU_VIEW_TABLE),
            icon=app_icon(AppIcon24.TABLE),
            callback=self._on_view_clicked,
            available=has_exec,
            unavailable_reason=need_run,
        )
        menu.add_item(
            tr_ui(_T.RUNS_MENU_VIEW_GRAPH),
            icon=app_icon(AppIcon24.BAR_CHART),
            available=False,  # Graph page not built yet.
            unavailable_reason=tr_ui(_T.RUNS_GRAPH_SOON_TOOLTIP),
        )
        menu.add_item(
            tr_ui(_T.RUNS_MENU_INSERT_MOCK),
            icon=app_icon(AppIcon24.BOOKMARK),
            callback=self._on_sample_clicked,
            available=has_setup,
            unavailable_reason=need_setup,
        )
        menu.add_item(
            tr_ui(_T.RUNS_MENU_SEE_DESC),
            icon=app_icon(AppIcon24.INFO),
            callback=self._on_see_run_description,
            available=has_exec,
            unavailable_reason=need_run,
        )
        menu.add_separator()
        menu.add_item(
            tr_ui(_T.RUNS_MENU_DELETE_RUN),
            icon=app_icon(AppIcon24.TRASH),
            callback=self._on_delete_exec_clicked,
            available=has_exec,
            unavailable_reason=need_run,
        )
        menu.popup_under(self._runs_menu_btn)

    # ── Item factories ───────────────────────────────────────────────────────

    @staticmethod
    def _make_setup_item(row: SetupRow) -> QListWidgetItem:
        created = row.creation_date.strftime("%d/%m/%Y")
        label = (
            f"{row.name}    {row.runtime_label}\n"
            f"   {row.type_label} · {row.instrument_model} · "
            f"{row.execution_count} run(s) · created {created}"
        )
        item = QListWidgetItem(label)
        item.setData(_ID_ROLE, row.id)
        return item

    @staticmethod
    def _make_exec_item(row: ExecRow) -> QListWidgetItem:
        tag = "  · mock sample" if row.is_synthetic else ""
        stamp = row.execution_date.strftime("%d/%m/%Y %H:%M")
        label = (
            f"{row.name}{tag}\n"
            f"   {stamp} · {row.instrument_model} · "
            f"{row.variable_count} var(s)"
        )
        item = QListWidgetItem(label)
        if row.is_synthetic:
            item.setIcon(app_icon(AppIcon24.BOOKMARK))
        item.setData(_ID_ROLE, row.id)
        return item

    @staticmethod
    def _add_placeholder(listw: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(Qt.GlobalColor.gray)
        listw.addItem(item)

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
        # The ⋮ menus stay clickable at all times — per-entry availability (and
        # the "why disabled" tooltips) is resolved when each menu is opened.
        can_run = self._current_setup_id() is not None and self._hardware_ready
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
        # The presenter owns the dialog so a duplicate-name error can be shown
        # in the still-open modal (never the error bar).
        self.create_setup_requested.emit()

    def _on_edit_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        self.edit_setup_metadata_requested.emit(setup_id)

    def _on_delete_setup_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        if self._confirm(
            tr_ui(_T.RUNS_DELETE_SETUP_TITLE),
            tr_ui(_T.RUNS_DELETE_SETUP_MSG),
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

    def _on_copy_clicked(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is not None:
            self.copy_to_config_requested.emit(setup_id)

    def _on_delete_exec_clicked(self) -> None:
        exec_id = self._current_execution_id()
        if exec_id is None:
            return
        if self._confirm(
            tr_ui(_T.RUNS_DELETE_RUN_TITLE), tr_ui(_T.RUNS_DELETE_RUN_MSG)
        ):
            self.delete_execution_requested.emit(exec_id)

    def _on_see_setup_description(self) -> None:
        setup_id = self._current_setup_id()
        if setup_id is None:
            return
        row = self._setup_rows.get(setup_id)
        if row is not None:
            self._show_description(row.name, row.description)

    def _on_see_run_description(self) -> None:
        exec_id = self._current_execution_id()
        if exec_id is None:
            return
        row = self._exec_rows.get(exec_id)
        if row is not None:
            self._show_description(row.name, row.description)

    # ── Small helpers ────────────────────────────────────────────────────────

    def _show_description(self, name: str, description: str) -> None:
        DescriptionDialog(name, description, parent=self).exec()

    def _confirm(self, title: str, text: str) -> bool:
        reply = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def confirm_instrument_mismatch(
        self, setup_model: str, connected_model: str
    ) -> tuple[bool, bool]:
        """Warn that the setup targets a different instrument than connected.

        Returns ``(proceed, dont_ask_again)``; the presenter owns the
        session-scoped suppression decision.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Instrument mismatch")
        box.setText(
            f"This setup was created for {setup_model}, but "
            f"{connected_model} is currently connected.\n\n"
            "Execute this setup anyway?"
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        dont_ask = QCheckBox("Don't ask again for this session")
        box.setCheckBox(dont_ask)
        proceed = box.exec() == QMessageBox.StandardButton.Yes
        return proceed, dont_ask.isChecked()
