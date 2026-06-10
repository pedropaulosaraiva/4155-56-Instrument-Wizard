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

import json
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.models.sweep_config import (
    COMP_I_MAX,
    COMP_I_MIN,
    COMP_V_MAX,
    COMP_V_MIN,
    CURRENT_MAX,
    CURRENT_MIN,
    CURRENT_STEP_MAX,
    CURRENT_STEP_MIN,
    DELAY_MAX,
    DELAY_MIN,
    HOLD_TIME_MAX,
    HOLD_TIME_MIN,
    LONG_CYCLES_MAX,
    LONG_CYCLES_MIN,
    PCOMP_MAX,
    PCOMP_MIN,
    RATIO_MAX,
    RATIO_MIN,
    SHORT_TIME_MAX,
    SHORT_TIME_MIN,
    TOTAL_POINTS_MAX,
    VAR1_POINTS_MAX,
    VAR1_POINTS_MIN,
    VAR2_POINTS_MAX,
    VAR2_POINTS_MIN,
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
    VSU_VOLTAGE_MAX,
    VSU_VOLTAGE_MIN,
    WAIT_MULT_MAX,
    WAIT_MULT_MIN,
    SweepConstraints,
    RANGE_VALUES_MPSMU_CURRENT,
    RANGE_VALUES_HRSMU_CURRENT,
    RANGE_VALUES_SMU_VOLTAGE,
    RANGE_VALUES_VMU_V,
    RANGE_VALUES_VMU_DVOL,
)
from wizard_4155_4156.styles.stylesheets import (
    channel_row_badge_stylesheet,
    error_bar_stylesheet,
    export_btn_stylesheet,
    input_error_stylesheet,
    segmented_btn_checked_stylesheet,
    segmented_btn_unchecked_stylesheet,
    sweep_form_label_stylesheet,
    sweep_page_stylesheet,
    sweep_section_card_stylesheet,
    sweep_spinbox_stylesheet,
    sweep_unit_label_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
    unit_enable_checkbox_stylesheet,
    unit_group_header_stylesheet,
    unit_group_separator_stylesheet,
    validation_status_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage


# ── Shared helpers ────────────────────────────────────────────────────────────


def _form_row(
    label_text: str, widget: QWidget, label_width: int = 160
) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(label_width)
    lbl.setStyleSheet(sweep_form_label_stylesheet())
    lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    h.addWidget(lbl)
    h.addWidget(widget, stretch=1)
    return row


def _combo(options: List[str], default: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setStyleSheet(unit_card_combo_stylesheet())
    for opt in options:
        cb.addItem(opt, opt)
    idx = cb.findData(default)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    return cb


def _spinbox(lo: int, hi: int, default: int) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(default)
    sb.setStyleSheet(sweep_spinbox_stylesheet())
    return sb


def _matrix_label_style(ok: bool) -> str:
    color = P.STATUS_OK if ok else P.STATUS_ERROR
    return (
        f"color: {color}; font-size: {P.FONT_SIZE_SM}; font-weight: bold; "
        f"background: transparent; padding: 6px 10px; "
        f"border: 1px solid {color}; border-radius: {P.RADIUS_SM};"
    )


def _create_table_header(
    columns: List[Tuple[str, int]], spacing: int = 10
) -> QWidget:
    hdr = QWidget()
    hh = QHBoxLayout(hdr)
    hh.setContentsMargins(0, 0, 0, 4)
    hh.setSpacing(spacing)
    for text, w in columns:
        l = QLabel(text)
        l.setStyleSheet(
            f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
            "font-weight: bold; letter-spacing: 1px; background: transparent;"
        )
        l.setFixedWidth(w)
        l.setAlignment(
            Qt.AlignmentFlag.AlignCenter
            if text in ("Unit", "Channel")
            else Qt.AlignmentFlag.AlignLeft
        )
        hh.addWidget(l)
    hh.addStretch()
    return hdr


def _create_horizontal_divider() -> QFrame:
    div = QFrame()
    div.setFrameShape(QFrame.Shape.HLine)
    div.setStyleSheet(f"background-color: {P.BORDER}; max-height: 1px;")
    return div


class SciDoubleValidator(QValidator):
    def __init__(self, min_val: float, max_val: float, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_str: str, pos: int):
        val_str = input_str.replace(",", ".").strip()
        if not val_str:
            return QValidator.State.Intermediate, input_str, pos

        # Allow sign prefix
        if val_str in ("-", "+", "-.", "+."):
            return QValidator.State.Intermediate, input_str, pos

        # Check scientific notation intermediate states
        lower_str = val_str.lower()
        if "e" in lower_str:
            parts = lower_str.split("e")
            if len(parts) > 2:
                return QValidator.State.Invalid, input_str, pos
            mantissa, exponent = parts[0], parts[1]
            if mantissa in ("", "-", "+", "-.", "+."):
                pass
            else:
                try:
                    float(mantissa)
                except ValueError:
                    return QValidator.State.Invalid, input_str, pos
            if exponent in ("", "-", "+"):
                return QValidator.State.Intermediate, input_str, pos
            else:
                try:
                    int(exponent)
                except ValueError:
                    return QValidator.State.Invalid, input_str, pos
        else:
            try:
                float(val_str)
            except ValueError:
                if val_str in (".", "0.", "-0.", "+0."):
                    return QValidator.State.Intermediate, input_str, pos
                return QValidator.State.Invalid, input_str, pos

        try:
            val = float(val_str)
            if self.min_val <= val <= self.max_val:
                return QValidator.State.Acceptable, input_str, pos
            else:
                return QValidator.State.Intermediate, input_str, pos
        except ValueError:
            return QValidator.State.Invalid, input_str, pos


class _SciDoubleEdit(QWidget):
    """
    QLineEdit with scientific-notation support. Emits value_committed(float)
    whenever a valid float is parsed upon editingFinished.
    """

    value_committed = Signal(float)

    def __init__(
        self,
        default: float,
        min_v: float,
        max_v: float,
        unit: str = "",
        disallow_zero: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min = min_v
        self._max = max_v
        self._disallow_zero = disallow_zero

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setStyleSheet(unit_card_line_edit_stylesheet())

        # Use SciDoubleValidator with wide bounds to accept all float values
        self._validator = SciDoubleValidator(-1e300, 1e300, self._edit)
        self._edit.setValidator(self._validator)

        self._set_text(default)
        h.addWidget(self._edit, stretch=1)

        if unit:
            self._unit_lbl = QLabel(unit)
            self._unit_lbl.setStyleSheet(sweep_unit_label_stylesheet())
            self._unit_lbl.setFixedWidth(32)
            h.addWidget(self._unit_lbl)
        else:
            self._unit_lbl = None

        self._edit.editingFinished.connect(self._on_finish)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_value(self, val: float) -> None:
        self._edit.blockSignals(True)
        self._set_text(val)
        self._edit.blockSignals(False)

    def get_value(self) -> Optional[float]:
        """Returns the float if it can be parsed, else None."""
        try:
            text = self._edit.text().replace(",", ".").strip()
            if not text:
                return None
            return float(text)
        except ValueError:
            return None

    def update_bounds(
        self, min_v: float, max_v: float, unit: str = ""
    ) -> None:
        """Dynamically update bounds context when sweep type changes."""
        self._min = min_v
        self._max = max_v
        if unit and self._unit_lbl:
            self._unit_lbl.setText(unit)

    def set_error(self, msg: str = "") -> None:
        pass

    def clear_error(self) -> None:
        pass

    def validate_value(self) -> bool:
        """Always returns True if a float can be parsed."""
        return self.get_value() is not None

    # ── Private ───────────────────────────────────────────────────────────────

    def _set_text(self, val: float) -> None:
        if val != 0 and (abs(val) < 0.01 or abs(val) >= 1e5):
            self._edit.setText(f"{val:.3e}")
        else:
            self._edit.setText(f"{val:.6g}")

    def _on_finish(self) -> None:
        v = self.get_value()
        if v is not None:
            self.value_committed.emit(v)


# ── _SegmentedGroup ────────────────────────────────────────────────────────────


class _SegmentedGroup(QWidget):
    selection_changed = Signal(str)

    def __init__(
        self,
        options: List[str],
        default: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: Dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        for opt in options:
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            btn.setFixedHeight(28)
            self._buttons[opt] = btn
            self._group.addButton(btn)
            h.addWidget(btn)

        selected = default if default in self._buttons else options[0]
        self._buttons[selected].setChecked(True)
        self._refresh_styles()
        self._group.buttonClicked.connect(self._on_clicked)

    def set_value(self, value: str) -> None:
        if value in self._buttons:
            self._group.blockSignals(True)
            self._buttons[value].setChecked(True)
            self._group.blockSignals(False)
            self._refresh_styles()

    def current_value(self) -> str:
        for name, btn in self._buttons.items():
            if btn.isChecked():
                return name
        return ""

    def _on_clicked(self, btn: QPushButton) -> None:
        self._refresh_styles()
        for name, b in self._buttons.items():
            if b is btn:
                self.selection_changed.emit(name)
                return

    def _refresh_styles(self) -> None:
        for btn in self._buttons.values():
            btn.setStyleSheet(
                segmented_btn_checked_stylesheet()
                if btn.isChecked()
                else segmented_btn_unchecked_stylesheet()
            )


# ── _SectionFrame ─────────────────────────────────────────────────────────────


class _SectionFrame(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header_row = QWidget()
        hr = QHBoxLayout(header_row)
        hr.setContentsMargins(0, 0, 0, 0)
        hr.setSpacing(12)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(unit_group_header_stylesheet())
        hr.addWidget(lbl)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(unit_group_separator_stylesheet())
        hr.addWidget(sep, stretch=1)
        root.addWidget(header_row)

        self._card = QFrame()
        self._card.setObjectName("section_card")
        self._card.setStyleSheet(sweep_section_card_stylesheet())
        self._body = QVBoxLayout(self._card)
        self._body.setContentsMargins(16, 14, 16, 14)
        self._body.setSpacing(10)
        root.addWidget(self._card)

    def body(self) -> QVBoxLayout:
        return self._body


# ── Section widgets ───────────────────────────────────────────────────────────


class _ChannelSummarySection(_SectionFrame):
    smu_standby_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Channel Assignments", parent)
        self._standby_cbs: Dict[str, QCheckBox] = {}

    def display_channels(self, active_channels: List[dict]) -> None:
        while self.body().count():
            item = self.body().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._standby_cbs.clear()

        if not active_channels:
            lbl = QLabel(
                "No channels enabled — configure the Channels page first."
            )
            lbl.setStyleSheet(
                f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
                "font-style: italic; background: transparent;"
            )
            self.body().addWidget(lbl)
            return

        # Column headers
        hdr = _create_table_header(
            [
                ("Channel", 65),
                ("Function", 70),
                ("Mode", 75),
                ("V-Name", 55),
                ("I-Name", 55),
                ("Standby", 55),
            ],
            spacing=0,
        )
        self.body().addWidget(hdr)
        self.body().addWidget(_create_horizontal_divider())

        fn_colors = {
            "VAR1": P.STATUS_OK,
            "VAR2": P.STATUS_WARN,
            "VAR1'": "#c586c0",
            "CONST": P.TEXT_MUTED,
            "COMM": P.TEXT_DISABLED,
            "MONITOR": P.TEXT_DISABLED,
        }

        for ch in active_channels:
            ch_id = ch["id"]
            is_smu = ch.get("unit_type") == "SMU"
            fn = ch.get("function", "CONST")
            mode = ch.get("mode", "")

            # Apply display aliases
            fn_display = "MONIT" if fn == "MONITOR" else fn

            mode_display = mode
            if mode == "VPULSE":
                mode_display = "VPUL"
            elif mode == "IPULSE":
                mode_display = "IPUL"

            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 2, 0, 2)
            rh.setSpacing(0)

            # 1. Channel (Unity Name) column: container of width 65, badge of width 48
            ch_container = QWidget()
            ch_container.setFixedWidth(65)
            ch_layout = QHBoxLayout(ch_container)
            ch_layout.setContentsMargins(0, 0, 0, 0)
            ch_layout.setSpacing(0)

            ch_lbl = QLabel(ch_id)
            ch_lbl.setFixedWidth(48)
            ch_lbl.setStyleSheet(channel_row_badge_stylesheet(P.ACCENT_HOVER))
            ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            ch_layout.addStretch()
            ch_layout.addWidget(ch_lbl)
            ch_layout.addStretch()
            rh.addWidget(ch_container)

            # 2. Function column: container of width 70, badge of width 60
            fn_container = QWidget()
            fn_container.setFixedWidth(70)
            fn_layout = QHBoxLayout(fn_container)
            fn_layout.setContentsMargins(0, 0, 0, 0)
            fn_layout.setSpacing(0)

            fn_lbl = QLabel(fn_display)
            fn_lbl.setFixedWidth(60)
            fn_lbl.setStyleSheet(
                channel_row_badge_stylesheet(fn_colors.get(fn, P.TEXT_MUTED))
            )
            fn_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            fn_layout.addStretch()
            fn_layout.addWidget(fn_lbl)
            fn_layout.addStretch()
            rh.addWidget(fn_container)

            # 3. Mode column: container of width 75, badge of width 65
            mode_container = QWidget()
            mode_container.setFixedWidth(75)
            mode_layout = QHBoxLayout(mode_container)
            mode_layout.setContentsMargins(0, 0, 0, 0)
            mode_layout.setSpacing(0)

            mode_lbl = QLabel(mode_display)
            mode_lbl.setFixedWidth(65)
            mode_lbl.setStyleSheet(
                channel_row_badge_stylesheet(fn_colors.get(fn, P.TEXT_MUTED))
            )
            mode_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            mode_layout.addStretch()
            mode_layout.addWidget(mode_lbl)
            mode_layout.addStretch()
            rh.addWidget(mode_container)

            # 4. V-Name column: label of width 55
            v_name_lbl = QLabel(ch.get("v_name", ""))
            v_name_lbl.setFixedWidth(55)
            v_name_lbl.setStyleSheet(
                f"color:{P.TEXT_SECONDARY};font-size:{P.FONT_SIZE_SM};"
                f"font-family:{P.FONT_FAMILY_MONO};background:transparent;"
            )
            v_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rh.addWidget(v_name_lbl)

            # 5. I-Name column: label of width 55
            i_name_lbl = QLabel(ch.get("i_name", "") if is_smu else "—")
            i_name_lbl.setFixedWidth(55)
            i_name_lbl.setStyleSheet(
                f"color:{P.TEXT_SECONDARY};font-size:{P.FONT_SIZE_SM};"
                f"font-family:{P.FONT_FAMILY_MONO};background:transparent;"
            )
            i_name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rh.addWidget(i_name_lbl)

            # 6. Standby column: container of width 55, checkbox/spacer inside
            if is_smu:
                cb_container = QWidget()
                cb_container.setFixedWidth(55)
                cb_layout = QHBoxLayout(cb_container)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.setSpacing(0)

                cb = QCheckBox()
                cb.setChecked(ch.get("standby", False))
                cb.setCursor(Qt.CursorShape.PointingHandCursor)
                cb.setStyleSheet(unit_enable_checkbox_stylesheet())
                cb.setFixedWidth(16)

                cb_layout.addStretch()
                cb_layout.addWidget(cb)
                cb_layout.addStretch()

                cb.toggled.connect(
                    lambda checked, cid=ch_id: self.smu_standby_changed.emit(
                        cid, checked
                    )
                )
                self._standby_cbs[ch_id] = cb
                rh.addWidget(cb_container)
            else:
                spacer_container = QWidget()
                spacer_container.setFixedWidth(55)
                sc_layout = QHBoxLayout(spacer_container)
                sc_layout.setContentsMargins(0, 0, 0, 0)
                sc_layout.setSpacing(0)

                spacer = QLabel("—")
                spacer.setStyleSheet(sweep_form_label_stylesheet())
                spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)

                sc_layout.addWidget(spacer)
                rh.addWidget(spacer_container)

            rh.addStretch()
            self.body().addWidget(row)

    def set_standby(self, ch_id: str, on: bool) -> None:
        if ch_id in self._standby_cbs:
            self._standby_cbs[ch_id].blockSignals(True)
            self._standby_cbs[ch_id].setChecked(on)
            self._standby_cbs[ch_id].blockSignals(False)


class _MeasSetupSection(_SectionFrame):
    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_multiplier_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Measurement Setup", parent)
        self._setup_widgets()

    def _setup_widgets(self) -> None:
        self._mode_seg = _SegmentedGroup(["SHORT", "MED", "LONG"], "MED")
        self.body().addWidget(_form_row("Integration Mode", self._mode_seg))

        self._short_edit = _SciDoubleEdit(
            2e-4, SHORT_TIME_MIN, SHORT_TIME_MAX, "s"
        )
        self._short_edit._edit.setToolTip(
            f"Range: {SHORT_TIME_MIN:.0e} – {SHORT_TIME_MAX:.2e} s"
        )
        self._short_row = _form_row("Short Aperture", self._short_edit)
        self._short_row.setVisible(False)
        self.body().addWidget(self._short_row)

        self._long_sb = _spinbox(LONG_CYCLES_MIN, LONG_CYCLES_MAX, 50)
        self._long_sb.setToolTip(
            f"Range: {LONG_CYCLES_MIN} – {LONG_CYCLES_MAX} PLC"
        )
        self._long_row = _form_row("Integration Cycles", self._long_sb)
        self._long_row.setVisible(False)
        self.body().addWidget(self._long_row)

        self._wait_edit = _SciDoubleEdit(
            1.0, WAIT_MULT_MIN, WAIT_MULT_MAX, "×"
        )
        self._wait_edit._edit.setToolTip(
            "Dimensionless wait-time multiplier (0.0 – 10.0)"
        )
        self.body().addWidget(_form_row("Wait Multiplier", self._wait_edit))

        self._mode_seg.selection_changed.connect(self._on_mode)
        self._mode_seg.selection_changed.connect(self.integration_mode_changed)
        self._short_edit.value_committed.connect(self.short_time_committed)
        self._long_sb.valueChanged.connect(self.long_cycles_changed)
        self._wait_edit.value_committed.connect(self.wait_multiplier_committed)

    def display_state(
        self, mode: str, short_time: float, long_cycles: int, wait_mult: float
    ) -> None:
        self._mode_seg.set_value(mode)
        self._short_edit.set_value(short_time)
        self._long_sb.blockSignals(True)
        self._long_sb.setValue(long_cycles)
        self._long_sb.blockSignals(False)
        self._wait_edit.set_value(wait_mult)
        self._on_mode(mode)

    def _on_mode(self, mode: str) -> None:
        self._short_row.setVisible(mode == "SHORT")
        self._long_row.setVisible(mode == "LONG")

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._wait_edit.get_value() is None:
            errors["wait_multiplier"] = (
                "Wait Multiplier: value is empty or invalid"
            )
        if self._mode_seg.current_value() == "SHORT":
            if self._short_edit.get_value() is None:
                errors["short_time"] = (
                    "Short Aperture: value is empty or invalid"
                )
        return errors


_MODE_DISPLAY_TO_INTERNAL = {
    "Automatic": "AUTO",
    "Automatic with limitation": "LIM",
    "Fixed": "FIX",
}
_MODE_INTERNAL_TO_DISPLAY = {
    v: k for k, v in _MODE_DISPLAY_TO_INTERNAL.items()
}


class _RangeRow(QWidget):
    changed = Signal(str, object)  # (mode, value)

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        unit_mode: str,
        instrument_model: str,
        initial_mode: str = "AUTO",
        initial_value: Optional[float] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.unit_mode = unit_mode
        self.instrument_model = instrument_model

        # Determine range options
        self.options = self._get_options()

        # Layout
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)

        # 1. Badge / Name
        self.badge = QLabel(unit_id)
        self.badge.setFixedWidth(48)
        self.badge.setStyleSheet(channel_row_badge_stylesheet(P.ACCENT_HOVER))
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.badge)

        # 2. Mode combo box
        self.mode_combo = QComboBox()
        self.mode_combo.setStyleSheet(unit_card_combo_stylesheet())
        self.mode_combo.setFixedWidth(180)
        for label in ["Automatic", "Automatic with limitation", "Fixed"]:
            self.mode_combo.addItem(label)

        display_mode = _MODE_INTERNAL_TO_DISPLAY.get(initial_mode, "Automatic")
        self.mode_combo.setCurrentText(display_mode)
        h.addWidget(self.mode_combo, stretch=1)

        # 3. Value combo box
        self.val_combo = QComboBox()
        self.val_combo.setStyleSheet(unit_card_combo_stylesheet())
        self.val_combo.setFixedWidth(100)
        h.addWidget(self.val_combo, stretch=1)

        self._repopulate_values(initial_value)

        # Connect signals
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.val_combo.currentIndexChanged.connect(self._on_value_changed)

    def _get_options(self) -> Tuple[Tuple[str, float], ...]:
        if self.unit_type == "SMU":
            is_voltage_range = self.unit_mode in ("I", "IPULSE")
            is_4156 = "56" in self.instrument_model
            if is_voltage_range:
                return RANGE_VALUES_SMU_VOLTAGE
            else:
                return (
                    RANGE_VALUES_HRSMU_CURRENT
                    if is_4156
                    else RANGE_VALUES_MPSMU_CURRENT
                )
        elif self.unit_type == "VMU":
            if self.unit_mode == "V":
                return RANGE_VALUES_VMU_V
            else:  # DVOLT
                return RANGE_VALUES_VMU_DVOL
        return ()

    def _repopulate_values(self, initial_value: Optional[float]) -> None:
        self.val_combo.blockSignals(True)
        self.val_combo.clear()
        for label, _ in self.options:
            self.val_combo.addItem(label)

        if initial_value is not None:
            best_idx = 0
            min_diff = float("inf")
            for idx, (_, val) in enumerate(self.options):
                diff = abs(val - initial_value)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = idx
            self.val_combo.setCurrentIndex(best_idx)
        else:
            self.val_combo.setCurrentIndex(0)
        self.val_combo.blockSignals(False)

        mode = _MODE_DISPLAY_TO_INTERNAL.get(
            self.mode_combo.currentText(), "AUTO"
        )
        self.val_combo.setEnabled(mode in ("LIM", "FIX"))

    def _on_mode_changed(self, display_mode: str) -> None:
        mode = _MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        self.val_combo.setEnabled(mode in ("LIM", "FIX"))
        self.changed.emit(mode, self.current_value())

    def _on_value_changed(self, idx: int) -> None:
        display_mode = self.mode_combo.currentText()
        mode = _MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        self.changed.emit(mode, self.current_value())

    def current_value(self) -> Optional[float]:
        display_mode = self.mode_combo.currentText()
        mode = _MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        if mode == "AUTO":
            return None
        idx = self.val_combo.currentIndex()
        if 0 <= idx < len(self.options):
            return self.options[idx][1]
        return None


class _RangesSection(_SectionFrame):
    range_changed = Signal(str, str, object)  # (unit_id, mode, value)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Measurement Ranges", parent)
        self._rows: Dict[str, _RangeRow] = {}

    def display_ranges(
        self,
        active_channels: List[dict],
        instrument_model: str,
        ranges_config: Dict[str, dict],
    ) -> None:
        while self.body().count():
            item = self.body().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        eligible_channels = []
        for ch in active_channels:
            if ch["unit_type"] in ("SMU", "VMU"):
                eligible_channels.append(ch)

        if not eligible_channels:
            lbl = QLabel("No active measurement units (SMU/VMU).")
            lbl.setStyleSheet(
                f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
                "font-style: italic; background: transparent;"
            )
            self.body().addWidget(lbl)
            return

        # Column headers
        hdr = _create_table_header(
            [
                ("Unit", 48),
                ("Range Mode", 180),
                ("Range Value", 100),
            ],
            spacing=10,
        )
        self.body().addWidget(hdr)
        self.body().addWidget(_create_horizontal_divider())

        for ch in eligible_channels:
            ch_id = ch["id"]
            r_data = ranges_config.get(ch_id, {})
            mode = r_data.get("mode", "AUTO")
            value = r_data.get("value")

            row = _RangeRow(
                unit_id=ch_id,
                unit_type=ch.get("unit_type", "SMU"),
                unit_mode=ch.get("mode", ""),
                instrument_model=instrument_model,
                initial_mode=mode,
                initial_value=value,
                parent=self,
            )
            row.changed.connect(
                lambda m, v, cid=ch_id: self.range_changed.emit(cid, m, v)
            )
            self._rows[ch_id] = row
            self.body().addWidget(row)


class _ConstantRow(QWidget):
    source_changed = Signal(str, float)
    compliance_changed = Signal(str, float)

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        unit_mode: str,
        initial_source: float,
        initial_compliance: Optional[float] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.unit_mode = unit_mode

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(10)

        # 1. Badge / Name
        self.badge = QLabel(unit_id)
        self.badge.setFixedWidth(48)
        self.badge.setStyleSheet(channel_row_badge_stylesheet(P.ACCENT_HOVER))
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.badge)

        # 2. Source input
        if unit_type == "VSU":
            min_s, max_s, unit_s = VSU_VOLTAGE_MIN, VSU_VOLTAGE_MAX, "V"
        else:
            if unit_mode in ("V", "VPULSE"):
                min_s, max_s, unit_s = VOLTAGE_MIN, VOLTAGE_MAX, "V"
            else:
                min_s, max_s, unit_s = CURRENT_MIN, CURRENT_MAX, "A"

        self.source_edit = _SciDoubleEdit(
            initial_source, min_s, max_s, unit_s, parent=self
        )
        self.source_edit._edit.setToolTip(
            f"Range: {min_s:.3g} – {max_s:.3g} {unit_s}"
        )
        self.source_edit.setFixedWidth(160)
        self.source_edit.value_committed.connect(
            lambda val: self.source_changed.emit(self.unit_id, val)
        )
        h.addWidget(self.source_edit, stretch=1)

        # 3. Compliance input (SMU only)
        if unit_type == "SMU":
            if unit_mode in ("V", "VPULSE"):
                min_c, max_c, unit_c = COMP_I_MIN, COMP_I_MAX, "A"
            else:
                min_c, max_c, unit_c = COMP_V_MIN, COMP_V_MAX, "V"

            comp_val = (
                initial_compliance if initial_compliance is not None else 0.01
            )
            self.compliance_edit = _SciDoubleEdit(
                comp_val, min_c, max_c, unit_c, parent=self
            )
            self.compliance_edit._edit.setToolTip(
                f"Range: {min_c:.3g} – {max_c:.3g} {unit_c}"
            )
            self.compliance_edit.setFixedWidth(160)
            self.compliance_edit.value_committed.connect(
                lambda val: self.compliance_changed.emit(self.unit_id, val)
            )
            h.addWidget(self.compliance_edit, stretch=1)
        else:
            self.compliance_edit = None
            spacer = QLabel("—")
            spacer.setStyleSheet(sweep_form_label_stylesheet())
            spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spacer.setFixedWidth(160)
            h.addWidget(spacer, stretch=1)


