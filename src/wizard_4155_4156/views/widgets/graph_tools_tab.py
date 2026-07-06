"""
views/widgets/graph_tools_tab.py
--------------------------------
"Tools" sidebar tab — interaction tools for the ACTIVE plot, grouped by
workflow: view control (reset, mouse mode), cursors (mode, source trace,
readout), the ROI toggle, and export.

Passive view: emits ``*_requested``/``*_changed`` signals with trace ids
(stable strings) as payloads; state arrives through ``display_*``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    global_option_checkbox_stylesheet,
    graph_cursor_readout_stylesheet,
    runs_secondary_button_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.config_sections import (
    SectionFrame,
    SegmentedGroup,
    combo,
    form_row,
)

_LABEL_WIDTH = 90

_MOUSE_LABELS = {  # SegmentedGroup label ↔ logical id
    "pan": TXT.GRAPH_MOUSE_PAN,
    "zoom": TXT.GRAPH_MOUSE_ZOOM,
}
_CURSOR_LABELS = {
    "off": TXT.GRAPH_CURSOR_OFF,
    "single": TXT.GRAPH_CURSOR_SINGLE,
    "dual": TXT.GRAPH_CURSOR_DUAL,
}


class GraphToolsTab(QWidget):
    """View / cursors / ROI / export tools for the active plot."""

    reset_view_requested = Signal()
    mouse_mode_changed = Signal(str)  # "pan" | "zoom"
    cursor_mode_changed = Signal(str)  # "off" | "single" | "dual"
    cursor_source_changed = Signal(str)  # trace id
    roi_enabled_changed = Signal(bool)
    export_requested = Signal(str)  # "png" | "csv"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        root.addWidget(self._build_view_section())
        root.addWidget(self._build_cursors_section())
        root.addWidget(self._build_roi_section())
        root.addWidget(self._build_export_section())
        root.addStretch(1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_view_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_VIEW), flat=True, accent=P.GRAPH_TAB_TOOLS
        )
        body = section.body()

        self._reset_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_RESET_VIEW))
        self._reset_btn.setStyleSheet(runs_secondary_button_stylesheet())
        self._reset_btn.clicked.connect(self.reset_view_requested)
        body.addWidget(self._reset_btn)

        self._mouse_group = SegmentedGroup(
            [tr_ui(t) for t in _MOUSE_LABELS.values()], compact=True
        )
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_MOUSE), self._mouse_group, _LABEL_WIDTH
            )
        )
        self._mouse_group.selection_changed.connect(
            lambda label: self.mouse_mode_changed.emit(
                self._label_to_id(_MOUSE_LABELS, label)
            )
        )
        return section

    def _build_cursors_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_CURSORS), flat=True, accent=P.GRAPH_TAB_TOOLS
        )
        body = section.body()

        self._cursor_group = SegmentedGroup(
            [tr_ui(t) for t in _CURSOR_LABELS.values()], compact=True
        )
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_CURSORS),
                self._cursor_group,
                _LABEL_WIDTH,
            )
        )
        self._cursor_group.selection_changed.connect(
            lambda label: self.cursor_mode_changed.emit(
                self._label_to_id(_CURSOR_LABELS, label)
            )
        )

        self._cursor_source = combo([])
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_CURSOR_SOURCE),
                self._cursor_source,
                _LABEL_WIDTH,
            )
        )
        self._cursor_source.currentIndexChanged.connect(
            self._on_cursor_source_changed
        )

        self._readout = QLabel("")
        self._readout.setStyleSheet(graph_cursor_readout_stylesheet())
        self._readout.setWordWrap(True)
        self._readout.setVisible(False)  # shown only with cursor text
        body.addWidget(self._readout)
        return section

    def _build_roi_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_ROI), flat=True, accent=P.GRAPH_TAB_TOOLS
        )
        self._roi_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_ROI))
        self._roi_chk.setStyleSheet(global_option_checkbox_stylesheet())
        self._roi_chk.toggled.connect(self.roi_enabled_changed)
        section.body().addWidget(self._roi_chk)
        return section

    def _build_export_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_EXPORT), flat=True, accent=P.GRAPH_TAB_TOOLS
        )
        export_row = QWidget()
        h = QHBoxLayout(export_row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        for kind, text in (
            ("png", TXT.GRAPH_BTN_EXPORT_PNG),
            ("csv", TXT.GRAPH_BTN_EXPORT_CSV),
        ):
            btn = QPushButton(tr_ui(text))
            btn.setStyleSheet(runs_secondary_button_stylesheet())
            btn.clicked.connect(
                lambda _c=False, k=kind: self.export_requested.emit(k)
            )
            h.addWidget(btn)
        section.body().addWidget(export_row)
        return section

    # ── Public display API ──────────────────────────────────────────────────

    def display_tools(
        self,
        mouse_mode: str,
        cursor_mode: str,
        cursor_source_id: str | None,
        roi_enabled: bool,
    ) -> None:
        self._mouse_group.set_value(
            tr_ui(_MOUSE_LABELS.get(mouse_mode, TXT.GRAPH_MOUSE_PAN))
        )
        self._cursor_group.set_value(
            tr_ui(_CURSOR_LABELS.get(cursor_mode, TXT.GRAPH_CURSOR_OFF))
        )
        self._roi_chk.blockSignals(True)
        self._roi_chk.setChecked(roi_enabled)
        self._roi_chk.blockSignals(False)
        if cursor_source_id is not None:
            self._cursor_source.blockSignals(True)
            idx = self._cursor_source.findData(cursor_source_id)
            self._cursor_source.setCurrentIndex(idx)
            self._cursor_source.blockSignals(False)

    def display_trace_options(
        self, options: list[tuple[str, str]], current: str | None
    ) -> None:
        """Cursor-source combo entries: (trace id, display name)."""
        self._cursor_source.blockSignals(True)
        self._cursor_source.clear()
        for trace_id, name in options:
            self._cursor_source.addItem(name, trace_id)
            self._cursor_source.setItemData(
                self._cursor_source.count() - 1,
                name,
                Qt.ItemDataRole.ToolTipRole,
            )
        if current is not None:
            idx = self._cursor_source.findData(current)
            self._cursor_source.setCurrentIndex(idx)
        self._cursor_source.blockSignals(False)

    def display_cursor_readout(self, text: str) -> None:
        self._readout.setText(text)
        self._readout.setVisible(bool(text))

    # ── Internals ───────────────────────────────────────────────────────────

    @staticmethod
    def _label_to_id(mapping: dict, label: str) -> str:
        for logical_id, text in mapping.items():
            if tr_ui(text) == label:
                return logical_id
        return next(iter(mapping))

    def _on_cursor_source_changed(self, index: int) -> None:
        trace_id = self._cursor_source.itemData(index)
        if trace_id is not None:
            self.cursor_source_changed.emit(trace_id)
