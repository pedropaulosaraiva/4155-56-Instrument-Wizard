"""
views/widgets/graph_plot_tab.py
-------------------------------
"Plot" sidebar tab — everything about how the ACTIVE plot presents its
data: per-axis settings (variable, autoscale, log, manual min/max,
engineering multiplier), title/axis labels, font sizes, and per-trace
styling rows (visibility, color, name, line style/width, marker
type/size).

Passive view: emits ``*_changed``/``*_committed`` signals; state arrives
through ``display_*`` methods.  The ``axis`` argument in axis signals is
``"x"`` or ``"y"``.  Trace payloads use the stable string trace ids.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    form_label_stylesheet,
    global_option_checkbox_stylesheet,
    graph_color_swatch_stylesheet,
    graph_trace_row_stylesheet,
    table_empty_label_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.config_sections import (
    SciDoubleEdit,
    SectionFrame,
    SegmentedGroup,
    combo,
    dspinbox,
    form_row,
    spinbox,
)

#: Multiplier selector options — MUST mirror the values of
#: ``models/graph/config.MULTIPLIERS`` (the presenter parses them back).
_MULTIPLIER_OPTIONS = ["p", "n", "µ", "m", "1", "k", "M", "G"]

_LABEL_WIDTH = 90
#: Shared width of the "Line:"/"Marker:" trace-row labels so the combos
#: in both rows stay vertically aligned.
_TRACE_ROW_LABEL_WIDTH = 48
_BOUND_LIMIT = 1e300
_FONT_PT_MIN = 6
_FONT_PT_MAX = 32
_LINE_WIDTH_MIN = 0.5
_LINE_WIDTH_MAX = 10.0
_LINE_WIDTH_STEP = 0.5
_MARKER_SIZE_MIN = 1.0
_MARKER_SIZE_MAX = 20.0
_MARKER_SIZE_STEP = 0.5

#: (element key, form label) — keys mirror PlotConfig.font_* fields.
_FONT_ELEMENTS: list[tuple[str, TXT]] = [
    ("title", TXT.GRAPH_LBL_FONT_TITLE),
    ("axis_x", TXT.GRAPH_LBL_FONT_X),
    ("axis_y", TXT.GRAPH_LBL_FONT_Y),
    ("ticks", TXT.GRAPH_LBL_FONT_TICKS),
    ("legend", TXT.GRAPH_LBL_FONT_LEGEND),
]

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


def _id_combo(options: list[tuple[str, TXT]]) -> QComboBox:
    box = QComboBox()
    box.setStyleSheet(unit_card_combo_stylesheet())
    # Shrinkable minimum (not longest-item) + tooltips for clipped text.
    box.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    box.setMinimumContentsLength(6)
    for logical_id, text in options:
        box.addItem(tr_ui(text), logical_id)
        box.setItemData(
            box.count() - 1, tr_ui(text), Qt.ItemDataRole.ToolTipRole
        )
    box.currentTextChanged.connect(box.setToolTip)
    box.setToolTip(box.currentText())
    return box


class _AxisSection:
    """The X-axis or Y-axis SectionFrame (built once per axis)."""

    def __init__(self, owner: "GraphPlotTab", axis: str, title: str):
        self.section = SectionFrame(
            title, flat=True, accent=P.GRAPH_TAB_PLOT
        )
        body = self.section.body()

        self.var_combo = combo([])
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_VARIABLE), self.var_combo, _LABEL_WIDTH
            )
        )

        self.auto_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_AUTOSCALE))
        self.auto_chk.setStyleSheet(global_option_checkbox_stylesheet())
        self.log_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_LOG))
        self.log_chk.setStyleSheet(global_option_checkbox_stylesheet())
        self.grid_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_GRID))
        self.grid_chk.setStyleSheet(global_option_checkbox_stylesheet())
        body.addWidget(self.auto_chk)
        body.addWidget(self.log_chk)
        body.addWidget(self.grid_chk)

        self.min_edit = SciDoubleEdit(
            0.0, -_BOUND_LIMIT, _BOUND_LIMIT, dim_when_disabled=True
        )
        self.max_edit = SciDoubleEdit(
            1.0, -_BOUND_LIMIT, _BOUND_LIMIT, dim_when_disabled=True
        )
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_MIN), self.min_edit, _LABEL_WIDTH)
        )
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_MAX), self.max_edit, _LABEL_WIDTH)
        )

        # Stacked full-width row — the only layout where 8 segments fit
        # the narrow sidebar (a form_row would leave them ~150px).
        mult_lbl = QLabel(tr_ui(TXT.GRAPH_LBL_MULTIPLIER))
        mult_lbl.setStyleSheet(form_label_stylesheet())
        body.addWidget(mult_lbl)
        self.mult_group = SegmentedGroup(
            _MULTIPLIER_OPTIONS, "1", compact=True
        )
        body.addWidget(self.mult_group)

        self.var_combo.currentTextChanged.connect(
            lambda name: owner._on_variable_changed(axis, name)
        )
        self.auto_chk.toggled.connect(
            lambda on: owner.axis_autoscale_changed.emit(axis, on)
        )
        self.log_chk.toggled.connect(
            lambda on: owner.axis_log_changed.emit(axis, on)
        )
        self.grid_chk.toggled.connect(
            lambda on: owner.axis_grid_changed.emit(axis, on)
        )
        self.min_edit.value_committed.connect(
            lambda v: owner.axis_min_committed.emit(axis, v)
        )
        self.max_edit.value_committed.connect(
            lambda v: owner.axis_max_committed.emit(axis, v)
        )
        self.mult_group.selection_changed.connect(
            lambda label: owner.axis_multiplier_changed.emit(axis, label)
        )

    def display(self, cfg: dict) -> None:
        """Push one axis state (keys mirror models AxisConfig fields)."""
        for widget in (
            self.var_combo,
            self.auto_chk,
            self.log_chk,
            self.grid_chk,
        ):
            widget.blockSignals(True)
        idx = self.var_combo.findText(cfg.get("variable") or "")
        self.var_combo.setCurrentIndex(idx)
        self.auto_chk.setChecked(bool(cfg.get("auto_scale", True)))
        self.log_chk.setChecked(bool(cfg.get("log", False)))
        self.grid_chk.setChecked(bool(cfg.get("grid", True)))
        for widget in (
            self.var_combo,
            self.auto_chk,
            self.log_chk,
            self.grid_chk,
        ):
            widget.blockSignals(False)

        if cfg.get("min_val") is not None:
            self.min_edit.set_value(float(cfg["min_val"]))
        if cfg.get("max_val") is not None:
            self.max_edit.set_value(float(cfg["max_val"]))
        self.mult_group.set_value(cfg.get("multiplier", "1"))

        manual = not cfg.get("auto_scale", True)
        self.min_edit.setEnabled(manual)
        self.max_edit.setEnabled(manual)
        # setScale conflicts with log ticks → multiplier locked on log.
        self.mult_group.setEnabled(not cfg.get("log", False))

    def set_variables(self, options: list[str]) -> None:
        current = self.var_combo.currentText()
        self.var_combo.blockSignals(True)
        self.var_combo.clear()
        for opt in options:
            self.var_combo.addItem(opt, opt)
            self.var_combo.setItemData(
                self.var_combo.count() - 1,
                opt,
                Qt.ItemDataRole.ToolTipRole,
            )
        idx = self.var_combo.findText(current)
        self.var_combo.setCurrentIndex(idx)
        self.var_combo.blockSignals(False)


class _TraceRow(QFrame):
    """Three-line styling row — the name owns the full first line so it
    stays readable in the narrow sidebar; line and marker each pair
    their type with its size:

    [visible] [swatch] [name………………]
    [Line:]   [line style combo] [line width]
    [Marker:] [marker combo] [marker size]
    """

    def __init__(self, owner: "GraphPlotTab", spec: dict) -> None:
        super().__init__()
        self.setObjectName("trace_row")
        self.setStyleSheet(graph_trace_row_stylesheet())
        trace_id = spec["id"]
        self.setToolTip(spec["name"])

        v = QVBoxLayout(self)
        v.setContentsMargins(6, 4, 6, 4)
        v.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(6)
        line_row = QHBoxLayout()
        line_row.setSpacing(6)
        marker_row = QHBoxLayout()
        marker_row.setSpacing(6)
        v.addLayout(top)
        v.addLayout(line_row)
        v.addLayout(marker_row)

        visible = QCheckBox()
        visible.setStyleSheet(global_option_checkbox_stylesheet())
        visible.setChecked(bool(spec["visible"]))
        visible.toggled.connect(
            lambda on: owner.trace_visibility_changed.emit(trace_id, on)
        )
        top.addWidget(visible)

        swatch = QPushButton()
        swatch.setFixedSize(20, 20)
        swatch.setStyleSheet(graph_color_swatch_stylesheet(spec["color"]))
        swatch.clicked.connect(
            lambda: owner._pick_color(trace_id, spec["color"])
        )
        top.addWidget(swatch)

        name = QLineEdit(spec["name"])
        name.setStyleSheet(unit_card_line_edit_stylesheet())
        name.setToolTip(spec["name"])
        name.textChanged.connect(name.setToolTip)  # full text when clipped
        name.editingFinished.connect(
            lambda: owner.trace_renamed.emit(trace_id, name.text())
        )
        top.addWidget(name, stretch=1)

        line_lbl = QLabel(tr_ui(TXT.GRAPH_LBL_LINE))
        line_lbl.setStyleSheet(form_label_stylesheet())
        line_lbl.setFixedWidth(_TRACE_ROW_LABEL_WIDTH)
        line_row.addWidget(line_lbl)

        line = _id_combo(_LINE_STYLE_OPTIONS)
        line.setCurrentIndex(max(0, line.findData(spec["line_style"])))
        line.currentIndexChanged.connect(
            lambda _i: owner.trace_line_style_changed.emit(
                trace_id, line.currentData()
            )
        )
        line_row.addWidget(line, stretch=1)

        width = dspinbox(
            _LINE_WIDTH_MIN,
            _LINE_WIDTH_MAX,
            _LINE_WIDTH_STEP,
            float(spec["width"]),
        )
        width.setToolTip(tr_ui(TXT.GRAPH_TT_TRACE_WIDTH))
        width.valueChanged.connect(
            lambda v: owner.trace_width_changed.emit(trace_id, v)
        )
        line_row.addWidget(width)

        marker_lbl = QLabel(tr_ui(TXT.GRAPH_LBL_MARKER))
        marker_lbl.setStyleSheet(form_label_stylesheet())
        marker_lbl.setFixedWidth(_TRACE_ROW_LABEL_WIDTH)
        marker_row.addWidget(marker_lbl)

        marker = _id_combo(_MARKER_OPTIONS)
        marker.setCurrentIndex(max(0, marker.findData(spec["marker"])))
        marker.currentIndexChanged.connect(
            lambda _i: owner.trace_marker_changed.emit(
                trace_id, marker.currentData()
            )
        )
        marker_row.addWidget(marker, stretch=1)

        marker_size = dspinbox(
            _MARKER_SIZE_MIN,
            _MARKER_SIZE_MAX,
            _MARKER_SIZE_STEP,
            float(spec["marker_size"]),
        )
        marker_size.setToolTip(tr_ui(TXT.GRAPH_TT_MARKER_SIZE))
        marker_size.valueChanged.connect(
            lambda v: owner.trace_marker_size_changed.emit(trace_id, v)
        )
        marker_row.addWidget(marker_size)


class GraphPlotTab(QWidget):
    """Axes / labels / per-trace styling of the active plot."""

    x_variable_changed = Signal(str)
    y_variable_changed = Signal(str)
    axis_autoscale_changed = Signal(str, bool)  # (axis, on)
    axis_log_changed = Signal(str, bool)
    axis_grid_changed = Signal(str, bool)
    axis_min_committed = Signal(str, float)
    axis_max_committed = Signal(str, float)
    axis_multiplier_changed = Signal(str, str)  # (axis, label)
    plot_title_committed = Signal(str)
    axis_label_committed = Signal(str, str)  # (axis, text)
    trace_visibility_changed = Signal(str, bool)
    trace_color_changed = Signal(str, str)  # (trace id, hex color)
    trace_renamed = Signal(str, str)
    trace_line_style_changed = Signal(str, str)
    trace_marker_changed = Signal(str, str)
    trace_width_changed = Signal(str, float)
    trace_marker_size_changed = Signal(str, float)
    plot_font_size_changed = Signal(str, int)  # (element key, size in pt)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        self._axis_x = _AxisSection(self, "x", tr_ui(TXT.GRAPH_SEC_AXIS_X))
        self._axis_y = _AxisSection(self, "y", tr_ui(TXT.GRAPH_SEC_AXIS_Y))
        root.addWidget(self._axis_x.section)
        root.addWidget(self._axis_y.section)
        root.addWidget(self._build_labels_section())
        root.addWidget(self._build_fonts_section())
        root.addWidget(self._build_traces_section())
        root.addStretch(1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_labels_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_LABELS), flat=True, accent=P.GRAPH_TAB_PLOT
        )
        body = section.body()

        self._title_edit = QLineEdit()
        self._title_edit.setStyleSheet(unit_card_line_edit_stylesheet())
        self._title_edit.setPlaceholderText(tr_ui(TXT.GRAPH_PH_TITLE))
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
            edit.setPlaceholderText(tr_ui(TXT.GRAPH_PH_AXIS_LABEL))
            edit.editingFinished.connect(
                lambda a=axis, e=edit: self.axis_label_committed.emit(
                    a, e.text()
                )
            )
            body.addWidget(form_row(tr_ui(text), edit, _LABEL_WIDTH))
        return section

    def _build_fonts_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_FONTS), flat=True, accent=P.GRAPH_TAB_PLOT
        )
        body = section.body()

        self._font_spins: dict[str, QSpinBox] = {}
        for element, text in _FONT_ELEMENTS:
            spin = spinbox(_FONT_PT_MIN, _FONT_PT_MAX, _FONT_PT_MIN)
            spin.valueChanged.connect(
                lambda v, e=element: self.plot_font_size_changed.emit(e, v)
            )
            self._font_spins[element] = spin
            body.addWidget(form_row(tr_ui(text), spin, _LABEL_WIDTH))
        return section

    def _build_traces_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_TRACES), flat=True, accent=P.GRAPH_TAB_PLOT
        )
        self._traces_box = QVBoxLayout()
        self._traces_box.setSpacing(6)
        section.body().addLayout(self._traces_box)

        self._traces_empty = QLabel(tr_ui(TXT.GRAPH_NO_TRACES))
        self._traces_empty.setStyleSheet(table_empty_label_stylesheet())
        section.body().addWidget(self._traces_empty)
        return section

    # ── Public display API ──────────────────────────────────────────────────

    def display_variables(
        self, options: list[str], x_var: str | None, y_var: str | None
    ) -> None:
        self._axis_x.set_variables(options)
        self._axis_y.set_variables(options)
        self._axis_x.display({"variable": x_var, **self._axis_state("x")})
        self._axis_y.display({"variable": y_var, **self._axis_state("y")})

    def display_axis(self, axis: str, cfg: dict) -> None:
        """cfg keys: variable, auto_scale, log, grid, min_val, max_val,
        multiplier."""
        (self._axis_x if axis == "x" else self._axis_y).display(cfg)

    def display_labels(self, title: str, x_label: str, y_label: str) -> None:
        for edit, text in (
            (self._title_edit, title),
            (self._x_label_edit, x_label),
            (self._y_label_edit, y_label),
        ):
            edit.blockSignals(True)
            edit.setText(text)
            edit.blockSignals(False)

    def display_fonts(self, fonts: dict[str, int]) -> None:
        """Push font sizes; keys mirror ``_FONT_ELEMENTS`` element ids."""
        for element, spin in self._font_spins.items():
            spin.blockSignals(True)
            spin.setValue(int(fonts[element]))
            spin.blockSignals(False)

    def display_traces(self, specs: list[dict]) -> None:
        """Rebuild trace rows.  Spec keys: id, name, color, visible,
        line_style, marker, width, marker_size."""
        while self._traces_box.count():
            item = self._traces_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for spec in specs:
            self._traces_box.addWidget(_TraceRow(self, spec))
        self._traces_empty.setVisible(not specs)

    # ── Internals ───────────────────────────────────────────────────────────

    def _axis_state(self, axis: str) -> dict:
        """Current widget state (used to re-display on variable refresh)."""
        section = self._axis_x if axis == "x" else self._axis_y
        return {
            "auto_scale": section.auto_chk.isChecked(),
            "log": section.log_chk.isChecked(),
            "grid": section.grid_chk.isChecked(),
            "min_val": section.min_edit.get_value(),
            "max_val": section.max_edit.get_value(),
            "multiplier": section.mult_group.current_value(),
        }

    def _on_variable_changed(self, axis: str, name: str) -> None:
        if not name:
            return
        if axis == "x":
            self.x_variable_changed.emit(name)
        else:
            self.y_variable_changed.emit(name)

    def _pick_color(self, trace_id: str, current: str) -> None:
        color = QColorDialog.getColor(QColor(current), self)
        if color.isValid():
            self.trace_color_changed.emit(trace_id, color.name())
