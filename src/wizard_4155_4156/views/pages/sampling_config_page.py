"""
views/pages/sampling_config_page.py
-----------------------------------
Sampling Configuration page — pure View layer.

Mirrors sweep_config_page.py: SciDoubleEdit widgets handle their own
parsing, bounds context is pushed in by the presenter via display_*
methods, and all mode-dependent enable/disable decisions are made by
the presenter (passive view).
"""

from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.models.sampling_config import (
    EVENT_COUNT_MAX,
    EVENT_COUNT_MIN,
    IINT_MAX,
    IINT_MIN_LINEAR,
    PERIOD_MAX,
    SAMP_HOLD_MAX,
    SAMP_HOLD_MIN_FAST,
    SAMPLES_MAX,
    SAMPLES_MIN,
)
from wizard_4155_4156.styles.stylesheets import (
    config_page_stylesheet,
    unit_card_combo_stylesheet,
    unit_enable_checkbox_stylesheet,
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
from wizard_4155_4156.views.widgets.measurement_status import MeasurementTopBar

# Display label ↔ SCPI value mappings (view-local presentation aliases)

_SAMPLING_MODE_DISPLAY_TO_SCPI = {
    "LINEAR": "LINEAR",
    "LOG10": "L10",
    "LOG25": "L25",
    "LOG50": "L50",
    "THIN": "THINNEDOUT",
}
_SAMPLING_MODE_SCPI_TO_DISPLAY = {
    v: k for k, v in _SAMPLING_MODE_DISPLAY_TO_SCPI.items()
}

_PERIOD_MODE_DISPLAY = {
    "AUTO": "AUTO",
    "NO_LIMIT": "NO LIMIT",
    "NUMERIC": "Value",
}

_SCON_EVENT_DISPLAY_TO_SCPI = {
    "Val > Th": "HIGH",
    "Val < Th": "LOW",
    "|Val| > |Th|": "ABSHIGH",
    "|Val| < |Th|": "ABSLOW",
}


class _SamplingSetupSection(_SectionFrame):
    """MODE / INITIAL INTERVAL / NO. OF SAMPLES / TOTAL SAMP. TIME /
    HOLD TIME / FILTER."""

    mode_changed = Signal(str)  # SCPI value
    initial_interval_committed = Signal(float)
    points_changed = Signal(int)
    period_mode_changed = Signal(str)  # AUTO | NO_LIMIT | NUMERIC
    period_committed = Signal(float)
    hold_time_committed = Signal(float)
    filter_changed = Signal(str)  # ON | OFF

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Sampling Parameters",
            parent,
            accent=P.STATUS_INFO,
            doc_topic=DocTopic.SAMPLING_PARAMETERS,
        )

        self._mode_seg = _SegmentedGroup(
            list(_SAMPLING_MODE_DISPLAY_TO_SCPI.keys()), "LINEAR"
        )
        self.body().addWidget(_form_row("Mode", self._mode_seg))

        self._iint_edit = _SciDoubleEdit(
            2e-3, IINT_MIN_LINEAR, IINT_MAX, "s"
        )
        self.body().addWidget(
            _form_row("Initial Interval", self._iint_edit)
        )

        self._points_sb = _spinbox(SAMPLES_MIN, SAMPLES_MAX, 11)
        self.body().addWidget(_form_row("Number of Samples", self._points_sb))

        # Total Sampling Time: mode combo + numeric value
        period_w = QWidget()
        ph = QHBoxLayout(period_w)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.setSpacing(8)
        self._period_combo = QComboBox()
        self._period_combo.setStyleSheet(unit_card_combo_stylesheet())
        self._period_combo.setFixedWidth(110)
        ph.addWidget(self._period_combo)
        self._period_edit = _SciDoubleEdit(1.0, 0.0, PERIOD_MAX, "s")
        ph.addWidget(self._period_edit, stretch=1)
        self._period_row = _form_row("Total Sampling Time", period_w)
        self.body().addWidget(self._period_row)

        self._hold_edit = _SciDoubleEdit(
            0.0, SAMP_HOLD_MIN_FAST, SAMP_HOLD_MAX, "s"
        )
        self.body().addWidget(_form_row("Hold Time", self._hold_edit))

        self._filter_seg = _SegmentedGroup(["ON", "OFF"], "ON")
        self.body().addWidget(_form_row("Filter", self._filter_seg))

        # Wiring
        self._mode_seg.selection_changed.connect(self._on_mode_clicked)
        self._iint_edit.value_committed.connect(
            self.initial_interval_committed
        )
        self._points_sb.valueChanged.connect(self.points_changed)
        self._period_combo.currentIndexChanged.connect(
            self._on_period_combo_changed
        )
        self._period_edit.value_committed.connect(self.period_committed)
        self._hold_edit.value_committed.connect(self.hold_time_committed)
        self._filter_seg.selection_changed.connect(self.filter_changed)

    # ── Internal relays ──────────────────────────────────────────────────

    def _on_mode_clicked(self, display: str) -> None:
        self.mode_changed.emit(
            _SAMPLING_MODE_DISPLAY_TO_SCPI.get(display, "LINEAR")
        )

    def _on_period_combo_changed(self, idx: int) -> None:
        data = self._period_combo.itemData(idx)
        if data is not None:
            self._period_edit.setEnabled(data == "NUMERIC")
            self.period_mode_changed.emit(data)

    # ── Display API (presenter → view) ───────────────────────────────────

    def display_state(self, snap: dict) -> None:
        self._mode_seg.set_value(
            _SAMPLING_MODE_SCPI_TO_DISPLAY.get(snap.get("mode"), "LINEAR")
        )
        self._iint_edit.set_value(snap.get("initial_interval", 2e-3))
        self._points_sb.blockSignals(True)
        self._points_sb.setValue(snap.get("points", 11))
        self._points_sb.blockSignals(False)
        self._period_edit.set_value(snap.get("period", 1.0))
        self._hold_edit.set_value(snap.get("hold_time", 0.0))
        self._filter_seg.set_value(
            "ON" if snap.get("filter_on", True) else "OFF"
        )

    def display_period_options(self, allowed: List[str], current: str) -> None:
        """Empty `allowed` hides the row (LOG modes)."""
        self._period_row.setVisible(bool(allowed))
        if not allowed:
            return
        self._period_combo.blockSignals(True)
        self._period_combo.clear()
        for mode in allowed:
            self._period_combo.addItem(
                _PERIOD_MODE_DISPLAY.get(mode, mode), mode
            )
        idx = self._period_combo.findData(current)
        self._period_combo.setCurrentIndex(max(idx, 0))
        self._period_combo.blockSignals(False)
        self._period_edit.setEnabled(current == "NUMERIC")

    def display_iint_bounds(self, min_v: float, max_v: float) -> None:
        self._iint_edit.update_bounds(min_v, max_v)
        self._iint_edit._edit.setToolTip(
            f"Range: {min_v:.3g} – {max_v:.3g} s"
        )

    def display_points_bounds(self, max_points: int) -> None:
        # The spinbox keeps its static maximum (SAMPLES_MAX); the mode/unit-
        # dependent limit is enforced by the model validator, not by clamping
        # the widget.  Clamping while signals are blocked silently desynced the
        # widget value from the model when a newly displayed variable lowered
        # the limit below the stored value.
        self._points_sb.setToolTip(f"Range: {SAMPLES_MIN} – {max_points}")

    def display_hold_bounds(self, min_v: float, max_v: float) -> None:
        self._hold_edit.update_bounds(min_v, max_v)
        self._hold_edit._edit.setToolTip(
            f"Range: {min_v:.3g} – {max_v:.3g} s (100 µs resolution)"
        )

    def display_period_bounds(self, min_v: float, max_v: float) -> None:
        self._period_edit.update_bounds(min_v, max_v)
        self._period_edit._edit.setToolTip(
            f"Range: {min_v:.3g} – {max_v:.3g} s"
        )

    def get_input_errors(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        if self._iint_edit.get_value() is None:
            errors["initial_interval"] = (
                "Initial Interval: value is empty or invalid"
            )
        if self._hold_edit.get_value() is None:
            errors["hold_time"] = "Hold Time: value is empty or invalid"
        if (
            self._period_row.isVisible()
            and self._period_combo.currentData() == "NUMERIC"
            and self._period_edit.get_value() is None
        ):
            errors["period"] = (
                "Total Samp. Time: value is empty or invalid"
            )
        return errors


class _StopConditionSection(_SectionFrame):
    """ENABLE / NAME / EVENT / THRESHOLD / EVENT NO. / ENABLE DELAY."""

    enabled_changed = Signal(bool)
    name_changed = Signal(str)
    event_changed = Signal(str)  # SCPI value
    threshold_committed = Signal(float)
    event_count_changed = Signal(int)
    enable_delay_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Stop Condition",
            parent,
            accent=P.STATUS_CAUTION,
            doc_topic=DocTopic.STOP_CONDITION,
        )
        self._allowed = True

        self._enable_cb = QCheckBox("Enable stop condition")
        self._enable_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enable_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self.body().addWidget(self._enable_cb)

        self._hint_lbl = QLabel(
            "Requires Initial Interval ≥ 2 ms."
        )
        self._hint_lbl.setStyleSheet(
            f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._hint_lbl)

        self._name_combo = QComboBox()
        self._name_combo.setStyleSheet(unit_card_combo_stylesheet())
        self.body().addWidget(_form_row(
            "Variable Name (Val)",
            self._name_combo
        ))

        self._event_combo = QComboBox()
        self._event_combo.setStyleSheet(unit_card_combo_stylesheet())
        for label, scpi in _SCON_EVENT_DISPLAY_TO_SCPI.items():
            self._event_combo.addItem(label, scpi)
        self.body().addWidget(_form_row("Event", self._event_combo))

        self._threshold_edit = _SciDoubleEdit(0.0, -1e30, 1e30, "")
        self.body().addWidget(
            _form_row("Threshold (Th)", self._threshold_edit)
        )

        self._count_sb = _spinbox(EVENT_COUNT_MIN, EVENT_COUNT_MAX, 1)
        self._count_sb.setToolTip(
            f"Range: {EVENT_COUNT_MIN} – {EVENT_COUNT_MAX}"
        )
        self.body().addWidget(_form_row(
            "Maximum Number of Events",
            self._count_sb
        ))

        self._delay_edit = _SciDoubleEdit(0.0, 0.0, 1e30, "s")
        self.body().addWidget(
            _form_row("Enable Delay", self._delay_edit)
        )

        self._inner_widgets = (
            self._name_combo,
            self._event_combo,
            self._threshold_edit,
            self._count_sb,
            self._delay_edit,
        )

        self._enable_cb.toggled.connect(self._on_enable_toggled)
        self._name_combo.currentTextChanged.connect(self.name_changed)
        self._event_combo.currentIndexChanged.connect(
            self._on_event_changed
        )
        self._threshold_edit.value_committed.connect(
            self.threshold_committed
        )
        self._count_sb.valueChanged.connect(self.event_count_changed)
        self._delay_edit.value_committed.connect(
            self.enable_delay_committed
        )

        self._refresh_enabled_state()

    # ── Internal relays ──────────────────────────────────────────────────

    def _on_enable_toggled(self, checked: bool) -> None:
        self._refresh_enabled_state()
        self.enabled_changed.emit(checked)

    def _on_event_changed(self, idx: int) -> None:
        data = self._event_combo.itemData(idx)
        if data is not None:
            self.event_changed.emit(data)

    def _refresh_enabled_state(self) -> None:
        inner_on = self._allowed and self._enable_cb.isChecked()
        for w in self._inner_widgets:
            w.setEnabled(inner_on)
        self._enable_cb.setEnabled(self._allowed)

    # ── Display API (presenter → view) ───────────────────────────────────

    def display_state(self, snap: dict) -> None:
        self._enable_cb.blockSignals(True)
        self._enable_cb.setChecked(snap.get("enabled", False))
        self._enable_cb.blockSignals(False)
        idx = self._event_combo.findData(snap.get("event", "HIGH"))
        self._event_combo.blockSignals(True)
        self._event_combo.setCurrentIndex(max(idx, 0))
        self._event_combo.blockSignals(False)
        self._threshold_edit.set_value(snap.get("threshold", 0.0))
        self._count_sb.blockSignals(True)
        self._count_sb.setValue(snap.get("event_count", 1))
        self._count_sb.blockSignals(False)
        self._delay_edit.set_value(snap.get("enable_delay", 0.0))
        self._refresh_enabled_state()

    def display_variables(self, var_names: List[str], current: str) -> None:
        self._name_combo.blockSignals(True)
        self._name_combo.clear()
        self._name_combo.addItems(var_names)
        idx = self._name_combo.findText(current)
        self._name_combo.setCurrentIndex(max(idx, 0))
        self._name_combo.blockSignals(False)

    def display_allowed(self, allowed: bool) -> None:
        self._allowed = allowed
        self._hint_lbl.setVisible(not allowed)
        self._refresh_enabled_state()

    def display_delay_bounds(self, min_v: float, max_v: float) -> None:
        self._delay_edit.update_bounds(min_v, max_v)
        self._delay_edit._edit.setToolTip(
            f"Range: {min_v:.3g} – {max_v:.3g} s "
            "(resolution: Initial Interval)"
        )

    def is_enabled_checked(self) -> bool:
        return self._enable_cb.isChecked()

    def get_input_errors(self) -> Dict[str, str]:
        if not (self._allowed and self._enable_cb.isChecked()):
            return {}
        errors: Dict[str, str] = {}
        if self._threshold_edit.get_value() is None:
            errors["scon_threshold"] = (
                "Stop Condition Threshold: value is empty or invalid"
            )
        if self._delay_edit.get_value() is None:
            errors["scon_delay"] = (
                "Stop Condition Enable Delay: value is empty or invalid"
            )
        return errors


