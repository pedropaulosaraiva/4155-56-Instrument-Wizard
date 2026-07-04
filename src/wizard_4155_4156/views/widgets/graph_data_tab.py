"""
views/widgets/graph_data_tab.py
-------------------------------
"Data" sidebar tab — configures the ACTIVE plot of the current scene:
dataset (execution) selection, grid layout, and per-axis settings
(variable, autoscale, log, manual min/max, engineering multiplier).

Passive view: emits ``*_changed``/``*_committed`` signals; state arrives
through ``display_*`` methods.  The ``axis`` argument in axis signals is
``"x"`` or ``"y"``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    global_option_checkbox_stylesheet,
    graph_dataset_tree_stylesheet,
)
from wizard_4155_4156.views.widgets.config_sections import (
    SciDoubleEdit,
    SectionFrame,
    SegmentedGroup,
    combo,
    form_row,
    spinbox,
)

#: Multiplier selector options — MUST mirror the values of
#: ``models/graph/config.MULTIPLIERS`` (the presenter parses them back).
_MULTIPLIER_OPTIONS = ["p", "n", "µ", "m", "1", "k", "M", "G"]

_EXEC_ID_ROLE = Qt.ItemDataRole.UserRole
_LABEL_WIDTH = 90
_BOUND_LIMIT = 1e300


class _AxisSection:
    """The X-axis or Y-axis SectionFrame (built once per axis)."""

    def __init__(self, owner: "GraphDataTab", axis: str, title: str):
        self.section = SectionFrame(title)
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
        body.addWidget(self.auto_chk)
        body.addWidget(self.log_chk)

        self.min_edit = SciDoubleEdit(0.0, -_BOUND_LIMIT, _BOUND_LIMIT)
        self.max_edit = SciDoubleEdit(1.0, -_BOUND_LIMIT, _BOUND_LIMIT)
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_MIN), self.min_edit, _LABEL_WIDTH)
        )
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_MAX), self.max_edit, _LABEL_WIDTH)
        )

        self.mult_group = SegmentedGroup(_MULTIPLIER_OPTIONS, "1")
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_MULTIPLIER),
                self.mult_group,
                _LABEL_WIDTH,
            )
        )

        self.var_combo.currentTextChanged.connect(
            lambda name: owner._on_variable_changed(axis, name)
        )
        self.auto_chk.toggled.connect(
            lambda on: owner.axis_autoscale_changed.emit(axis, on)
        )
        self.log_chk.toggled.connect(
            lambda on: owner.axis_log_changed.emit(axis, on)
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
        ):
            widget.blockSignals(True)
        idx = self.var_combo.findText(cfg.get("variable") or "")
        self.var_combo.setCurrentIndex(idx)
        self.auto_chk.setChecked(bool(cfg.get("auto_scale", True)))
        self.log_chk.setChecked(bool(cfg.get("log", False)))
        for widget in (
            self.var_combo,
            self.auto_chk,
            self.log_chk,
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
        idx = self.var_combo.findText(current)
        self.var_combo.setCurrentIndex(idx)
        self.var_combo.blockSignals(False)


class GraphDataTab(QWidget):
    """Dataset / layout / axis configuration of the active plot."""

    execution_check_changed = Signal(int, bool)  # (exec_id, checked)
    grid_layout_changed = Signal(int, int)  # (rows, cols)
    maximize_toggled = Signal(bool)
    x_variable_changed = Signal(str)
    y_variable_changed = Signal(str)
    axis_autoscale_changed = Signal(str, bool)  # (axis, on)
    axis_log_changed = Signal(str, bool)
    axis_min_committed = Signal(str, float)
    axis_max_committed = Signal(str, float)
    axis_multiplier_changed = Signal(str, str)  # (axis, label)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        root.addWidget(self._build_datasets_section())
        root.addWidget(self._build_layout_section())
        self._axis_x = _AxisSection(self, "x", tr_ui(TXT.GRAPH_SEC_AXIS_X))
        self._axis_y = _AxisSection(self, "y", tr_ui(TXT.GRAPH_SEC_AXIS_Y))
        root.addWidget(self._axis_x.section)
        root.addWidget(self._axis_y.section)
        root.addStretch(1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_datasets_section(self) -> SectionFrame:
        section = SectionFrame(tr_ui(TXT.GRAPH_SEC_DATASETS))
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet(graph_dataset_tree_stylesheet())
        self._tree.setMinimumHeight(150)
        self._tree.itemChanged.connect(self._on_item_changed)
        section.body().addWidget(self._tree)
        return section

    def _build_layout_section(self) -> SectionFrame:
        section = SectionFrame(tr_ui(TXT.GRAPH_SEC_LAYOUT))
        body = section.body()

        self._rows_spin = spinbox(1, 3, 1)
        self._cols_spin = spinbox(1, 3, 1)
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_ROWS), self._rows_spin, _LABEL_WIDTH)
        )
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_COLS), self._cols_spin, _LABEL_WIDTH)
        )

        self._maximize_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_MAXIMIZE))
        self._maximize_chk.setStyleSheet(global_option_checkbox_stylesheet())
        body.addWidget(self._maximize_chk)

        self._rows_spin.valueChanged.connect(self._emit_grid)
        self._cols_spin.valueChanged.connect(self._emit_grid)
        self._maximize_chk.toggled.connect(self.maximize_toggled)
        return section

    # ── Public display API ──────────────────────────────────────────────────

    def display_datasets(
        self,
        groups: list[tuple[str, list[tuple[int, str, bool, bool]]]],
    ) -> None:
        """Rebuild the tree: (setup label, [(id, label, checked, enabled)])."""
        self._tree.blockSignals(True)
        self._tree.clear()
        for setup_label, executions in groups:
            top = QTreeWidgetItem([setup_label])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._tree.addTopLevelItem(top)
            for exec_id, label, checked, enabled in executions:
                child = QTreeWidgetItem([label])
                child.setData(0, _EXEC_ID_ROLE, exec_id)
                flags = (
                    Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsSelectable
                )
                if enabled:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                else:
                    child.setToolTip(0, tr_ui(TXT.GRAPH_INCOMPATIBLE_TOOLTIP))
                child.setFlags(flags)
                child.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if checked
                    else Qt.CheckState.Unchecked,
                )
                top.addChild(child)
            top.setExpanded(True)
        self._tree.blockSignals(False)

    def display_variables(
        self, options: list[str], x_var: str | None, y_var: str | None
    ) -> None:
        self._axis_x.set_variables(options)
        self._axis_y.set_variables(options)
        self._axis_x.display({"variable": x_var, **self._axis_state("x")})
        self._axis_y.display({"variable": y_var, **self._axis_state("y")})

    def display_axis(self, axis: str, cfg: dict) -> None:
        """cfg keys: variable, auto_scale, log, min_val, max_val,
        multiplier."""
        (self._axis_x if axis == "x" else self._axis_y).display(cfg)

    def display_grid(self, rows: int, cols: int, maximized: bool) -> None:
        for widget in (self._rows_spin, self._cols_spin, self._maximize_chk):
            widget.blockSignals(True)
        self._rows_spin.setValue(rows)
        self._cols_spin.setValue(cols)
        self._maximize_chk.setChecked(maximized)
        for widget in (self._rows_spin, self._cols_spin, self._maximize_chk):
            widget.blockSignals(False)

    # ── Internals ───────────────────────────────────────────────────────────

    def _axis_state(self, axis: str) -> dict:
        """Current widget state (used to re-display on variable refresh)."""
        section = self._axis_x if axis == "x" else self._axis_y
        return {
            "auto_scale": section.auto_chk.isChecked(),
            "log": section.log_chk.isChecked(),
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

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        exec_id = item.data(column, _EXEC_ID_ROLE)
        if exec_id is None:
            return
        self.execution_check_changed.emit(
            int(exec_id), item.checkState(column) == Qt.CheckState.Checked
        )

    def _emit_grid(self) -> None:
        self.grid_layout_changed.emit(
            self._rows_spin.value(), self._cols_spin.value()
        )
