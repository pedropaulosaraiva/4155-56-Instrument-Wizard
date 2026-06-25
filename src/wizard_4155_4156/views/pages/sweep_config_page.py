"""
views/pages/sweep_config_page.py
---------------------------------
Sweep Configuration page — pure View layer.

Validation philosophy (simplified)
------------------------------------
1. _SciDoubleEdit handles its own per-widget bounds:
   - QDoubleValidator enforces min/max in the input.
   - Red border + tooltip appear on editingFinished when out of range.
   - update_bounds(min_v, max_v) lets the section update limits when the
     sweep type changes (voltage ↔ current, or VAR1 source changes).

2. Cross-parameter rules (step count, total points) are computed locally
   in _update_matrix_status() using values read directly from the widgets.
   A single QLabel at the top of the right column shows the result —
   green ✓ or red ⚠ with a plain-English description.

3. The presenter only touches validation via display_validation_errors()
   for export-blocking errors; routine editing never round-trips to the
   presenter for feedback.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.models.sweep_config import (
    COMP_I_MAX,
    COMP_I_MIN,
    DELAY_MAX,
    DELAY_MIN,
    HOLD_TIME_MAX,
    HOLD_TIME_MIN,
    PCOMP_MAX,
    PCOMP_MIN,
    RATIO_MAX,
    RATIO_MIN,
    VAR2_N_OF_STEPS_MAX,
    VAR2_N_OF_STEPS_MIN,
    VAR2_V_STEP_MAX,
    VAR2_V_STEP_MIN,
    VARD_OFFSET_I_MAX,
    VARD_OFFSET_I_MIN,
    VARD_OFFSET_V_MAX,
    VARD_OFFSET_V_MIN,
    VOLTAGE_MAX,
    VOLTAGE_MIN,
    VOLTAGE_STEP_MAX,
    VOLTAGE_STEP_MIN,
    SweepConstraints,
)
from wizard_4155_4156.styles.stylesheets import (
    config_page_stylesheet,
    export_btn_stylesheet,
    unit_enable_checkbox_stylesheet,
    validation_status_stylesheet,
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
    MeasSetupSection as _MeasSetupSection,
)
from wizard_4155_4156.views.widgets.config_sections import (
    RangesSection as _RangesSection,
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
from wizard_4155_4156.views.widgets.config_sections import (
    spinbox as _spinbox,
)


class _PCompWidget(QWidget):
    """Power-compliance value edit with an LED on/off toggle on its right.

    The LED lights green when power compliance is enabled and stays unlit
    when disabled (the JSON omits "pcompliance").  Disabled is the default
    state.
    """

    value_committed = Signal(float)
    enabled_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        self._edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")
        self._on_cb = QCheckBox()
        self._on_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self._on_cb.setToolTip("Power compliance ON / OFF")
        self._on_cb.setChecked(False)
        self._edit.setEnabled(False)

        h.addWidget(self._edit, stretch=1)
        h.addWidget(self._on_cb, stretch=1)

        self._edit.value_committed.connect(self.value_committed)
        self._on_cb.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self._edit.setEnabled(checked)
        self.enabled_changed.emit(checked)

    def display_state(self, value: float, enabled: bool) -> None:
        self._edit.set_value(value)
        self._on_cb.blockSignals(True)
        self._on_cb.setChecked(enabled)
        self._on_cb.blockSignals(False)
        self._edit.setEnabled(enabled)

    def is_pcomp_enabled(self) -> bool:
        return self._on_cb.isChecked()

    def get_value(self) -> Optional[float]:
        return self._edit.get_value()


class _SweepTimingSection(_SectionFrame):
    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Sweep Timing", parent, doc_topic=DocTopic.SWEEP_TIMING
        )
        self._delay_edit = _SciDoubleEdit(0.1, DELAY_MIN, DELAY_MAX, "s")
        self._delay_edit._edit.setToolTip(
            f"Range: {DELAY_MIN} – {DELAY_MAX} s"
        )
        self.body().addWidget(_form_row("Delay", self._delay_edit))

        # Hold time has a DIFFERENT (larger) max than delay
        self._hold_edit = _SciDoubleEdit(
            0.5, HOLD_TIME_MIN, HOLD_TIME_MAX, "s"
        )
        self._hold_edit._edit.setToolTip(
            f"Range: {HOLD_TIME_MIN} – {HOLD_TIME_MAX} s"
        )
        self.body().addWidget(_form_row("Hold Time", self._hold_edit))

        self._stop_seg = _SegmentedGroup(
            ["ABNORMAL", "COMPLIANCE", "OFF"], "COMPLIANCE"
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


class _VAR1Section(_SectionFrame):
    mode_changed = Signal(str)
    spacing_changed = Signal(str)
    start_committed = Signal(float)
    stop_committed = Signal(float)
    step_committed = Signal(float)
    comp_committed = Signal(float)
    pcomp_committed = Signal(float)
    pcomp_enabled_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "VAR1  —  Basic Sweep",
            parent,
            accent=P.FUNC_VAR1,
            doc_topic=DocTopic.SWEEP_VAR1,
        )
        self._is_vsu = False
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.FUNC_VAR1}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._channel_lbl)

        self._mode_seg = _SegmentedGroup(["SINGLE", "DOUBLE"], "SINGLE")
        self._spacing_seg = _SegmentedGroup(
            ["LINEAR", "L10", "L25", "L50"], "LINEAR"
        )
        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._stop_edit = _SciDoubleEdit(1.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(
            0.1, VOLTAGE_STEP_MIN, VOLTAGE_STEP_MAX, "V", disallow_zero=True
        )
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_widget = _PCompWidget()

        self._comp_row = _form_row("Compliance", self._comp_edit)
        self._pcomp_row = _form_row("Power Compliance", self._pcomp_widget)
        for row in [
            _form_row("Mode", self._mode_seg),
            _form_row("Spacing", self._spacing_seg),
            _form_row("Start", self._start_edit),
            _form_row("Stop", self._stop_edit),
            _form_row("Step", self._step_edit),
            self._comp_row,
            self._pcomp_row,
        ]:
            self.body().addWidget(row)

        self._mode_seg.selection_changed.connect(self.mode_changed)
        self._spacing_seg.selection_changed.connect(self.spacing_changed)
        self._spacing_seg.selection_changed.connect(self._on_spacing_changed)
        self._start_edit.value_committed.connect(self.start_committed)
        self._stop_edit.value_committed.connect(self.stop_committed)
        self._step_edit.value_committed.connect(self.step_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_widget.value_committed.connect(self.pcomp_committed)
        self._pcomp_widget.enabled_changed.connect(self.pcomp_enabled_changed)

    def _on_spacing_changed(self, spacing: str) -> None:
        is_linear = spacing == "LINEAR"
        self._step_edit.setEnabled(is_linear)

    # ── Display API ─────────────────────────────────────────────────────

    def display_state(
        self,
        mode: str,
        spacing: str,
        start: float,
        stop: float,
        step: float,
        compliance: float,
        pcomp: float,
        pcomp_enabled: bool,
    ) -> None:
        self._mode_seg.set_value(mode)
        self._spacing_seg.set_value(spacing)
        self._on_spacing_changed(spacing)
        self._start_edit.set_value(start)
        self._stop_edit.set_value(stop)
        self._step_edit.set_value(step)
        self._comp_edit.set_value(compliance)
        self._pcomp_widget.display_state(pcomp, pcomp_enabled)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(
        self,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        """Called by the view when sweep-type context changes."""
        SC = SweepConstraints
        self._is_vsu = is_vsu
        self._comp_row.setVisible(not is_vsu)
        self._pcomp_row.setVisible(not is_vsu)
        src_min, src_max = SC.source_range(is_voltage, is_vsu, interlock_open)
        if is_vsu:
            # VSU step spans the full range width in either direction
            stp_max = abs(src_max - src_min)
            stp_min = -stp_max
        else:
            stp_min, stp_max = SC.step_range(
                is_voltage,
                is_var2_or_offset=False,
                interlock_open=interlock_open,
            )
        cmp_min, cmp_max = SC.compliance_range(
            is_voltage or is_vsu, interlock_open
        )
        src_u = SC.source_unit(is_voltage or is_vsu)
        cmp_u = SC.compliance_unit(is_voltage or is_vsu)

        self._start_edit.update_bounds(src_min, src_max, src_u)
        self._stop_edit.update_bounds(src_min, src_max, src_u)
        self._step_edit.update_bounds(stp_min, stp_max, src_u)
        self._comp_edit.update_bounds(cmp_min, cmp_max, cmp_u)

    # ── Cross-param helper (read-only) ────────────────────────────────

    def get_step_count(self) -> Optional[int]:
        start = self._start_edit.get_value()
        stop = self._stop_edit.get_value()
        step = self._step_edit.get_value()
        spacing = self._spacing_seg.current_value()
        if spacing == "LINEAR":
            if all(v is not None for v in (start, stop, step)) and step != 0:
                return SweepConstraints.var1_step_count(
                    start, stop, step, spacing
                )
        elif all(v is not None for v in (start, stop)):
            return SweepConstraints.var1_step_count(
                start, stop, 0.0, spacing
            )
        return None

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._start_edit.get_value() is None:
            errors["var1_start"] = "VAR1 Start: value is empty or invalid"
        if self._stop_edit.get_value() is None:
            errors["var1_stop"] = "VAR1 Stop: value is empty or invalid"
        if self._spacing_seg.current_value() == "LINEAR":
            if self._step_edit.get_value() is None:
                errors["var1_step"] = "VAR1 Step: value is empty or invalid"
        if not self._is_vsu:
            if self._comp_edit.get_value() is None:
                errors["var1_comp"] = (
                    "VAR1 Compliance: value is empty or invalid"
                )
            if (
                self._pcomp_widget.is_pcomp_enabled()
                and self._pcomp_widget.get_value() is None
            ):
                errors["var1_pcomp"] = (
                    "VAR1 Power Compliance: value is empty or invalid"
                )
        return errors


class _VAR2Section(_SectionFrame):
    start_committed = Signal(float)
    step_committed = Signal(float)
    n_of_steps_changed = Signal(int)
    comp_committed = Signal(float)
    pcomp_committed = Signal(float)
    pcomp_enabled_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "VAR2  —  Subordinate Sweep",
            parent,
            accent=P.FUNC_VAR2,
            doc_topic=DocTopic.SWEEP_VAR2,
        )
        self._is_vsu = False
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.FUNC_VAR2}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._channel_lbl)

        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(
            0.1, VAR2_V_STEP_MIN, VAR2_V_STEP_MAX, "V", disallow_zero=True
        )
        self._n_steps_sb = _spinbox(
            VAR2_N_OF_STEPS_MIN, VAR2_N_OF_STEPS_MAX, 3
        )
        self._n_steps_sb.setToolTip(
            f"Range: {VAR2_N_OF_STEPS_MIN} – {VAR2_N_OF_STEPS_MAX}"
        )
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_widget = _PCompWidget()

        self._comp_row = _form_row("Compliance", self._comp_edit)
        self._pcomp_row = _form_row("Power Compliance", self._pcomp_widget)
        for row in [
            _form_row("Start", self._start_edit),
            _form_row("Step", self._step_edit),
            _form_row("Number of steps", self._n_steps_sb),
            self._comp_row,
            self._pcomp_row,
        ]:
            self.body().addWidget(row)

        self._start_edit.value_committed.connect(self.start_committed)
        self._step_edit.value_committed.connect(self.step_committed)
        self._n_steps_sb.valueChanged.connect(self.n_of_steps_changed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_widget.value_committed.connect(self.pcomp_committed)
        self._pcomp_widget.enabled_changed.connect(self.pcomp_enabled_changed)

    def display_state(
        self,
        start: float,
        step: float,
        n_of_steps: int,
        compliance: float,
        pcomp: float,
        pcomp_enabled: bool,
    ) -> None:
        self._start_edit.set_value(start)
        self._step_edit.set_value(step)
        self._n_steps_sb.blockSignals(True)
        self._n_steps_sb.setValue(n_of_steps)
        self._n_steps_sb.blockSignals(False)
        self._comp_edit.set_value(compliance)
        self._pcomp_widget.display_state(pcomp, pcomp_enabled)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(
        self,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        SC = SweepConstraints
        self._is_vsu = is_vsu
        self._comp_row.setVisible(not is_vsu)
        self._pcomp_row.setVisible(not is_vsu)
        src_min, src_max = SC.source_range(is_voltage, is_vsu, interlock_open)
        stp_min, stp_max = SC.step_range(
            is_voltage, is_var2_or_offset=True, interlock_open=interlock_open
        )
        cmp_min, cmp_max = SC.compliance_range(
            is_voltage or is_vsu, interlock_open
        )
        src_u = SC.source_unit(is_voltage or is_vsu)
        cmp_u = SC.compliance_unit(is_voltage or is_vsu)
        self._start_edit.update_bounds(src_min, src_max, src_u)
        self._step_edit.update_bounds(stp_min, stp_max, src_u)
        self._comp_edit.update_bounds(cmp_min, cmp_max, cmp_u)

    def get_n_of_steps(self) -> int:
        return self._n_steps_sb.value()

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._start_edit.get_value() is None:
            errors["var2_start"] = "VAR2 Start: value is empty or invalid"
        if self._step_edit.get_value() is None:
            errors["var2_step"] = "VAR2 Step: value is empty or invalid"
        if not self._is_vsu:
            if self._comp_edit.get_value() is None:
                errors["var2_comp"] = (
                    "VAR2 Compliance: value is empty or invalid"
                )
            if (
                self._pcomp_widget.is_pcomp_enabled()
                and self._pcomp_widget.get_value() is None
            ):
                errors["var2_pcomp"] = (
                    "VAR2 Power Compliance: value is empty or invalid"
                )
        return errors


class _VARDSection(_SectionFrame):
    offset_committed = Signal(float)
    ratio_committed = Signal(float)
    comp_committed = Signal(float)
    pcomp_committed = Signal(float)
    pcomp_enabled_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "VARD  —  Synchronous Sweep",
            parent,
            accent=P.FUNC_VARD,
            doc_topic=DocTopic.SWEEP_VARD,
        )
        self._is_vsu = False
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.FUNC_VARD}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._channel_lbl)

        note = QLabel("Output = VAR1 × ratio + offset")
        note.setStyleSheet(
            f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(note)

        self._offset_edit = _SciDoubleEdit(
            0.0, VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX, "V"
        )
        self._ratio_edit = _SciDoubleEdit(1.0, RATIO_MIN, RATIO_MAX, "×")
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_widget = _PCompWidget()

        self._comp_row = _form_row("Compliance", self._comp_edit)
        self._pcomp_row = _form_row("Power Compliance", self._pcomp_widget)
        for row in [
            _form_row("Offset", self._offset_edit),
            _form_row("Ratio", self._ratio_edit),
            self._comp_row,
            self._pcomp_row,
        ]:
            self.body().addWidget(row)

        self._offset_edit.value_committed.connect(self.offset_committed)
        self._ratio_edit.value_committed.connect(self.ratio_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_widget.value_committed.connect(self.pcomp_committed)
        self._pcomp_widget.enabled_changed.connect(self.pcomp_enabled_changed)

    def display_state(
        self,
        offset: float,
        ratio: float,
        compliance: float,
        pcomp: float,
        pcomp_enabled: bool,
    ) -> None:
        self._offset_edit.set_value(offset)
        self._ratio_edit.set_value(ratio)
        self._comp_edit.set_value(compliance)
        self._pcomp_widget.display_state(pcomp, pcomp_enabled)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(
        self,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        SC = SweepConstraints
        self._is_vsu = is_vsu
        self._comp_row.setVisible(not is_vsu)
        self._pcomp_row.setVisible(not is_vsu)
        if is_vsu:
            off_min, off_max = VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX
        elif is_voltage:
            off_min, off_max = SC.step_range(
                True, is_var2_or_offset=True, interlock_open=interlock_open
            )
        else:
            off_min, off_max = VARD_OFFSET_I_MIN, VARD_OFFSET_I_MAX
        cmp_min, cmp_max = SC.compliance_range(
            is_voltage or is_vsu, interlock_open
        )
        src_u = SC.source_unit(is_voltage or is_vsu)
        cmp_u = SC.compliance_unit(is_voltage or is_vsu)
        self._offset_edit.update_bounds(off_min, off_max, src_u)
        self._comp_edit.update_bounds(cmp_min, cmp_max, cmp_u)

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._offset_edit.get_value() is None:
            errors["vard_offset"] = "VARD Offset: value is empty or invalid"
        if self._ratio_edit.get_value() is None:
            errors["vard_ratio"] = "VARD Ratio: value is empty or invalid"
        if not self._is_vsu:
            if self._comp_edit.get_value() is None:
                errors["vard_comp"] = (
                    "VARD Compliance: value is empty or invalid"
                )
            if (
                self._pcomp_widget.is_pcomp_enabled()
                and self._pcomp_widget.get_value() is None
            ):
                errors["vard_pcomp"] = (
                    "VARD Power Compliance: value is empty or invalid"
                )
        return errors


# ── Main page view ──────────────────────────────────────────────────────


class SweepConfigPageView(BasePage):
    """
    Sweep Configuration page.

    on_activate() → page_activated → presenter refreshes channel context.

    Cross-parameter status is computed locally by _update_matrix_status()
    which reads the current widget values directly from _VAR1Section and
    _VAR2Section.  No presenter round-trip needed for this feedback.
    """

    page_activated = Signal()

    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_multiplier_committed = Signal(float)

    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    var1_mode_changed = Signal(str)
    var1_spacing_changed = Signal(str)
    var1_start_committed = Signal(float)
    var1_stop_committed = Signal(float)
    var1_step_committed = Signal(float)
    var1_comp_committed = Signal(float)
    var1_pcomp_committed = Signal(float)
    var1_pcomp_enabled_changed = Signal(bool)

    var2_start_committed = Signal(float)
    var2_step_committed = Signal(float)
    var2_n_of_steps_changed = Signal(int)
    var2_comp_committed = Signal(float)
    var2_pcomp_committed = Signal(float)
    var2_pcomp_enabled_changed = Signal(bool)

    vard_offset_committed = Signal(float)
    vard_ratio_committed = Signal(float)
    vard_comp_committed = Signal(float)
    vard_pcomp_committed = Signal(float)
    vard_pcomp_enabled_changed = Signal(bool)

    smu_standby_changed = Signal(str, bool)
    display_var_toggled = Signal(str, bool)
    export_requested = Signal()
    save_requested = Signal(str)  # chosen file path (Save JSON)
    save_to_db_requested = Signal()  # save setup into the project database
    save_message_expired = Signal()  # transient "Saved" toast timed out
    range_changed = Signal(str, str, object)
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

    def display_ranges_setup(
        self,
        active_channels: List[dict],
        instrument_model: str,
        ranges_config: Dict[str, dict],
    ) -> None:
        self._ranges_sec.display_ranges(
            active_channels, instrument_model, ranges_config
        )

    def display_config(self, snap: dict) -> None:
        ms = snap.get("measurement_setup", {})
        self._meas_sec.display_state(
            ms.get("integration_mode", "MED"),
            ms.get("short_time", 2e-4),
            ms.get("long_time_cycles", 50),
            ms.get("wait_multiplier", 1.0),
        )
        self._timing_sec.display_state(
            snap.get("delay", 0.0),
            snap.get("hold_time", 0.5),
            snap.get("sweep_stop", "COMPLIANCE"),
        )
        v1 = snap.get("var1", {})
        self._var1_sec.display_state(
            v1.get("mode", "SINGLE"),
            v1.get("spacing", "LINEAR"),
            v1.get("start", 0.0),
            v1.get("stop", 1.0),
            v1.get("step", 0.1),
            v1.get("compliance", 0.01),
            v1.get("power_compliance", 0.01),
            v1.get("power_compliance_enabled", False),
        )
        v2 = snap.get("var2", {})
        self._var2_sec.display_state(
            v2.get("start", 0.0),
            v2.get("step", 0.1),
            v2.get("n_of_steps", 3),
            v2.get("compliance", 0.01),
            v2.get("power_compliance", 0.01),
            v2.get("power_compliance_enabled", False),
        )
        vd = snap.get("vard", {})
        self._vard_sec.display_state(
            vd.get("offset", 0.0),
            vd.get("ratio", 1.0),
            vd.get("compliance", 0.01),
            vd.get("power_compliance", 0.01),
            vd.get("power_compliance_enabled", False),
        )

    def display_var_sections(
        self, has_var1: bool, has_var2: bool, has_vard: bool
    ) -> None:
        self._var1_sec.setVisible(has_var1)
        self._var2_sec.setVisible(has_var2)
        self._vard_sec.setVisible(has_vard)

    def display_var1_context(
        self,
        channel_label: str,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        self._var1_sec.update_ranges(is_voltage, is_vsu, interlock_open)
        self._var1_sec.display_context(channel_label)

    def display_var2_context(
        self,
        channel_label: str,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        self._var2_sec.update_ranges(is_voltage, is_vsu, interlock_open)
        self._var2_sec.display_context(channel_label)

    def display_vard_context(
        self,
        channel_label: str,
        is_voltage: bool,
        is_vsu: bool = False,
        interlock_open: bool = False,
    ) -> None:
        self._vard_sec.update_ranges(is_voltage, is_vsu, interlock_open)
        self._vard_sec.display_context(channel_label)

    def display_available_vars(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        self._display_vars_sec.display_available(var_names, selected)

    def display_validation_status(self, is_valid: bool, message: str) -> None:
        """Update the validation status label in the header."""
        # A fresh validation state supersedes any lingering "Saved" toast.
        self._save_msg_timer.stop()
        self._export_btn.setEnabled(is_valid)
        self._save_btn.setEnabled(is_valid)
        self._save_db_btn.setEnabled(is_valid)
        if is_valid:
            self._validation_lbl.setText(f"✅ {message}")
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("valid")
            )
        else:
            self._validation_lbl.setText(f"⚠️ {message}")
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("warning")
            )

    def display_json(self, json_str: str) -> None:
        dlg = _JsonPreviewDialog(json_str, self)
        dlg.exec()

    def _on_save_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sweep Setup",
            "",
            "Setup files (*.json);;All files (*)",
        )
        if path:
            self.save_requested.emit(path)

    def display_save_success(self, filename: str) -> None:
        """Flash a transient confirmation in the header validation label."""
        self._validation_lbl.setText(f"💾 Saved to {filename}")
        self._validation_lbl.setStyleSheet(validation_status_stylesheet("valid"))
        self._save_msg_timer.start()

    def display_constants_setup(
        self,
        active_channels: List[dict],
        constants_config: Dict[str, dict],
        interlock_open: bool = False,
    ) -> None:
        self._constants_sec.display_constants(
            active_channels, constants_config, interlock_open
        )

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._meas_sec.isVisible():
            errors.update(self._meas_sec.get_input_errors())
        if self._timing_sec.isVisible():
            errors.update(self._timing_sec.get_input_errors())
        if self._constants_sec.isVisible():
            errors.update(self._constants_sec.get_input_errors())
        if self._var1_sec.isVisible():
            errors.update(self._var1_sec.get_input_errors())
        if self._var2_sec.isVisible():
            errors.update(self._var2_sec.get_input_errors())
        if self._vard_sec.isVisible():
            errors.update(self._vard_sec.get_input_errors())
        return errors

    # ── Private — layout ──────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(config_page_stylesheet())

        # Header
        header = QWidget()
        header.setStyleSheet(
            f"background-color: {P.BG_PANEL}; "
            f"border-bottom: 1px solid {P.BORDER};"
        )
        hh = QHBoxLayout(header)
        hh.setContentsMargins(24, 14, 24, 14)
        hh.setSpacing(16)
        title = QLabel("Sweep Configuration")
        title.setStyleSheet(
            f"color: {P.TEXT_PRIMARY}; font-size: 18px; "
            "font-weight: bold; background: transparent;"
        )
        hh.addWidget(title)

        # Validation status label (also hosts the transient "Saved" toast)
        self._validation_lbl = QLabel()
        hh.addWidget(self._validation_lbl)

        self._save_msg_timer = QTimer(self)
        self._save_msg_timer.setSingleShot(True)
        self._save_msg_timer.setInterval(3000)
        self._save_msg_timer.timeout.connect(self.save_message_expired)

        hh.addStretch()
        self._save_db_btn = QPushButton("Save Setup")
        self._save_db_btn.setStyleSheet(export_btn_stylesheet())
        self._save_db_btn.clicked.connect(self.save_to_db_requested)
        hh.addWidget(self._save_db_btn)
        self._save_btn = QPushButton("Save JSON")
        self._save_btn.setStyleSheet(export_btn_stylesheet())
        self._save_btn.clicked.connect(self._on_save_clicked)
        hh.addWidget(self._save_btn)
        self._export_btn = QPushButton("Generate JSON")
        self._export_btn.setStyleSheet(export_btn_stylesheet())
        self._export_btn.clicked.connect(self.export_requested)
        hh.addWidget(self._export_btn)
        root.addWidget(header)

        # Scrollable body
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
        self._meas_sec = _MeasSetupSection()
        self._ranges_sec = _RangesSection()
        self._timing_sec = _SweepTimingSection()
        self._display_vars_sec = _DisplayVarsSection()

        for w in (
            self._summary_sec,
            self._meas_sec,
            self._ranges_sec,
            self._display_vars_sec,
        ):
            left_v.addWidget(w)
        left_v.addStretch()

        # Right column (expanding)
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(12)
        right_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._var1_sec = _VAR1Section()
        self._var2_sec = _VAR2Section()
        self._vard_sec = _VARDSection()
        self._constants_sec = _ConstantsSection()

        for w in (
            self._var1_sec,
            self._var2_sec,
            self._vard_sec,
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

        m = self._meas_sec
        m.integration_mode_changed.connect(self.integration_mode_changed)
        m.short_time_committed.connect(self.short_time_committed)
        m.long_cycles_changed.connect(self.long_cycles_changed)
        m.wait_multiplier_committed.connect(self.wait_multiplier_committed)

        t = self._timing_sec
        t.delay_committed.connect(self.delay_committed)
        t.hold_time_committed.connect(self.hold_time_committed)
        t.sweep_stop_changed.connect(self.sweep_stop_changed)

        v1 = self._var1_sec
        v1.mode_changed.connect(self.var1_mode_changed)
        v1.spacing_changed.connect(self.var1_spacing_changed)
        v1.start_committed.connect(self.var1_start_committed)
        v1.stop_committed.connect(self.var1_stop_committed)
        v1.step_committed.connect(self.var1_step_committed)
        v1.comp_committed.connect(self.var1_comp_committed)
        v1.pcomp_committed.connect(self.var1_pcomp_committed)
        v1.pcomp_enabled_changed.connect(self.var1_pcomp_enabled_changed)

        v2 = self._var2_sec
        v2.start_committed.connect(self.var2_start_committed)
        v2.step_committed.connect(self.var2_step_committed)
        v2.n_of_steps_changed.connect(self.var2_n_of_steps_changed)
        v2.comp_committed.connect(self.var2_comp_committed)
        v2.pcomp_committed.connect(self.var2_pcomp_committed)
        v2.pcomp_enabled_changed.connect(self.var2_pcomp_enabled_changed)

        vd = self._vard_sec
        vd.offset_committed.connect(self.vard_offset_committed)
        vd.ratio_committed.connect(self.vard_ratio_committed)
        vd.comp_committed.connect(self.vard_comp_committed)
        vd.pcomp_committed.connect(self.vard_pcomp_committed)
        vd.pcomp_enabled_changed.connect(self.vard_pcomp_enabled_changed)

        self._display_vars_sec.var_toggled.connect(self.display_var_toggled)
        self._ranges_sec.range_changed.connect(self.range_changed)

        self._constants_sec.const_source_changed.connect(
            self.const_source_changed
        )
        self._constants_sec.const_compliance_changed.connect(
            self.const_compliance_changed
        )