# ── Main page view ───────────────────────────────────────────────────────────


class SamplingConfigPageView(BasePage):
    """
    Sampling Configuration page.

    Built lazily by MeasureConfigFactory from a static channels snapshot;
    on_activate() → page_activated → presenter re-pushes its state.
    """

    page_activated = Signal()

    # Measurement setup (relayed from shared sections)
    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_multiplier_committed = Signal(float)
    range_changed = Signal(str, str, object)
    smu_standby_changed = Signal(str, bool)
    display_var_toggled = Signal(str, bool)

    # Sampling parameters
    sampling_mode_changed = Signal(str)
    initial_interval_committed = Signal(float)
    points_changed = Signal(int)
    period_mode_changed = Signal(str)
    period_committed = Signal(float)
    hold_time_committed = Signal(float)
    filter_changed = Signal(str)

    # Stop condition
    scon_enabled_changed = Signal(bool)
    scon_name_changed = Signal(str)
    scon_event_changed = Signal(str)
    scon_threshold_committed = Signal(float)
    scon_event_count_changed = Signal(int)
    scon_enable_delay_committed = Signal(float)

    # Constants / export / save
    const_source_changed = Signal(str, float)
    const_compliance_changed = Signal(str, float)
    export_requested = Signal()
    save_requested = Signal(str)  # chosen file path (Save JSON)
    save_to_db_requested = Signal()  # save setup into the project database
    save_message_expired = Signal()
    documentation_requested = Signal(str)  # DocTopic value (section doc icon)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._wire_sections()
        for section in self.findChildren(_SectionFrame):
            section.doc_requested.connect(self.documentation_requested)

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API ───────────────────────────────────────────────────────

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
        self._sampling_sec.display_state(snap)
        self._scon_sec.display_state(snap.get("stop_condition", {}))

    def display_available_vars(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        self._display_vars_sec.display_available(var_names, selected)

    def display_scon_variables(
        self, var_names: List[str], current: str
    ) -> None:
        self._scon_sec.display_variables(var_names, current)

    def display_scon_allowed(self, allowed: bool) -> None:
        self._scon_sec.display_allowed(allowed)

    def display_scon_delay_bounds(self, min_v: float, max_v: float) -> None:
        self._scon_sec.display_delay_bounds(min_v, max_v)

    def display_period_options(
        self, allowed: List[str], current: str
    ) -> None:
        self._sampling_sec.display_period_options(allowed, current)

    def display_period_bounds(self, min_v: float, max_v: float) -> None:
        self._sampling_sec.display_period_bounds(min_v, max_v)

    def display_iint_bounds(self, min_v: float, max_v: float) -> None:
        self._sampling_sec.display_iint_bounds(min_v, max_v)

    def display_points_bounds(self, max_points: int) -> None:
        self._sampling_sec.display_points_bounds(max_points)

    def display_hold_bounds(self, min_v: float, max_v: float) -> None:
        self._sampling_sec.display_hold_bounds(min_v, max_v)

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
        min_time: str,
    ) -> None:
        """Push the setup's critical/warning/info state to the top bar."""
        self._top_bar.display_status(
            criticals, warnings, indexes, points, min_time
        )

    def display_json(self, json_str: str) -> None:
        dlg = _JsonPreviewDialog(
            json_str,
            self,
            title="Generated JSON — Sampling Configuration",
        )
        dlg.exec()

    def display_save_success(self, filename: str) -> None:
        self._top_bar.flash_saved(filename)

    def get_input_errors(self) -> Dict[str, str]:
        errors: Dict[str, str] = {}
        errors.update(self._meas_sec.get_input_errors())
        errors.update(self._sampling_sec.get_input_errors())
        errors.update(self._scon_sec.get_input_errors())
        errors.update(self._constants_sec.get_input_errors())
        return errors

    # ── Private — layout ──────────────────────────────────────────────────

    def _on_save_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sampling Setup",
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
            tr_ui(CommandWizardText.CFG_MODE_SAMPLING),
            DocTopic.SAMPLING_OVERVIEW,
        )
        self._top_bar.save_setup_requested.connect(self.save_to_db_requested)
        self._top_bar.save_json_requested.connect(self._on_save_clicked)
        self._top_bar.export_requested.connect(self.export_requested)
        self._top_bar.documentation_requested.connect(
            self.documentation_requested
        )
        root.addWidget(self._top_bar)

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

        # Left column (fixed 425 px — reused sections)
        left = QWidget()
        left.setFixedWidth(425)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(20)
        left_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._summary_sec = _ChannelSummarySection()
        self._meas_sec = _MeasSetupSection()
        self._ranges_sec = _RangesSection()
        self._display_vars_sec = _DisplayVarsSection()

        for w in (
            self._summary_sec,
            self._meas_sec,
            self._ranges_sec,
            self._display_vars_sec,
        ):
            left_v.addWidget(w)
        left_v.addStretch()

        # Right column (expanding — sampling-specific sections)
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(12)
        right_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._sampling_sec = _SamplingSetupSection()
        self._scon_sec = _StopConditionSection()
        self._constants_sec = _ConstantsSection()

        for w in (
            self._sampling_sec,
            self._scon_sec,
            self._constants_sec,
        ):
            right_v.addWidget(w)
        right_v.addStretch()

        body_h.addWidget(left)
        body_h.addWidget(right, stretch=1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _wire_sections(self) -> None:
        self._summary_sec.smu_standby_changed.connect(
            self.smu_standby_changed
        )

        m = self._meas_sec
        m.integration_mode_changed.connect(self.integration_mode_changed)
        m.short_time_committed.connect(self.short_time_committed)
        m.long_cycles_changed.connect(self.long_cycles_changed)
        m.wait_multiplier_committed.connect(self.wait_multiplier_committed)

        s = self._sampling_sec
        s.mode_changed.connect(self.sampling_mode_changed)
        s.initial_interval_committed.connect(
            self.initial_interval_committed
        )
        s.points_changed.connect(self.points_changed)
        s.period_mode_changed.connect(self.period_mode_changed)
        s.period_committed.connect(self.period_committed)
        s.hold_time_committed.connect(self.hold_time_committed)
        s.filter_changed.connect(self.filter_changed)

        sc = self._scon_sec
        sc.enabled_changed.connect(self.scon_enabled_changed)
        sc.name_changed.connect(self.scon_name_changed)
        sc.event_changed.connect(self.scon_event_changed)
        sc.threshold_committed.connect(self.scon_threshold_committed)
        sc.event_count_changed.connect(self.scon_event_count_changed)
        sc.enable_delay_committed.connect(
            self.scon_enable_delay_committed
        )

        self._display_vars_sec.var_toggled.connect(self.display_var_toggled)
        self._ranges_sec.range_changed.connect(self.range_changed)
        self._constants_sec.const_source_changed.connect(
            self.const_source_changed
        )
        self._constants_sec.const_compliance_changed.connect(
            self.const_compliance_changed
        )
