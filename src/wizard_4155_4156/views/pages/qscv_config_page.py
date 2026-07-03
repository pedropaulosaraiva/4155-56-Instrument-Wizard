"""
views/pages/qscv_config_page.py
-------------------------------
Quasi-static C-V (QSCV) Configuration page — pure View layer.

Mirrors sweep_config_page.py (header + 2-column scroll body) but with
QSCV-specific sections.  QSCV does NOT use the shared MeasSetupSection
(integration mode SHORT/MED/LONG has no effect in QSCV) nor the per-unit
RangesSection (QSCV has a single capacitance current range); those are
replaced by `_QscvMeasSetupSection`.  The voltage staircase lives in
`_QscvVar1Section` (no spacing / power-compliance — QSCV is always linear).

Layout
------
Left column : channel summary · user-function names (cap/leak) · display vars.
Right column: QSCV measure setup (accent bar) · VAR1 sweep ·
constants · timing.

Reused shared sections: ChannelSummarySection, ConstantsSection,
DisplayVarsSection, and the SciDoubleEdit / SegmentedGroup / SectionFrame /
form_row primitives from views/widgets/config_sections.py.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.qscv_config import (
    CSTEP_MAX,
    cap_integration_bounds,
    leak_integration_bounds,
)
from wizard_4155_4156.models.sweep_config import (
    COMP_I_MAX,
    COMP_I_MIN,
    DELAY_MAX,
    DELAY_MIN,
    HOLD_TIME_MAX,
    HOLD_TIME_MIN,
    VOLTAGE_MAX,
    VOLTAGE_MIN,
    VOLTAGE_STEP_MAX,
    VOLTAGE_STEP_MIN,
    SweepConstraints,
)
from wizard_4155_4156.styles.stylesheets import (
    config_page_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.config_sections import (
    ChannelSummarySection as _ChannelSummarySection,
)
from wizard_4155_4156.views.widgets.config_sections import (
    ConstantsSection as _ConstantsSection,
)
from wizard_4155_4156.views.widgets.config_sections import (
    DisplayVarsSection as _DisplayVarsSection,
)
from wizard_4155_4156.views.widgets.config_sections import (
    JsonPreviewDialog as _JsonPreviewDialog,
)
from wizard_4155_4156.views.widgets.config_sections import (
    SciDoubleEdit as _SciDoubleEdit,
)
from wizard_4155_4156.views.widgets.config_sections import (
    SectionFrame as _SectionFrame,
)
from wizard_4155_4156.views.widgets.config_sections import (
    SegmentedGroup as _SegmentedGroup,
)
from wizard_4155_4156.views.widgets.config_sections import (
    form_row as _form_row,
)
from wizard_4155_4156.views.widgets.measurement_status import MeasurementTopBar


class _QscvNamesSection(_SectionFrame):
    """User-function output names: capacitance (CNAME) and leakage (LNAME)."""

    cap_name_changed = Signal(str)
    leak_name_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "User Functions",
            parent,
            doc_topic=DocTopic.QSCV_USER_FUNCTIONS,
        )

        self._cname_edit = QLineEdit()
        self._cname_edit.setStyleSheet(unit_card_line_edit_stylesheet())
        self._cname_edit.setMaxLength(6)
        self.body().addWidget(_form_row("Capacitance Name", self._cname_edit))

        self._iname_edit = QLineEdit()
        self._iname_edit.setStyleSheet(unit_card_line_edit_stylesheet())
        self._iname_edit.setMaxLength(6)
        self.body().addWidget(
            _form_row("Leakage Current Name", self._iname_edit)
        )

        self._cname_edit.editingFinished.connect(
            lambda: self.cap_name_changed.emit(self._cname_edit.text().strip())
        )
        self._iname_edit.editingFinished.connect(
            lambda: self.leak_name_changed.emit(
                self._iname_edit.text().strip()
            )
        )

    def display_state(self, cname: str, iname: str) -> None:
        self._cname_edit.setText(cname)
        self._iname_edit.setText(iname)


class _QscvMeasSetupSection(_SectionFrame):
    """Capacitance measurement setup: unit, range, integration times, flags."""

    unit_changed = Signal(str)
    range_changed = Signal(float)
    cap_int_committed = Signal(float)
    leak_int_committed = Signal(float)
    leak_comp_changed = Signal(bool)
    zero_cancel_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "QSCV Measure Setup",
            parent,
            accent=P.ACCENT,
            doc_topic=DocTopic.QSCV_MEASURE_SETUP,
        )
        self._range_values: List[float] = []
        self._range_resolutions: List[str] = []

        self._unit_combo = QComboBox()
        self._unit_combo.setStyleSheet(unit_card_combo_stylesheet())
        self.body().addWidget(_form_row("Measurement Unit", self._unit_combo))

        self._range_combo = QComboBox()
        self._range_combo.setStyleSheet(unit_card_combo_stylesheet())
        self.body().addWidget(
            _form_row("Measurement Range", self._range_combo)
        )

        cap_lo, cap_hi = cap_integration_bounds(50)
        self._cap_int_edit = _SciDoubleEdit(0.1, cap_lo, cap_hi, "s")
        self.body().addWidget(
            _form_row("QSCV Integration Time", self._cap_int_edit)
        )

        leak_lo, leak_hi = leak_integration_bounds(50)
        self._leak_int_edit = _SciDoubleEdit(0.1, leak_lo, leak_hi, "s")
        self.body().addWidget(
            _form_row("Leak Integration Time", self._leak_int_edit)
        )

        self._leak_seg = _SegmentedGroup(["OFF", "ON"], "OFF")
        self.body().addWidget(_form_row("Leak Compensation", self._leak_seg))

        self._zero_seg = _SegmentedGroup(["OFF", "ON"], "OFF")
        self.body().addWidget(_form_row("Zero Cancel", self._zero_seg))

        # Resolution as a bottom sub-label (styled like VAR1's "Assigned:").
        self._resolution_lbl = QLabel("")
        self._resolution_lbl.setStyleSheet(
            f"color: {P.ACCENT}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._resolution_lbl)

        self._unit_combo.currentIndexChanged.connect(self._on_unit)
        self._range_combo.currentIndexChanged.connect(self._on_range)
        self._cap_int_edit.value_committed.connect(self.cap_int_committed)
        self._leak_int_edit.value_committed.connect(self.leak_int_committed)
        self._leak_seg.selection_changed.connect(
            lambda v: self.leak_comp_changed.emit(v == "ON")
        )
        self._zero_seg.selection_changed.connect(
            lambda v: self.zero_cancel_changed.emit(v == "ON")
        )

    # ── Display API ─────────────────────────────────────────────────────

    def display_units(self, options: List[str], current: str) -> None:
        self._unit_combo.blockSignals(True)
        self._unit_combo.clear()
        for opt in options:
            self._unit_combo.addItem(opt, opt)
        idx = self._unit_combo.findData(current)
        self._unit_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._unit_combo.blockSignals(False)

    def display_ranges(
        self, ranges: List[Tuple[str, float, str]], current_value: float
    ) -> None:
        self._range_combo.blockSignals(True)
        self._range_combo.clear()
        self._range_values = []
        self._range_resolutions = []
        sel = 0
        for i, (label, value, resolution) in enumerate(ranges):
            self._range_combo.addItem(label, value)
            self._range_values.append(value)
            self._range_resolutions.append(resolution)
            if value == current_value:
                sel = i
        self._range_combo.setCurrentIndex(sel)
        self._range_combo.blockSignals(False)
        self._update_resolution_label()

    def display_integration_bounds(
        self, cap_bounds: Tuple[float, float], leak_bounds: Tuple[float, float]
    ) -> None:
        self._cap_int_edit.update_bounds(cap_bounds[0], cap_bounds[1], "s")
        self._leak_int_edit.update_bounds(leak_bounds[0], leak_bounds[1], "s")

    def display_state(
        self,
        cap_time: float,
        leak_time: float,
        leak_comp: bool,
        zero_cancel: bool,
    ) -> None:
        self._cap_int_edit.set_value(cap_time)
        self._leak_int_edit.set_value(leak_time)
        self._leak_seg.set_value("ON" if leak_comp else "OFF")
        self._zero_seg.set_value("ON" if zero_cancel else "OFF")

    def current_unit(self) -> str:
        return self._unit_combo.currentData() or "DEFAULT"

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._cap_int_edit.get_value() is None:
            errors["cap_int"] = (
                "QSCV Integration Time: value is empty or invalid"
            )
        if self._leak_int_edit.get_value() is None:
            errors["leak_int"] = (
                "Leak Integration Time: value is empty or invalid"
            )
        return errors

    # ── Private ─────────────────────────────────────────────────────────

    def _update_resolution_label(self) -> None:
        idx = self._range_combo.currentIndex()
        if 0 <= idx < len(self._range_resolutions):
            self._resolution_lbl.setText(
                f"Resolution: {self._range_resolutions[idx]}"
            )
        else:
            self._resolution_lbl.setText("")

    def _on_unit(self, _idx: int) -> None:
        self.unit_changed.emit(self.current_unit())

    def _on_range(self, idx: int) -> None:
        self._update_resolution_label()
        if 0 <= idx < len(self._range_values):
            self.range_changed.emit(self._range_values[idx])


class _QscvTimingSection(_SectionFrame):
    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "QSCV Timing", parent, doc_topic=DocTopic.QSCV_TIMING
        )
        self._delay_edit = _SciDoubleEdit(0.0, DELAY_MIN, DELAY_MAX, "s")
        self._delay_edit._edit.setToolTip(
            f"Range: {DELAY_MIN} – {DELAY_MAX} s"
        )
        self.body().addWidget(_form_row("Delay", self._delay_edit))

        self._hold_edit = _SciDoubleEdit(
            0.0, HOLD_TIME_MIN, HOLD_TIME_MAX, "s"
        )
        self._hold_edit._edit.setToolTip(
            f"Range: {HOLD_TIME_MIN} – {HOLD_TIME_MAX} s"
        )
        self.body().addWidget(_form_row("Hold Time", self._hold_edit))

        self._stop_seg = _SegmentedGroup(
            ["ABNORMAL", "COMPLIANCE", "OFF"], "OFF"
        )
        self.body().addWidget(_form_row("Sweep Stop", self._stop_seg))

        self._delay_edit.value_committed.connect(self.delay_committed)
        self._hold_edit.value_committed.connect(self.hold_time_committed)
        self._stop_seg.selection_changed.connect(self.sweep_stop_changed)

    def display_state(
        self, delay: float, hold_time: float, sweep_stop: str
    ) -> None:
        self._delay_edit.set_value(delay)
        self._hold_edit.set_value(hold_time)
        self._stop_seg.set_value(sweep_stop)

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._delay_edit.get_value() is None:
            errors["delay"] = "Delay: value is empty or invalid"
        if self._hold_edit.get_value() is None:
            errors["hold_time"] = "Hold Time: value is empty or invalid"
        return errors


class _QscvVar1Section(_SectionFrame):
    """Voltage staircase sweep — always linear, always an SMU forcing V."""

    mode_changed = Signal(str)
    start_committed = Signal(float)
    stop_committed = Signal(float)
    step_committed = Signal(float)
    cstep_committed = Signal(float)
    comp_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "VAR1  —  Voltage Sweep",
            parent,
            accent=P.FUNC_VAR1,
            doc_topic=DocTopic.QSCV_VAR1,
        )
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.FUNC_VAR1}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._channel_lbl)

        self._mode_seg = _SegmentedGroup(["SINGLE", "DOUBLE"], "SINGLE")
        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._stop_edit = _SciDoubleEdit(1.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(
            0.1, VOLTAGE_STEP_MIN, VOLTAGE_STEP_MAX, "V", disallow_zero=True
        )
        self._cstep_edit = _SciDoubleEdit(0.1, 0.0, CSTEP_MAX, "V")
        self._cstep_edit._edit.setToolTip(
            "Capacitance measurement voltage: "
            f"0 < v ≤ {CSTEP_MAX:g} V and ≤ |Step|"
        )
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")

        for row in [
            _form_row("Mode", self._mode_seg),
            _form_row("Start", self._start_edit),
            _form_row("Stop", self._stop_edit),
            _form_row("Step", self._step_edit),
            _form_row("QSCV Meas Voltage", self._cstep_edit),
            _form_row("Compliance", self._comp_edit),
        ]:
            self.body().addWidget(row)

        self._mode_seg.selection_changed.connect(self.mode_changed)
        self._start_edit.value_committed.connect(self.start_committed)
        self._stop_edit.value_committed.connect(self.stop_committed)
        self._step_edit.value_committed.connect(self.step_committed)
        self._cstep_edit.value_committed.connect(self.cstep_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)

    def display_state(
        self,
        mode: str,
        start: float,
        stop: float,
        step: float,
        cstep: float,
        compliance: float,
    ) -> None:
        self._mode_seg.set_value(mode)
        self._start_edit.set_value(start)
        self._stop_edit.set_value(stop)
        self._step_edit.set_value(step)
        self._cstep_edit.set_value(cstep)
        self._comp_edit.set_value(compliance)

    def display_context(
        self, channel_label: str, interlock_open: bool = False
    ) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")
        src_min, src_max = SweepConstraints.source_range(
            True, False, interlock_open
        )
        stp_min, stp_max = SweepConstraints.step_range(
            True, is_var2_or_offset=False, interlock_open=interlock_open
        )
        cmp_min, cmp_max = SweepConstraints.compliance_range(
            True, interlock_open
        )
        self._start_edit.update_bounds(src_min, src_max, "V")
        self._stop_edit.update_bounds(src_min, src_max, "V")
        self._step_edit.update_bounds(stp_min, stp_max, "V")
        self._comp_edit.update_bounds(cmp_min, cmp_max, "A")

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._start_edit.get_value() is None:
            errors["var1_start"] = "VAR1 Start: value is empty or invalid"
        if self._stop_edit.get_value() is None:
            errors["var1_stop"] = "VAR1 Stop: value is empty or invalid"
        if self._step_edit.get_value() is None:
            errors["var1_step"] = "VAR1 Step: value is empty or invalid"
        if self._cstep_edit.get_value() is None:
            errors["var1_cstep"] = (
                "QSCV Meas Voltage: value is empty or invalid"
            )
        if self._comp_edit.get_value() is None:
            errors["var1_comp"] = "VAR1 Compliance: value is empty or invalid"
        return errors


# ── Main page view ──────────────────────────────────────────────────────


class QscvConfigPageView(BasePage):
    """QSCV Configuration page (View)."""

    page_activated = Signal()

    # Measure setup
    unit_changed = Signal(str)
    range_changed = Signal(float)
    cap_int_committed = Signal(float)
    leak_int_committed = Signal(float)
    leak_comp_changed = Signal(bool)
    zero_cancel_changed = Signal(bool)

    # User-function names
    cap_name_changed = Signal(str)
    leak_name_changed = Signal(str)

    # Timing
    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    # VAR1
    var1_mode_changed = Signal(str)
    var1_start_committed = Signal(float)
    var1_stop_committed = Signal(float)
    var1_step_committed = Signal(float)
    var1_cstep_committed = Signal(float)
    var1_comp_committed = Signal(float)

    # Channels + vars + export
    smu_standby_changed = Signal(str, bool)
    display_var_toggled = Signal(str, bool)
    export_requested = Signal()
    save_requested = Signal(str)
    save_to_db_requested = Signal()
    apply_setup_requested = Signal()  # quick-apply setup over GPIB
    apply_run_fetch_requested = Signal()  # quick-apply setup + run + fetch
    save_message_expired = Signal()
    const_source_changed = Signal(str, float)
    const_compliance_changed = Signal(str, float)
    documentation_requested = Signal(str)  # DocTopic value (section doc icon)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._wire_sections()
        for section in self.findChildren(_SectionFrame):
            section.doc_requested.connect(self.documentation_requested)

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API ─────────────────────────────────────────────────────

    def display_channel_summary(self, active_channels: List[dict]) -> None:
        self._summary_sec.display_channels(active_channels)

    def display_measure_setup(
        self,
        unit_options: List[str],
        current_unit: str,
        ranges: List[Tuple[str, float, str]],
        current_range: float,
        cap_bounds: Tuple[float, float],
        leak_bounds: Tuple[float, float],
    ) -> None:
        self._meas_sec.display_units(unit_options, current_unit)
        self._meas_sec.display_ranges(ranges, current_range)
        self._meas_sec.display_integration_bounds(cap_bounds, leak_bounds)

    def display_config(self, snap: dict) -> None:
        ms = snap.get("measure_setup", {})
        self._meas_sec.display_state(
            ms.get("cap_time", 0.1),
            ms.get("leak_time", 0.1),
            ms.get("leak_comp", False),
            ms.get("zero_cancel", False),
        )
        self._names_sec.display_state(
            ms.get("cname", ""), ms.get("iname", "")
        )
        self._timing_sec.display_state(
            snap.get("delay", 0.0),
            snap.get("hold_time", 0.0),
            snap.get("sweep_stop", "OFF"),
        )
        v1 = snap.get("var1", {})
        self._var1_sec.display_state(
            v1.get("mode", "SINGLE"),
            v1.get("start", 0.0),
            v1.get("stop", 1.0),
            v1.get("step", 0.1),
            v1.get("cstep", 0.1),
            v1.get("compliance", 0.01),
        )

    def display_var1_context(
        self, channel_label: str, interlock_open: bool = False
    ) -> None:
        self._var1_sec.display_context(channel_label, interlock_open)

    def display_available_vars(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        self._display_vars_sec.display_available(var_names, selected)

    def display_constants_setup(
        self,
        active_channels: List[dict],
        constants_config: Dict[str, dict],
        interlock_open: bool = False,
    ) -> None:
        self._constants_sec.display_constants(
            active_channels, constants_config, interlock_open
        )

    def display_measurement_status(
        self,
        criticals: List[str],
        warnings: List[str],
        indexes: str,
        points: str,
        exec_time: str,
    ) -> None:
        """Push the setup's critical/warning/info state to the top bar."""
        self._top_bar.display_status(
            criticals, warnings, indexes, points, exec_time
        )

    def display_hardware_state(self, connected: bool, busy: bool) -> None:
        """Push GPIB readiness so the top bar can gate quick-apply actions."""
        self._top_bar.set_hardware_state(connected, busy)

    def display_json(self, json_str: str) -> None:
        dlg = _JsonPreviewDialog(
            json_str, self, title="Generated JSON — QSCV Configuration"
        )
        dlg.exec()

    def display_save_success(self, filename: str) -> None:
        self._top_bar.flash_saved(filename)

    def get_input_errors(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        errors.update(self._meas_sec.get_input_errors())
        errors.update(self._timing_sec.get_input_errors())
        errors.update(self._var1_sec.get_input_errors())
        if self._constants_sec.isVisible():
            errors.update(self._constants_sec.get_input_errors())
        return errors

    # ── Private — layout ──────────────────────────────────────────────

    def _on_save_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save QSCV Setup",
            "",
            "Setup files (*.json);;All files (*)",
        )
        if path:
            self.save_requested.emit(path)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(config_page_stylesheet())

        # Top bar: mode + doc, status widget, save/JSON actions
        self._top_bar = MeasurementTopBar(
            tr_ui(CommandWizardText.CFG_MODE_QSCV), DocTopic.QSCV_OVERVIEW
        )
        self._top_bar.save_setup_requested.connect(self.save_to_db_requested)
        self._top_bar.save_json_requested.connect(self._on_save_clicked)
        self._top_bar.export_requested.connect(self.export_requested)
        self._top_bar.apply_setup_requested.connect(
            self.apply_setup_requested
        )
        self._top_bar.apply_run_fetch_requested.connect(
            self.apply_run_fetch_requested
        )
        self._top_bar.documentation_requested.connect(
            self.documentation_requested
        )
        root.addWidget(self._top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        body = QWidget()
        body.setStyleSheet(f"background-color: {P.BG_DEEP};")
        body_h = QHBoxLayout(body)
        body_h.setContentsMargins(20, 20, 20, 20)
        body_h.setSpacing(20)
        body_h.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Left column (fixed 425 px)
        left = QWidget()
        left.setFixedWidth(425)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(20)
        left_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._summary_sec = _ChannelSummarySection()
        self._names_sec = _QscvNamesSection()
        self._display_vars_sec = _DisplayVarsSection()
        for w in (self._summary_sec, self._names_sec, self._display_vars_sec):
            left_v.addWidget(w)
        left_v.addStretch()

        # Right column (expanding)
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(12)
        right_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._meas_sec = _QscvMeasSetupSection()
        self._var1_sec = _QscvVar1Section()
        self._constants_sec = _ConstantsSection()
        self._timing_sec = _QscvTimingSection()
        for w in (
            self._meas_sec,
            self._var1_sec,
            self._constants_sec,
            self._timing_sec,
        ):
            right_v.addWidget(w)
        right_v.addStretch()

        body_h.addWidget(left)
        body_h.addWidget(right, stretch=1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _wire_sections(self) -> None:
        self._summary_sec.smu_standby_changed.connect(self.smu_standby_changed)

        n = self._names_sec
        n.cap_name_changed.connect(self.cap_name_changed)
        n.leak_name_changed.connect(self.leak_name_changed)

        m = self._meas_sec
        m.unit_changed.connect(self.unit_changed)
        m.range_changed.connect(self.range_changed)
        m.cap_int_committed.connect(self.cap_int_committed)
        m.leak_int_committed.connect(self.leak_int_committed)
        m.leak_comp_changed.connect(self.leak_comp_changed)
        m.zero_cancel_changed.connect(self.zero_cancel_changed)

        t = self._timing_sec
        t.delay_committed.connect(self.delay_committed)
        t.hold_time_committed.connect(self.hold_time_committed)
        t.sweep_stop_changed.connect(self.sweep_stop_changed)

        v1 = self._var1_sec
        v1.mode_changed.connect(self.var1_mode_changed)
        v1.start_committed.connect(self.var1_start_committed)
        v1.stop_committed.connect(self.var1_stop_committed)
        v1.step_committed.connect(self.var1_step_committed)
        v1.cstep_committed.connect(self.var1_cstep_committed)
        v1.comp_committed.connect(self.var1_comp_committed)

        self._display_vars_sec.var_toggled.connect(self.display_var_toggled)
        self._constants_sec.const_source_changed.connect(
            self.const_source_changed
        )
        self._constants_sec.const_compliance_changed.connect(
            self.const_compliance_changed
        )