class _ConstantsSection(_SectionFrame):
    const_source_changed = Signal(str, float)
    const_compliance_changed = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Constant Sources", parent)
        self._rows: Dict[str, _ConstantRow] = {}

    def display_constants(
        self,
        active_channels: List[dict],
        constants_config: Dict[str, dict],
    ) -> None:
        while self.body().count():
            item = self.body().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        eligible_channels = []
        for ch in active_channels:
            if (
                ch.get("function") == "CONST"
                and ch.get("unit_type") in ("SMU", "VSU")
                and ch.get("mode") != "COMM"
            ):
                eligible_channels.append(ch)

        if not eligible_channels:
            lbl = QLabel("No constant source units configured.")
            lbl.setStyleSheet(
                f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
                "font-style: italic; background: transparent;"
            )
            self.body().addWidget(lbl)
            return

        # Column headers
        hdr = _create_table_header(
            [
                ("Unit", 48),
                ("Constant Source", 160),
                ("Compliance Limit", 160),
            ],
            spacing=10,
        )
        self.body().addWidget(hdr)
        self.body().addWidget(_create_horizontal_divider())

        for ch in eligible_channels:
            ch_id = ch["id"]
            c_data = constants_config.get(ch_id, {})
            source_val = c_data.get("source", 0.0)
            comp_val = (
                c_data.get("compliance", 0.01)
                if ch.get("unit_type") == "SMU"
                else None
            )

            row = _ConstantRow(
                unit_id=ch_id,
                unit_type=ch.get("unit_type", "SMU"),
                unit_mode=ch.get("mode", ""),
                initial_source=source_val,
                initial_compliance=comp_val,
                parent=self,
            )
            row.source_changed.connect(self.const_source_changed)
            row.compliance_changed.connect(self.const_compliance_changed)
            self._rows[ch_id] = row
            self.body().addWidget(row)

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        for ch_id, row in self._rows.items():
            if row.source_edit.get_value() is None:
                errors[f"const_source_{ch_id}"] = (
                    f"{ch_id} Constant Source: value is empty or invalid"
                )
            if row.compliance_edit is not None:
                if row.compliance_edit.get_value() is None:
                    errors[f"const_compliance_{ch_id}"] = (
                        f"{ch_id} Constant Compliance: value is empty or invalid"
                    )
        return errors


