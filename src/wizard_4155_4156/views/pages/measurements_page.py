"""
views/pages/measurements_page.py
--------------------------------
Measurements & Run page — pure View layer.

Layout (two columns)
--------------------
┌─────────────────────────────────────────────────────────────────┐
│  Measurements & Run                                               │
│  [error bar — hidden unless an error occurs]                      │
│ ┌── left column ──────────────┐ ┌── right column ──────────────┐ │
│ │  ── Configuration Source ──  │ │  ── Active Configuration ──  │ │
│ │   Source: Live Sweep Config  │ │  ┌ Field        │ Value ───┐ │ │
│ │   [Load file…] [Use live]    │ │  │ Mode         │ SWEEP    │ │ │
│ │   ┌ summary box ───────────┐ │ │  │ Channels  ▸  │          │ │ │
│ │  ── Run Controls ──────────  │ │  │ Sweep …   ▸  │          │ │ │
│ │   [Setup][Run][Setup+Run]    │ │  └──────────────┴──────────┘ │ │
│ │   Status: …                  │ │   (friendly JSON preview)    │ │
│ └──────────────────────────────┘ └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

MVP rules
---------
- No model/presenter imports — the view only emits intent signals and
  receives primitives through ``display_*`` methods.
- The QFileDialog for picking a setup file is pure UI and lives here; the
  chosen path is forwarded to the presenter via ``load_setup_file_requested``.
- All QSS comes from stylesheets.py; no hex literals appear here.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.stylesheets import (
    config_preview_tree_stylesheet,
    configure_measure_button_stylesheet,
    error_bar_stylesheet,
    export_btn_stylesheet,
    meas_source_label_stylesheet,
    meas_status_label_stylesheet,
    meas_summary_box_stylesheet,
    measurements_page_stylesheet,
    section_title_stylesheet,
    subsection_title_stylesheet,
    sweep_section_card_stylesheet,
    table_empty_label_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage

_BUTTON_HEIGHT = 36
_LEFT_COLUMN_MAX_WIDTH = 480


def _make_card(title_text: str) -> tuple[QFrame, QVBoxLayout]:
    """Return a titled section card and its content layout."""
    card = QFrame()
    card.setObjectName("section_card")
    card.setStyleSheet(sweep_section_card_stylesheet())

    outer = QVBoxLayout(card)
    outer.setContentsMargins(16, 12, 16, 16)
    outer.setSpacing(10)

    title = QLabel(title_text)
    title.setStyleSheet(subsection_title_stylesheet())
    outer.addWidget(title)

    return card, outer


def _make_button(text: str, primary: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(_BUTTON_HEIGHT)
    btn.setStyleSheet(
        export_btn_stylesheet()
        if primary
        else configure_measure_button_stylesheet()
    )
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _pretty_key(key: Any) -> str:
    """Humanise a JSON key, keeping unit tokens (SMU1, VAR1) intact."""
    text = str(key)
    if text.replace("_", "").isupper():
        return text
    return text.replace("_", " ").title()


def _fmt_scalar(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _add_node(parent: QTreeWidgetItem, key: Any, value: Any) -> None:
    """Recursively attach a key/value pair to a tree item."""
    if isinstance(value, dict):
        item = QTreeWidgetItem([_pretty_key(key), ""])
        parent.addChild(item)
        for child_key, child_value in value.items():
            _add_node(item, child_key, child_value)
    elif isinstance(value, list):
        if value and all(isinstance(v, (dict, list)) for v in value):
            item = QTreeWidgetItem([_pretty_key(key), f"[{len(value)}]"])
            parent.addChild(item)
            for idx, child_value in enumerate(value):
                _add_node(item, f"[{idx}]", child_value)
        else:
            joined = ", ".join(_fmt_scalar(v) for v in value) or "—"
            parent.addChild(QTreeWidgetItem([_pretty_key(key), joined]))
    else:
        parent.addChild(
            QTreeWidgetItem([_pretty_key(key), _fmt_scalar(value)])
        )


class MeasurementsPageView(BasePage):
    """View for triggering measurements on the connected instrument."""

    # ── Lifecycle ──────────────────────────────────────────────────────────
    page_activated = Signal()

    # ── User intents ───────────────────────────────────────────────────────
    apply_setup_requested = Signal()
    run_fetch_requested = Signal()
    full_sequence_requested = Signal()
    load_setup_file_requested = Signal(str)  # chosen file path
    use_live_config_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(measurements_page_stylesheet())
        self._setup_ui()
        self._wire_signals()

    # ── Build ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel(tr_ui(CommandWizardText.MEAS_PAGE_TITLE))
        title.setStyleSheet(section_title_stylesheet())
        root.addWidget(title)

        # Error bar (hidden until an error is reported)
        self._error_bar = QLabel("")
        self._error_bar.setStyleSheet(error_bar_stylesheet())
        self._error_bar.setWordWrap(True)
        self._error_bar.hide()
        root.addWidget(self._error_bar)

        # Two-column body: controls (left) | active-config preview (right)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_left_column())
        columns.addWidget(self._build_preview_card(), stretch=1)
        root.addLayout(columns, stretch=1)

        # Disabled until a connection is established.
        self.set_controls_enabled(False)

    def _build_left_column(self) -> QWidget:
        container = QWidget()
        container.setMaximumWidth(_LEFT_COLUMN_MAX_WIDTH)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_source_card())
        layout.addWidget(self._build_run_card())
        layout.addStretch(1)
        return container

    def _build_source_card(self) -> QFrame:
        card, layout = _make_card(tr_ui(CommandWizardText.MEAS_CONFIG_SOURCE))

        self._source_label = QLabel(tr_ui(CommandWizardText.MEAS_SOURCE_LIVE))
        self._source_label.setStyleSheet(meas_source_label_stylesheet())
        layout.addWidget(self._source_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._load_btn = _make_button(
            tr_ui(CommandWizardText.MEAS_BTN_LOAD_FILE)
        )
        self._use_live_btn = _make_button(
            tr_ui(CommandWizardText.MEAS_BTN_USE_LIVE)
        )
        btn_row.addWidget(self._load_btn)
        btn_row.addWidget(self._use_live_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._summary_label = QLabel(
            tr_ui(CommandWizardText.MEAS_SUMMARY_EMPTY)
        )
        self._summary_label.setStyleSheet(meas_summary_box_stylesheet())
        self._summary_label.setWordWrap(True)
        self._summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._summary_label)
        return card

    def _build_run_card(self) -> QFrame:
        card, layout = _make_card(tr_ui(CommandWizardText.MEAS_RUN_CONTROLS))

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self._apply_setup_btn = _make_button(
            tr_ui(CommandWizardText.MEAS_BTN_APPLY_SETUP)
        )
        self._run_fetch_btn = _make_button(
            tr_ui(CommandWizardText.MEAS_BTN_RUN_FETCH)
        )
        self._full_btn = _make_button(
            tr_ui(CommandWizardText.MEAS_BTN_FULL_SEQUENCE), primary=True
        )
        btn_row.addWidget(self._apply_setup_btn)
        btn_row.addWidget(self._run_fetch_btn)
        btn_row.addWidget(self._full_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._status_label = QLabel(tr_ui(CommandWizardText.MEAS_STATUS_READY))
        self._status_label.setStyleSheet(meas_status_label_stylesheet())
        layout.addWidget(self._status_label)
        return card

    def _build_preview_card(self) -> QFrame:
        card, layout = _make_card(tr_ui(CommandWizardText.MEAS_PREVIEW_TITLE))

        self._preview_stack = QStackedWidget()

        self._preview_empty = QLabel(
            tr_ui(CommandWizardText.MEAS_PREVIEW_EMPTY)
        )
        self._preview_empty.setStyleSheet(table_empty_label_stylesheet())
        self._preview_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_stack.addWidget(self._preview_empty)

        self._preview_tree = QTreeWidget()
        self._preview_tree.setColumnCount(2)
        self._preview_tree.setHeaderLabels(
            [
                tr_ui(CommandWizardText.MEAS_PREVIEW_COL_FIELD),
                tr_ui(CommandWizardText.MEAS_PREVIEW_COL_VALUE),
            ]
        )
        self._preview_tree.setStyleSheet(config_preview_tree_stylesheet())
        self._preview_tree.setAlternatingRowColors(True)
        self._preview_tree.setRootIsDecorated(True)
        self._preview_tree.setUniformRowHeights(True)
        header = self._preview_tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._preview_stack.addWidget(self._preview_tree)

        self._preview_stack.setCurrentWidget(self._preview_empty)
        self._preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._preview_stack, stretch=1)
        return card

    def _wire_signals(self) -> None:
        self._load_btn.clicked.connect(self._on_load_clicked)
        self._use_live_btn.clicked.connect(self.use_live_config_requested)
        self._apply_setup_btn.clicked.connect(self.apply_setup_requested)
        self._run_fetch_btn.clicked.connect(self.run_fetch_requested)
        self._full_btn.clicked.connect(self.full_sequence_requested)

    # ── Lifecycle hook ─────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Internal slots ─────────────────────────────────────────────────────

    def _on_load_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr_ui(CommandWizardText.MEAS_FILE_DIALOG_TITLE),
            "",
            tr_ui(CommandWizardText.MEAS_FILE_DIALOG_FILTER),
        )
        if path:
            self.load_setup_file_requested.emit(path)

    # ── Display API (called by the presenter) ─────────────────────────────

    def display_source(self, label: str) -> None:
        self._source_label.setText(label)

    def display_config_summary(self, summary: str) -> None:
        self._summary_label.setText(summary)

    def display_config_preview(self, config: dict | None) -> None:
        """Render the active config as a friendly key/value tree."""
        self._preview_tree.clear()
        if not config:
            self._preview_stack.setCurrentWidget(self._preview_empty)
            return
        root = self._preview_tree.invisibleRootItem()
        for key, value in config.items():
            _add_node(root, key, value)
        self._preview_tree.expandAll()
        self._preview_stack.setCurrentWidget(self._preview_tree)

    def display_status(self, text: str) -> None:
        self._status_label.setText(text)

    def display_progress(self, current: int, total: int, status: str) -> None:
        self._status_label.setText(f"{status} ({current}/{total})")

    def display_error(self, text: str) -> None:
        if text:
            self._error_bar.setText(text)
            self._error_bar.show()
        else:
            self._error_bar.clear()
            self._error_bar.hide()

    def set_controls_enabled(self, enabled: bool) -> None:
        self._apply_setup_btn.setEnabled(enabled)
        self._run_fetch_btn.setEnabled(enabled)
        self._full_btn.setEnabled(enabled)
