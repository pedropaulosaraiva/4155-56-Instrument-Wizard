"""
views/widgets/graph_view_tab.py
-------------------------------
"View" sidebar tab — visualization of the ACTIVE plot: tools (reset
view, mouse mode, cursors, ROI, export) and per-trace styling rows
(visibility, color, name, line style, marker), plus title/axis labels.

Passive view: emits ``*_requested``/``*_changed`` signals with trace ids
(stable strings) as payloads; state arrives through ``display_*``.
Trace rows are rebuilt from a spec list so future style columns (width,
opacity…) can be appended without restructuring.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    graph_color_swatch_stylesheet,
    graph_cursor_readout_stylesheet,
    graph_trace_row_stylesheet,
    runs_secondary_button_stylesheet,
    table_empty_label_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
)
from wizard_4155_4156.views.widgets.config_sections import (
    SectionFrame,
    SegmentedGroup,
    combo,
    form_row,
)

_LABEL_WIDTH = 90

#: (logical id, UI label) — logical ids match models/graph/trace.py.
_LINE_STYLE_OPTIONS: list[tuple[str, TXT]] = [
    ("solid", TXT.GRAPH_LINE_SOLID),
    ("dash", TXT.GRAPH_LINE_DASH),
    ("dot", TXT.GRAPH_LINE_DOT),
    ("none", TXT.GRAPH_LINE_NONE),
]
_MARKER_OPTIONS: list[tuple[str, TXT]] = [
    ("none", TXT.GRAPH_MARKER_NONE),
    ("circle", TXT.GRAPH_MARKER_CIRCLE),
    ("square", TXT.GRAPH_MARKER_SQUARE),
    ("triangle", TXT.GRAPH_MARKER_TRIANGLE),
    ("cross", TXT.GRAPH_MARKER_CROSS),
]

_MOUSE_LABELS = {  # SegmentedGroup label ↔ logical id
    "pan": TXT.GRAPH_MOUSE_PAN,
    "zoom": TXT.GRAPH_MOUSE_ZOOM,
}
_CURSOR_LABELS = {
    "off": TXT.GRAPH_CURSOR_OFF,
    "single": TXT.GRAPH_CURSOR_SINGLE,
    "dual": TXT.GRAPH_CURSOR_DUAL,
}


def _id_combo(options: list[tuple[str, TXT]]) -> QComboBox:
    box = QComboBox()
    box.setStyleSheet(unit_card_combo_stylesheet())
    for logical_id, text in options:
        box.addItem(tr_ui(text), logical_id)
    return box


class _TraceRow(QFrame):
    """One styling row: [visible] [color] [name] [line] [marker]."""

    def __init__(self, owner: "GraphViewTab", spec: dict) -> None:
        super().__init__()
        self.setObjectName("trace_row")
        self.setStyleSheet(graph_trace_row_stylesheet())
        trace_id = spec["id"]

        h = QHBoxLayout(self)
        h.setContentsMargins(6, 4, 6, 4)
        h.setSpacing(6)

        visible = QCheckBox()
        visible.setStyleSheet(global_option_checkbox_stylesheet())
        visible.setChecked(bool(spec["visible"]))
        visible.toggled.connect(
            lambda on: owner.trace_visibility_changed.emit(trace_id, on)
        )
        h.addWidget(visible)

        swatch = QPushButton()
        swatch.setFixedSize(20, 20)
        swatch.setStyleSheet(graph_color_swatch_stylesheet(spec["color"]))
        swatch.clicked.connect(
            lambda: owner._pick_color(trace_id, spec["color"])
        )
        h.addWidget(swatch)

        name = QLineEdit(spec["name"])
        name.setStyleSheet(unit_card_line_edit_stylesheet())
        name.editingFinished.connect(
            lambda: owner.trace_renamed.emit(trace_id, name.text())
        )
        h.addWidget(name, stretch=1)

        line = _id_combo(_LINE_STYLE_OPTIONS)
        line.setCurrentIndex(max(0, line.findData(spec["line_style"])))
        line.currentIndexChanged.connect(
            lambda _i: owner.trace_line_style_changed.emit(
                trace_id, line.currentData()
            )
        )
        h.addWidget(line)

        marker = _id_combo(_MARKER_OPTIONS)
        marker.setCurrentIndex(max(0, marker.findData(spec["marker"])))
        marker.currentIndexChanged.connect(
            lambda _i: owner.trace_marker_changed.emit(
                trace_id, marker.currentData()
            )
        )
        h.addWidget(marker)


class GraphViewTab(QWidget):
    """Tools / labels / per-trace styling of the active plot."""

    reset_view_requested = Signal()
    mouse_mode_changed = Signal(str)  # "pan" | "zoom"
    cursor_mode_changed = Signal(str)  # "off" | "single" | "dual"
    cursor_source_changed = Signal(str)  # trace id
    roi_enabled_changed = Signal(bool)
    export_requested = Signal(str)  # "png" | "csv"
    plot_title_committed = Signal(str)
    axis_label_committed = Signal(str, str)  # (axis, text)
    trace_visibility_changed = Signal(str, bool)
    trace_color_changed = Signal(str, str)  # (trace id, hex color)
    trace_renamed = Signal(str, str)
    trace_line_style_changed = Signal(str, str)
    trace_marker_changed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        root.addWidget(self._build_tools_section())
        root.addWidget(self._build_labels_section())
        root.addWidget(self._build_traces_section())
        root.addStretch(1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_tools_section(self) -> SectionFrame:
        section = SectionFrame(tr_ui(TXT.GRAPH_SEC_TOOLS))
        body = section.body()

        self._reset_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_RESET_VIEW))
        self._reset_btn.setStyleSheet(runs_secondary_button_stylesheet())
        self._reset_btn.clicked.connect(self.reset_view_requested)
        body.addWidget(self._reset_btn)

        self._mouse_group = SegmentedGroup(
            [tr_ui(t) for t in _MOUSE_LABELS.values()]
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

        self._cursor_group = SegmentedGroup(
            [tr_ui(t) for t in _CURSOR_LABELS.values()]
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
        body.addWidget(self._readout)

        self._roi_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_ROI))
        self._roi_chk.setStyleSheet(global_option_checkbox_stylesheet())
        self._roi_chk.toggled.connect(self.roi_enabled_changed)
        body.addWidget(self._roi_chk)

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
        body.addWidget(export_row)
        return section

    def _build_labels_section(self) -> SectionFrame:
        section = SectionFrame(tr_ui(TXT.GRAPH_SEC_LABELS))
        body = section.body()

        self._title_edit = QLineEdit()
        self._title_edit.setStyleSheet(unit_card_line_edit_stylesheet())
        self._title_edit.editingFinished.connect(
            lambda: self.plot_title_committed.emit(self._title_edit.text())
        )
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_PLOT_TITLE),
                self._title_edit,
                _LABEL_WIDTH,
            )
        )

        self._x_label_edit = QLineEdit()
        self._y_label_edit = QLineEdit()
        for axis, edit, text in (
            ("x", self._x_label_edit, TXT.GRAPH_LBL_X_LABEL),
            ("y", self._y_label_edit, TXT.GRAPH_LBL_Y_LABEL),
        ):
            edit.setStyleSheet(unit_card_line_edit_stylesheet())
            edit.editingFinished.connect(
                lambda a=axis, e=edit: self.axis_label_committed.emit(
                    a, e.text()
                )
            )
            body.addWidget(form_row(tr_ui(text), edit, _LABEL_WIDTH))
        return section

    def _build_traces_section(self) -> SectionFrame:
        section = SectionFrame(tr_ui(TXT.GRAPH_SEC_TRACES))
        self._traces_box = QVBoxLayout()
        self._traces_box.setSpacing(6)
        section.body().addLayout(self._traces_box)

        self._traces_empty = QLabel(tr_ui(TXT.GRAPH_NO_TRACES))
        self._traces_empty.setStyleSheet(table_empty_label_stylesheet())
        section.body().addWidget(self._traces_empty)
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

    def display_labels(self, title: str, x_label: str, y_label: str) -> None:
        for edit, text in (
            (self._title_edit, title),
            (self._x_label_edit, x_label),
            (self._y_label_edit, y_label),
        ):
            edit.blockSignals(True)
            edit.setText(text)
            edit.blockSignals(False)

    def display_trace_options(
        self, options: list[tuple[str, str]], current: str | None
    ) -> None:
        """Cursor-source combo entries: (trace id, display name)."""
        self._cursor_source.blockSignals(True)
        self._cursor_source.clear()
        for trace_id, name in options:
            self._cursor_source.addItem(name, trace_id)
        if current is not None:
            idx = self._cursor_source.findData(current)
            self._cursor_source.setCurrentIndex(idx)
        self._cursor_source.blockSignals(False)

    def display_traces(self, specs: list[dict]) -> None:
        """Rebuild trace rows.  Spec keys: id, name, color, visible,
        line_style, marker."""
        while self._traces_box.count():
            item = self._traces_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for spec in specs:
            self._traces_box.addWidget(_TraceRow(self, spec))
        self._traces_empty.setVisible(not specs)

    def display_cursor_readout(self, text: str) -> None:
        self._readout.setText(text)

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

    def _pick_color(self, trace_id: str, current: str) -> None:
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            self.trace_color_changed.emit(trace_id, color.name())