class _SweepTimingSection(_SectionFrame):
    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Sweep Timing", parent)
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

        self._stop_seg = _SegmentedGroup(["COMPLIANCE", "END"], "COMPLIANCE")
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("VAR1  —  Primary Sweep", parent)
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.ACCENT_HOVER}; font-size: {P.FONT_SIZE_SM}; "
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
        self._pcomp_edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")

        for label, widget in [
            ("Mode", self._mode_seg),
            ("Spacing", self._spacing_seg),
            ("Start", self._start_edit),
            ("Stop", self._stop_edit),
            ("Step", self._step_edit),
            ("Compliance", self._comp_edit),
            ("Power Compliance", self._pcomp_edit),
        ]:
            self.body().addWidget(_form_row(label, widget))

        self._mode_seg.selection_changed.connect(self.mode_changed)
        self._spacing_seg.selection_changed.connect(self.spacing_changed)
        self._spacing_seg.selection_changed.connect(self._on_spacing_changed)
        self._start_edit.value_committed.connect(self.start_committed)
        self._stop_edit.value_committed.connect(self.stop_committed)
        self._step_edit.value_committed.connect(self.step_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_edit.value_committed.connect(self.pcomp_committed)

    def _on_spacing_changed(self, spacing: str) -> None:
        is_linear = spacing == "LINEAR"
        self._step_edit.setEnabled(is_linear)

    # ── Display API ───────────────────────────────────────────────────────────

    def display_state(
        self,
        mode: str,
        spacing: str,
        start: float,
        stop: float,
        step: float,
        compliance: float,
        pcomp: float,
    ) -> None:
        self._mode_seg.set_value(mode)
        self._spacing_seg.set_value(spacing)
        self._on_spacing_changed(spacing)
        self._start_edit.set_value(start)
        self._stop_edit.set_value(stop)
        self._step_edit.set_value(step)
        self._comp_edit.set_value(compliance)
        self._pcomp_edit.set_value(pcomp)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(self, is_voltage: bool, is_vsu: bool = False) -> None:
        """Called by the view when sweep-type context changes."""
        SC = SweepConstraints
        src_min, src_max = SC.source_range(is_voltage, is_vsu)
        if is_vsu:
            # VSU step follows total VSU range width
            stp_min, stp_max = 0.0, abs(src_max - src_min)
        else:
            stp_min, stp_max = SC.step_range(
                is_voltage, is_var2_or_offset=False
            )
        cmp_min, cmp_max = SC.compliance_range(is_voltage or is_vsu)
        src_u = SC.source_unit(is_voltage or is_vsu)
        cmp_u = SC.compliance_unit(is_voltage or is_vsu)

        self._start_edit.update_bounds(src_min, src_max, src_u)
        self._stop_edit.update_bounds(src_min, src_max, src_u)
        self._step_edit.update_bounds(stp_min, stp_max, src_u)
        self._comp_edit.update_bounds(cmp_min, cmp_max, cmp_u)

    # ── Cross-param helper (read-only) ────────────────────────────────────────

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
        else:
            if all(v is not None for v in (start, stop)):
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
        if self._comp_edit.get_value() is None:
            errors["var1_comp"] = "VAR1 Compliance: value is empty or invalid"
        if self._pcomp_edit.get_value() is None:
            errors["var1_pcomp"] = (
                "VAR1 Power Compliance: value is empty or invalid"
            )
        return errors


class _VAR2Section(_SectionFrame):
    start_committed = Signal(float)
    step_committed = Signal(float)
    points_changed = Signal(int)
    comp_committed = Signal(float)
    pcomp_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("VAR2  —  Stepped Sweep", parent)
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: {P.STATUS_WARN}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(self._channel_lbl)

        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(
            0.1, VAR2_V_STEP_MIN, VAR2_V_STEP_MAX, "V", disallow_zero=True
        )
        self._points_sb = _spinbox(VAR2_POINTS_MIN, VAR2_POINTS_MAX, 3)
        self._points_sb.setToolTip(
            f"Range: {VAR2_POINTS_MIN} – {VAR2_POINTS_MAX}"
        )
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")

        for label, widget in [
            ("Start", self._start_edit),
            ("Step", self._step_edit),
            ("Points", self._points_sb),
            ("Compliance", self._comp_edit),
            ("Power Compliance", self._pcomp_edit),
        ]:
            self.body().addWidget(_form_row(label, widget))

        self._start_edit.value_committed.connect(self.start_committed)
        self._step_edit.value_committed.connect(self.step_committed)
        self._points_sb.valueChanged.connect(self.points_changed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_edit.value_committed.connect(self.pcomp_committed)

    def display_state(
        self,
        start: float,
        step: float,
        points: int,
        compliance: float,
        pcomp: float,
    ) -> None:
        self._start_edit.set_value(start)
        self._step_edit.set_value(step)
        self._points_sb.blockSignals(True)
        self._points_sb.setValue(points)
        self._points_sb.blockSignals(False)
        self._comp_edit.set_value(compliance)
        self._pcomp_edit.set_value(pcomp)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(self, is_voltage: bool, is_vsu: bool = False) -> None:
        SC = SweepConstraints
        src_min, src_max = SC.source_range(is_voltage, is_vsu)
        stp_min, stp_max = SC.step_range(is_voltage, is_var2_or_offset=True)
        cmp_min, cmp_max = SC.compliance_range(is_voltage or is_vsu)
        src_u = SC.source_unit(is_voltage or is_vsu)
        cmp_u = SC.compliance_unit(is_voltage or is_vsu)
        self._start_edit.update_bounds(src_min, src_max, src_u)
        self._step_edit.update_bounds(stp_min, stp_max, src_u)
        self._comp_edit.update_bounds(cmp_min, cmp_max, cmp_u)

    def get_points(self) -> int:
        return self._points_sb.value()

    def get_input_errors(self) -> Dict[str, str]:
        errors = {}
        if self._start_edit.get_value() is None:
            errors["var2_start"] = "VAR2 Start: value is empty or invalid"
        if self._step_edit.get_value() is None:
            errors["var2_step"] = "VAR2 Step: value is empty or invalid"
        if self._comp_edit.get_value() is None:
            errors["var2_comp"] = "VAR2 Compliance: value is empty or invalid"
        if self._pcomp_edit.get_value() is None:
            errors["var2_pcomp"] = (
                "VAR2 Power Compliance: value is empty or invalid"
            )
        return errors


class _VARDSection(_SectionFrame):
    offset_committed = Signal(float)
    ratio_committed = Signal(float)
    comp_committed = Signal(float)
    pcomp_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("VARD  —  VAR1 Derivative", parent)
        self._channel_lbl = QLabel("")
        self._channel_lbl.setStyleSheet(
            f"color: #c586c0; font-size: {P.FONT_SIZE_SM}; "
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
        self._pcomp_edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")

        for label, widget in [
            ("Offset", self._offset_edit),
            ("Ratio", self._ratio_edit),
            ("Compliance", self._comp_edit),
            ("Power Compliance", self._pcomp_edit),
        ]:
            self.body().addWidget(_form_row(label, widget))

        self._offset_edit.value_committed.connect(self.offset_committed)
        self._ratio_edit.value_committed.connect(self.ratio_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_edit.value_committed.connect(self.pcomp_committed)

    def display_state(
        self, offset: float, ratio: float, compliance: float, pcomp: float
    ) -> None:
        self._offset_edit.set_value(offset)
        self._ratio_edit.set_value(ratio)
        self._comp_edit.set_value(compliance)
        self._pcomp_edit.set_value(pcomp)

    def display_context(self, channel_label: str) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def update_ranges(self, is_voltage: bool, is_vsu: bool = False) -> None:
        SC = SweepConstraints
        if is_vsu:
            off_min, off_max = VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX
        elif is_voltage:
            off_min, off_max = VARD_OFFSET_V_MIN, VARD_OFFSET_V_MAX
        else:
            off_min, off_max = VARD_OFFSET_I_MIN, VARD_OFFSET_I_MAX
        cmp_min, cmp_max = SC.compliance_range(is_voltage or is_vsu)
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
        if self._comp_edit.get_value() is None:
            errors["vard_comp"] = "VARD Compliance: value is empty or invalid"
        if self._pcomp_edit.get_value() is None:
            errors["vard_pcomp"] = (
                "VARD Power Compliance: value is empty or invalid"
            )
        return errors


class _DisplayVarsSection(_SectionFrame):
    var_toggled = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Display Variables", parent)
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._grid = QGridLayout()
        self._grid.setSpacing(8)
        self.body().addLayout(self._grid)

    def display_available(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        for cb in self._checkboxes.values():
            cb.deleteLater()
        self._checkboxes.clear()
        while self._grid.count():
            self._grid.takeAt(0)

        sel = set(selected)
        for i, name in enumerate(var_names):
            cb = QCheckBox(name)
            cb.setChecked(name in sel)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(unit_enable_checkbox_stylesheet())
            cb.toggled.connect(
                lambda checked, n=name: self.var_toggled.emit(n, checked)
            )
            self._checkboxes[name] = cb
            self._grid.addWidget(cb, i // 4, i % 4)

    def set_selected(self, selected: List[str]) -> None:
        sel = set(selected)
        for name, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in sel)
            cb.blockSignals(False)


# ── JSON preview dialog ───────────────────────────────────────────────────────


class _JsonPreviewDialog(QDialog):
    def __init__(self, json_str: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generated JSON — Sweep Configuration")
        self.resize(640, 520)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(json_str)
        self._text.setStyleSheet(
            f"background-color: #0d0d0d; color: #d4d4d4; "
            f"font-family: {P.FONT_FAMILY_MONO}; font-size: 12px; "
            f"border: 1px solid {P.BORDER}; border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(self._text, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(export_btn_stylesheet())
        copy_btn.clicked.connect(self._copy)
        buttons.addButton(copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(
            f"QDialog {{ background-color: {P.BG_DEEP}; }} "
            f"QDialogButtonBox QPushButton {{ background: {P.BG_PANEL}; "
            f"color: {P.TEXT_SECONDARY}; border: 1px solid {P.BORDER}; "
            f"border-radius: 4px; padding: 6px 16px; }}"
        )

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._text.toPlainText())


# ── Main page view ────────────────────────────────────────────────────────────


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

    var2_start_committed = Signal(float)
    var2_step_committed = Signal(float)
    var2_points_changed = Signal(int)
    var2_comp_committed = Signal(float)
    var2_pcomp_committed = Signal(float)

    vard_offset_committed = Signal(float)
    vard_ratio_committed = Signal(float)
    vard_comp_committed = Signal(float)
    vard_pcomp_committed = Signal(float)

    smu_standby_changed = Signal(str, bool)
    display_var_toggled = Signal(str, bool)
    export_requested = Signal()
    range_changed = Signal(str, str, object)
    const_source_changed = Signal(str, float)
    const_compliance_changed = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._wire_sections()

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API ───────────────────────────────────────────────────────────

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
        )
        v2 = snap.get("var2", {})
        self._var2_sec.display_state(
            v2.get("start", 0.0),
            v2.get("step", 0.1),
            v2.get("points", 3),
            v2.get("compliance", 0.01),
            v2.get("power_compliance", 0.01),
        )
        vd = snap.get("vard", {})
        self._vard_sec.display_state(
            vd.get("offset", 0.0),
            vd.get("ratio", 1.0),
            vd.get("compliance", 0.01),
            vd.get("power_compliance", 0.01),
        )

    def display_var_sections(
        self, has_var1: bool, has_var2: bool, has_vard: bool
    ) -> None:
        self._var1_sec.setVisible(has_var1)
        self._var2_sec.setVisible(has_var2)
        self._vard_sec.setVisible(has_vard)

    def display_var1_context(
        self, channel_label: str, is_voltage: bool, is_vsu: bool = False
    ) -> None:
        self._var1_sec.update_ranges(is_voltage, is_vsu)
        self._var1_sec.display_context(channel_label)

    def display_var2_context(
        self, channel_label: str, is_voltage: bool, is_vsu: bool = False
    ) -> None:
        self._var2_sec.update_ranges(is_voltage, is_vsu)
        self._var2_sec.display_context(channel_label)

    def display_vard_context(
        self, channel_label: str, is_voltage: bool, is_vsu: bool = False
    ) -> None:
        self._vard_sec.update_ranges(is_voltage, is_vsu)
        self._vard_sec.display_context(channel_label)

    def display_available_vars(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        self._display_vars_sec.display_available(var_names, selected)

    def display_validation_status(self, is_valid: bool, message: str) -> None:
        """Update the validation status label in the header."""
        self._export_btn.setEnabled(is_valid)
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

    def display_constants_setup(
        self,
        active_channels: List[dict],
        constants_config: Dict[str, dict],
    ) -> None:
        self._constants_sec.display_constants(
            active_channels, constants_config
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

    # ── Private — layout ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(sweep_page_stylesheet())

        # Header
        header = QWidget()
        header.setStyleSheet(
            f"background-color: {P.BG_PANEL}; border-bottom: 1px solid {P.BORDER};"
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

        # Validation status label
        self._validation_lbl = QLabel()
        hh.addWidget(self._validation_lbl)

        hh.addStretch()
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
            self._timing_sec,
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

        v2 = self._var2_sec
        v2.start_committed.connect(self.var2_start_committed)
        v2.step_committed.connect(self.var2_step_committed)
        v2.points_changed.connect(self.var2_points_changed)
        v2.comp_committed.connect(self.var2_comp_committed)
        v2.pcomp_committed.connect(self.var2_pcomp_committed)

        vd = self._vard_sec
        vd.offset_committed.connect(self.vard_offset_committed)
        vd.ratio_committed.connect(self.vard_ratio_committed)
        vd.comp_committed.connect(self.vard_comp_committed)
        vd.pcomp_committed.connect(self.vard_pcomp_committed)

        self._display_vars_sec.var_toggled.connect(self.display_var_toggled)
        self._ranges_sec.range_changed.connect(self.range_changed)

        self._constants_sec.const_source_changed.connect(
            self.const_source_changed
        )
        self._constants_sec.const_compliance_changed.connect(
            self.const_compliance_changed
        )
