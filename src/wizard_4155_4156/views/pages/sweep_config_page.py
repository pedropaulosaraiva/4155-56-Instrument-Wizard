"""
views/pages/sweep_config_page.py
---------------------------------
Sweep Configuration page — pure View layer.

Layout
------
┌──────────────────────────────────────────────────────────────────┐
│  Page header: title + Generate JSON button + error bar           │
├────────────────────────┬─────────────────────────────────────────┤
│  LEFT (380 px fixed)   │  RIGHT (expanding)                      │
│  ─ Channel Summary ─   │  ─ VAR1 ─────────────────────────────   │
│  ─ Measurement Setup ─ │  ─ VAR2 ─────────────────────────────   │
│  ─ Sweep Timing ─      │  ─ VARD ─────────────────────────────   │
│                        │  ─ Display Variables ─────────────────  │
└────────────────────────┴─────────────────────────────────────────┘

_SciDoubleEdit  — QLineEdit that accepts scientific notation, with
                  automatic red-border feedback when out of range.

_SegmentedGroup — horizontal group of checkable QPushButtons that
                  behaves like an exclusive radio group.

_SectionFrame   — titled card (matching the channels page style).
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage


# ── Internal reusable widgets ─────────────────────────────────────────────────


class _SciDoubleEdit(QWidget):
    """
    QLineEdit that accepts scientific notation (e.g. 2e-4, -1.5E3).
    Shows a red border and tooltip when the value is out of the configured
    range.  Emits value_committed(float) on editingFinished if valid.
    """

    value_committed = Signal(float)

    def __init__(
        self,
        default: float,
        min_v: float,
        max_v: float,
        unit: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min = min_v
        self._max = max_v

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        from PySide6.QtWidgets import QLineEdit

        self._edit = QLineEdit()
        self._edit.setStyleSheet(unit_card_line_edit_stylesheet())
        validator = QDoubleValidator(min_v, max_v, 10, self._edit)
        self._edit.setValidator(validator)
        self._set_text(default)
        h.addWidget(self._edit, stretch=1)

        if unit:
            lbl = QLabel(unit)
            lbl.setStyleSheet(sweep_unit_label_stylesheet())
            lbl.setFixedWidth(30)
            h.addWidget(lbl)

        self._edit.editingFinished.connect(self._on_finish)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_value(self, val: float) -> None:
        self._edit.blockSignals(True)
        self._set_text(val)
        self._clear_error()
        self._edit.blockSignals(False)

    def get_value(self) -> Optional[float]:
        try:
            v = float(self._edit.text())
            if self._min <= v <= self._max:
                return v
            return None
        except ValueError:
            return None

    def set_error(self, msg: str = "") -> None:
        self._edit.setStyleSheet(input_error_stylesheet())
        if msg:
            self._edit.setToolTip(msg)

    def clear_error(self) -> None:
        self._clear_error()

    # ── Private ───────────────────────────────────────────────────────────────

    def _set_text(self, val: float) -> None:
        if val != 0 and (abs(val) < 0.01 or abs(val) >= 1e5):
            self._edit.setText(f"{val:.3e}")
        else:
            self._edit.setText(f"{val:.6g}")

    def _clear_error(self) -> None:
        self._edit.setStyleSheet(unit_card_line_edit_stylesheet())
        self._edit.setToolTip("")

    def _on_finish(self) -> None:
        v = self.get_value()
        if v is not None:
            self._clear_error()
            self.value_committed.emit(v)
        else:
            self.set_error(
                f"Value must be between {self._min:.3g} and {self._max:.3g}"
            )


class _SegmentedGroup(QWidget):
    """
    Horizontal group of checkable QPushButtons acting as an exclusive
    radio group.  Emits selection_changed(str) when the active button changes.
    """

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
            self._buttons[value].blockSignals(True)
            self._group.blockSignals(True)
            self._buttons[value].setChecked(True)
            self._group.blockSignals(False)
            self._buttons[value].blockSignals(False)
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
            if btn.isChecked():
                btn.setStyleSheet(segmented_btn_checked_stylesheet())
            else:
                btn.setStyleSheet(segmented_btn_unchecked_stylesheet())


class _SectionFrame(QFrame):
    """Titled section card matching the visual language of the channels page."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # Title row with horizontal rule
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

        # Content card
        self._card = QFrame()
        self._card.setObjectName("section_card")
        self._card.setStyleSheet(sweep_section_card_stylesheet())
        self._form_layout = QVBoxLayout(self._card)
        self._form_layout.setContentsMargins(16, 14, 16, 14)
        self._form_layout.setSpacing(10)
        root.addWidget(self._card)

    def body(self) -> QVBoxLayout:
        return self._form_layout

    def card(self) -> QFrame:
        return self._card


def _form_row(
    label_text: str,
    widget: QWidget,
    label_width: int = 160,
) -> QWidget:
    """A label + control horizontal row for use inside section bodies."""
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


# ── Section widgets ───────────────────────────────────────────────────────────


class _ChannelSummarySection(_SectionFrame):
    """
    Shows one row per enabled channel (from Channels page) with
    a Standby toggle for each SMU.

    Signals
    -------
    smu_standby_changed(channel_id: str, on: bool)
    """

    smu_standby_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Channel Assignments", parent)
        self._standby_cbs: Dict[str, QCheckBox] = {}

    def display_channels(self, active_channels: List[dict]) -> None:
        """
        active_channels: list of dicts, one per enabled channel.
        Expected keys: id, unit_type, function, mode, v_name,
                       i_name (SMU only), standby (SMU only, bool).
        """
        # Clear existing rows
        while self.body().count():
            item = self.body().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._standby_cbs.clear()

        if not active_channels:
            placeholder = QLabel(
                "No channels enabled — configure the Channels page first."
            )
            placeholder.setStyleSheet(
                f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
                "font-style: italic; background: transparent;"
            )
            self.body().addWidget(placeholder)
            return

        # Header labels
        header = QWidget()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 4)
        hh.setSpacing(0)
        for text, width in [
            ("Channel", 52),
            ("Function", 100),
            ("Mode", 68),
            ("V-Name", 70),
            ("I-Name", 70),
            ("Standby", 70),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
                "font-weight: bold; letter-spacing: 1px; background: transparent;"
            )
            lbl.setFixedWidth(width)
            hh.addWidget(lbl)
        hh.addStretch()
        self.body().addWidget(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background-color: {P.BORDER}; max-height: 1px;")
        self.body().addWidget(div)

        # One row per channel
        for ch in active_channels:
            ch_id = ch["id"]  # e.g. "SMU2"
            fn = ch.get("function", "CONST")
            mode = ch.get("mode", "V")
            v_name = ch.get("v_name", "")
            i_name = ch.get("i_name", "")
            is_smu = ch.get("unit_type") == "SMU"
            standby = ch.get("standby", False)

            row = QWidget()
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 2, 0, 2)
            rh.setSpacing(0)

            # Channel badge
            ch_lbl = QLabel(ch_id)
            ch_lbl.setFixedWidth(52)
            ch_lbl.setStyleSheet(channel_row_badge_stylesheet(P.ACCENT_HOVER))
            ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Function badge (colour-coded)
            fn_colors = {
                "VAR1": P.STATUS_OK,
                "VAR2": P.STATUS_WARN,
                "VAR1'": "#c586c0",  # purple
                "CONST": P.TEXT_MUTED,
                "COMM": P.TEXT_DISABLED,
            }
            fn_lbl = QLabel(fn)
            fn_lbl.setFixedWidth(100)
            fn_lbl.setStyleSheet(
                channel_row_badge_stylesheet(fn_colors.get(fn, P.TEXT_MUTED))
            )

            # Map display mode names (VPULSE -> VPUL, IPULSE -> IPUL)
            # TODO: Remove this sloppy code
            display_mode = mode
            if display_mode == "VPULSE":
                display_mode = "VPUL"
            elif display_mode == "IPULSE":
                display_mode = "IPUL"

            mode_lbl = QLabel(display_mode)
            mode_lbl.setFixedWidth(68)
            mode_lbl.setStyleSheet(sweep_form_label_stylesheet())

            vn_lbl = QLabel(v_name)
            vn_lbl.setFixedWidth(70)
            vn_lbl.setStyleSheet(
                f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_SM}; "
                f"font-family: {P.FONT_FAMILY_MONO}; background: transparent;"
            )

            in_lbl = QLabel(i_name if is_smu else "—")
            in_lbl.setFixedWidth(70)
            in_lbl.setStyleSheet(
                f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_SM}; "
                f"font-family: {P.FONT_FAMILY_MONO}; background: transparent;"
            )

            for w in (ch_lbl, fn_lbl, mode_lbl, vn_lbl, in_lbl):
                rh.addWidget(w)

            # Standby toggle (SMUs only)
            if is_smu:
                cb = QCheckBox()
                cb.setChecked(standby)
                cb.setStyleSheet(unit_enable_checkbox_stylesheet())
                cb.setFixedWidth(70)
                cb.toggled.connect(
                    lambda checked, cid=ch_id: self.smu_standby_changed.emit(
                        cid, checked
                    )
                )
                self._standby_cbs[ch_id] = cb
                rh.addWidget(cb)
            else:
                spacer_lbl = QLabel("—")
                spacer_lbl.setFixedWidth(70)
                spacer_lbl.setStyleSheet(sweep_form_label_stylesheet())
                rh.addWidget(spacer_lbl)

            rh.addStretch()
            self.body().addWidget(row)

    def set_standby(self, ch_id: str, on: bool) -> None:
        if ch_id in self._standby_cbs:
            self._standby_cbs[ch_id].blockSignals(True)
            self._standby_cbs[ch_id].setChecked(on)
            self._standby_cbs[ch_id].blockSignals(False)


class _MeasSetupSection(_SectionFrame):
    """Integration mode selector + conditional time/cycle inputs."""

    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_time_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Measurement Setup", parent)
        self._setup_widgets()

    def _setup_widgets(self) -> None:
        from wizard_4155_4156.models.sweep_config import (
            SHORT_TIME_MIN,
            SHORT_TIME_MAX,
            LONG_CYCLES_MIN,
            LONG_CYCLES_MAX,
            TIMING_MIN,
            TIMING_MAX,
        )

        self._mode_seg = _SegmentedGroup(["SHORT", "MED", "LONG"], "MED")
        self.body().addWidget(_form_row("Integration Mode", self._mode_seg))

        self._short_time_edit = _SciDoubleEdit(
            2e-4, SHORT_TIME_MIN, SHORT_TIME_MAX, "s"
        )
        self._short_row = _form_row("Short Integ. Time", self._short_time_edit)
        self._short_row.setVisible(False)
        self.body().addWidget(self._short_row)

        self._long_cycles_sb = _spinbox(LONG_CYCLES_MIN, LONG_CYCLES_MAX, 50)
        self._long_row = _form_row("Integration Cycles", self._long_cycles_sb)
        self._long_row.setVisible(False)
        self.body().addWidget(self._long_row)

        self._wait_edit = _SciDoubleEdit(1.0, TIMING_MIN, TIMING_MAX, "s")
        self.body().addWidget(_form_row("Wait Time", self._wait_edit))

        self._mode_seg.selection_changed.connect(self._on_mode_changed)
        self._mode_seg.selection_changed.connect(self.integration_mode_changed)
        self._short_time_edit.value_committed.connect(
            self.short_time_committed
        )
        self._long_cycles_sb.valueChanged.connect(self.long_cycles_changed)
        self._wait_edit.value_committed.connect(self.wait_time_committed)

    def display_state(
        self, mode: str, short_time: float, long_cycles: int, wait: float
    ) -> None:
        self._mode_seg.set_value(mode)
        self._short_time_edit.set_value(short_time)
        self._long_cycles_sb.blockSignals(True)
        self._long_cycles_sb.setValue(long_cycles)
        self._long_cycles_sb.blockSignals(False)
        self._wait_edit.set_value(wait)
        self._on_mode_changed(mode)

    def set_field_error(self, field: str, msg: str) -> None:
        targets = {
            "short_time": self._short_time_edit,
            "wait_time": self._wait_edit,
        }
        if field in targets:
            targets[field].set_error(msg)
        if field == "long_cycles":
            self._long_cycles_sb.setStyleSheet(input_error_stylesheet())
            self._long_cycles_sb.setToolTip(msg)

    def clear_errors(self) -> None:
        self._short_time_edit.clear_error()
        self._wait_edit.clear_error()
        self._long_cycles_sb.setStyleSheet(sweep_spinbox_stylesheet())
        self._long_cycles_sb.setToolTip("")

    def _on_mode_changed(self, mode: str) -> None:
        self._short_row.setVisible(mode == "SHORT")
        self._long_row.setVisible(mode == "LONG")


class _SweepTimingSection(_SectionFrame):
    """Delay, hold time, and sweep-stop condition."""

    delay_committed = Signal(float)
    hold_time_committed = Signal(float)
    sweep_stop_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Sweep Timing", parent)
        self._setup_widgets()

    def _setup_widgets(self) -> None:
        from wizard_4155_4156.models.sweep_config import TIMING_MIN, TIMING_MAX

        self._delay_edit = _SciDoubleEdit(0.1, TIMING_MIN, TIMING_MAX, "s")
        self.body().addWidget(_form_row("Delay", self._delay_edit))

        self._hold_edit = _SciDoubleEdit(0.5, TIMING_MIN, TIMING_MAX, "s")
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

    def set_field_error(self, field: str, msg: str) -> None:
        {"delay": self._delay_edit, "hold_time": self._hold_edit}.get(
            field, self._delay_edit
        ).set_error(msg)

    def clear_errors(self) -> None:
        self._delay_edit.clear_error()
        self._hold_edit.clear_error()


class _VAR1Section(_SectionFrame):
    """VAR1 sweep channel configuration."""

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

        from wizard_4155_4156.models.sweep_config import (
            VOLTAGE_MIN,
            VOLTAGE_MAX,
            COMP_I_MIN,
            COMP_I_MAX,
            PCOMP_MIN,
            PCOMP_MAX,
        )

        self._mode_seg = _SegmentedGroup(["SINGLE", "DOUBLE"], "SINGLE")
        self._spacing_seg = _SegmentedGroup(
            ["LINEAR", "L10", "L25", "L50"], "LINEAR"
        )
        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._stop_edit = _SciDoubleEdit(1.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(0.1, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")
        self._step_count_lbl = QLabel("")
        self._step_count_lbl.setStyleSheet(
            f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_XS}; "
            "background: transparent; font-style: italic;"
        )

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
        self.body().addWidget(self._step_count_lbl)

        self._mode_seg.selection_changed.connect(self.mode_changed)
        self._spacing_seg.selection_changed.connect(self.spacing_changed)
        self._start_edit.value_committed.connect(self._update_step_count)
        self._start_edit.value_committed.connect(self.start_committed)
        self._stop_edit.value_committed.connect(self._update_step_count)
        self._stop_edit.value_committed.connect(self.stop_committed)
        self._step_edit.value_committed.connect(self._update_step_count)
        self._step_edit.value_committed.connect(self.step_committed)
        self._comp_edit.value_committed.connect(self.comp_committed)
        self._pcomp_edit.value_committed.connect(self.pcomp_committed)

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
        self._start_edit.set_value(start)
        self._stop_edit.set_value(stop)
        self._step_edit.set_value(step)
        self._comp_edit.set_value(compliance)
        self._pcomp_edit.set_value(pcomp)
        self._update_step_count()

    def display_context(
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")
        for edit, unit in [
            (self._start_edit, sweep_unit),
            (self._stop_edit, sweep_unit),
            (self._step_edit, sweep_unit),
            (self._comp_edit, comp_unit),
        ]:
            edit._edit.setPlaceholderText(unit)

    def set_field_error(self, field: str, msg: str) -> None:
        targets = {
            "var1_start": self._start_edit,
            "var1_stop": self._stop_edit,
            "var1_step": self._step_edit,
            "var1_compliance": self._comp_edit,
            "var1_pcomp": self._pcomp_edit,
        }
        if field in targets:
            targets[field].set_error(msg)
        if field == "var1_step_count":
            self._step_count_lbl.setStyleSheet(
                f"color: {P.STATUS_ERROR}; font-size: {P.FONT_SIZE_XS}; "
                "background: transparent;"
            )
            self._step_count_lbl.setText(f"⚠  {msg}")

    def clear_errors(self) -> None:
        for e in (
            self._start_edit,
            self._stop_edit,
            self._step_edit,
            self._comp_edit,
            self._pcomp_edit,
        ):
            e.clear_error()
        self._step_count_lbl.setStyleSheet(
            f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_XS}; background: transparent;"
        )

    def _update_step_count(self) -> None:
        start = self._start_edit.get_value()
        stop = self._stop_edit.get_value()
        step = self._step_edit.get_value()
        if all(v is not None for v in (start, stop, step)) and step != 0:
            count = round(abs((stop - start) / step)) + 1
            ok = 1 <= count <= 1001
            color = P.STATUS_OK if ok else P.STATUS_ERROR
            self._step_count_lbl.setStyleSheet(
                f"color: {color}; font-size: {P.FONT_SIZE_XS}; background: transparent;"
            )
            self._step_count_lbl.setText(f"{count} sweep points")


class _VAR2Section(_SectionFrame):
    """VAR2 stepped channel configuration."""

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

        from wizard_4155_4156.models.sweep_config import (
            VOLTAGE_MIN,
            VOLTAGE_MAX,
            COMP_I_MIN,
            COMP_I_MAX,
            PCOMP_MIN,
            PCOMP_MAX,
            POINTS_MIN,
            POINTS_MAX,
        )

        self._start_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._step_edit = _SciDoubleEdit(0.1, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._points_sb = _spinbox(POINTS_MIN, POINTS_MAX, 3)
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

    def display_context(
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def set_field_error(self, field: str, msg: str) -> None:
        targets = {
            "var2_start": self._start_edit,
            "var2_step": self._step_edit,
            "var2_compliance": self._comp_edit,
            "var2_pcomp": self._pcomp_edit,
        }
        if field in targets:
            targets[field].set_error(msg)
        if field == "var2_points":
            self._points_sb.setStyleSheet(input_error_stylesheet())
            self._points_sb.setToolTip(msg)

    def clear_errors(self) -> None:
        for e in (
            self._start_edit,
            self._step_edit,
            self._comp_edit,
            self._pcomp_edit,
        ):
            e.clear_error()
        self._points_sb.setStyleSheet(sweep_spinbox_stylesheet())
        self._points_sb.setToolTip("")


class _VARDSection(_SectionFrame):
    """VARD (VAR1-derivative) channel configuration."""

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

        from wizard_4155_4156.models.sweep_config import (
            VOLTAGE_MIN,
            VOLTAGE_MAX,
            COMP_I_MIN,
            COMP_I_MAX,
            PCOMP_MIN,
            PCOMP_MAX,
            RATIO_MIN,
            RATIO_MAX,
        )

        self._offset_edit = _SciDoubleEdit(0.0, VOLTAGE_MIN, VOLTAGE_MAX, "V")
        self._ratio_edit = _SciDoubleEdit(1.0, RATIO_MIN, RATIO_MAX, "×")
        self._comp_edit = _SciDoubleEdit(0.01, COMP_I_MIN, COMP_I_MAX, "A")
        self._pcomp_edit = _SciDoubleEdit(0.01, PCOMP_MIN, PCOMP_MAX, "W")

        note = QLabel("Output = VAR1 × ratio + offset")
        note.setStyleSheet(
            f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
            "background: transparent; font-style: italic;"
        )
        self.body().addWidget(note)

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

    def display_context(
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._channel_lbl.setText(f"Assigned: {channel_label}")

    def set_field_error(self, field: str, msg: str) -> None:
        targets = {
            "vard_offset": self._offset_edit,
            "vard_ratio": self._ratio_edit,
            "vard_compliance": self._comp_edit,
            "vard_pcomp": self._pcomp_edit,
        }
        if field in targets:
            targets[field].set_error(msg)

    def clear_errors(self) -> None:
        for e in (
            self._offset_edit,
            self._ratio_edit,
            self._comp_edit,
            self._pcomp_edit,
        ):
            e.clear_error()


class _DisplayVarsSection(_SectionFrame):
    """Multi-select checkboxes for choosing which variables to display."""

    var_toggled = Signal(str, bool)  # var_name, selected

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Display Variables", parent)
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._grid = QGridLayout()
        self._grid.setSpacing(8)
        self.body().addLayout(self._grid)

    def display_available(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        # Clear
        for cb in self._checkboxes.values():
            cb.deleteLater()
        self._checkboxes.clear()
        while self._grid.count():
            self._grid.takeAt(0)

        selected_set = set(selected)
        for i, name in enumerate(var_names):
            cb = QCheckBox(name)
            cb.setChecked(name in selected_set)
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
            f"QDialogButtonBox QPushButton {{ "
            f"background: {P.BG_PANEL}; color: {P.TEXT_SECONDARY}; "
            f"border: 1px solid {P.BORDER}; border-radius: 4px; "
            f"padding: 6px 16px; }}"
        )

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._text.toPlainText())


# ── Main page view ────────────────────────────────────────────────────────────


class SweepConfigPageView(BasePage):
    """
    Sweep Configuration page — composed from section widgets.

    Lifecycle
    ---------
    on_activate() emits page_activated so the presenter refreshes its
    channel context from ChannelsPresenter before pushing display state.

    User-intent signals (→ SweepConfigPresenter)
    --------------------------------------------
    page_activated
    integration_mode_changed(str)
    short_time_committed(float)
    long_cycles_changed(int)
    wait_time_committed(float)
    delay_committed(float)
    hold_time_committed(float)
    sweep_stop_changed(str)
    var1_mode_changed(str)
    var1_spacing_changed(str)
    var1_start_committed(float)  … var1_step_committed(float)
    var1_comp_committed(float)   var1_pcomp_committed(float)
    var2_start_committed(float)  … var2_points_changed(int)
    var2_comp_committed(float)   var2_pcomp_committed(float)
    vard_offset_committed(float) vard_ratio_committed(float)
    vard_comp_committed(float)   vard_pcomp_committed(float)
    smu_standby_changed(str, bool)
    display_var_toggled(str, bool)
    export_requested()

    Display methods (← SweepConfigPresenter)
    -----------------------------------------
    display_channel_summary(list[dict])
    display_config(dict)              — full snapshot refresh
    display_var_sections(bool, bool, bool)
    display_var1_context(str, str, str)
    display_var2_context(str, str, str)
    display_vard_context(str, str, str)
    display_available_vars(list[str], list[str])
    display_validation_errors(dict[str, str])
    display_json(str)
    """

    # ── User-intent signals ───────────────────────────────────────────────────
    page_activated = Signal()

    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_time_committed = Signal(float)

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._wire_sections()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_activate(self) -> None:
        self.page_activated.emit()

    # ── Display API ───────────────────────────────────────────────────────────

    def display_channel_summary(self, active_channels: List[dict]) -> None:
        self._summary_sec.display_channels(active_channels)

    def display_config(self, snap: dict) -> None:
        """
        snap keys: measurement_setup (dict), delay, hold_time, sweep_stop,
                   var1 (dict), var2 (dict), vard (dict).
        """
        ms = snap.get("measurement_setup", {})
        self._meas_sec.display_state(
            ms.get("integration_mode", "MED"),
            ms.get("short_time", 2e-4),
            ms.get("long_time_cycles", 50),
            ms.get("wait_time", 1.0),
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
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._var1_sec.display_context(channel_label, sweep_unit, comp_unit)

    def display_var2_context(
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._var2_sec.display_context(channel_label, sweep_unit, comp_unit)

    def display_vard_context(
        self, channel_label: str, sweep_unit: str, comp_unit: str
    ) -> None:
        self._vard_sec.display_context(channel_label, sweep_unit, comp_unit)

    def display_available_vars(
        self, var_names: List[str], selected: List[str]
    ) -> None:
        self._display_vars_sec.display_available(var_names, selected)

    def display_validation_errors(self, errors: Dict[str, str]) -> None:
        # Clear all errors first
        for sec in (
            self._meas_sec,
            self._timing_sec,
            self._var1_sec,
            self._var2_sec,
            self._vard_sec,
        ):
            sec.clear_errors()

        if not errors:
            self._error_bar.setVisible(False)
            return

        self._error_bar.setVisible(True)
        summary = ";  ".join(errors.values())
        self._error_bar.setText(f"⚠  {len(errors)} error(s):  {summary}")

        # Route individual errors to the owning section
        sec_map = {
            "short_time": self._meas_sec,
            "long_cycles": self._meas_sec,
            "wait_time": self._meas_sec,
            "delay": self._timing_sec,
            "hold_time": self._timing_sec,
            "var1_start": self._var1_sec,
            "var1_stop": self._var1_sec,
            "var1_step": self._var1_sec,
            "var1_compliance": self._var1_sec,
            "var1_pcomp": self._var1_sec,
            "var1_step_count": self._var1_sec,
            "var2_start": self._var2_sec,
            "var2_step": self._var2_sec,
            "var2_points": self._var2_sec,
            "var2_compliance": self._var2_sec,
            "var2_pcomp": self._var2_sec,
            "vard_offset": self._vard_sec,
            "vard_ratio": self._vard_sec,
            "vard_compliance": self._vard_sec,
            "vard_pcomp": self._vard_sec,
        }
        for field, msg in errors.items():
            sec = sec_map.get(field)
            if sec:
                sec.set_field_error(field, msg)

    def display_json(self, json_str: str) -> None:
        dlg = _JsonPreviewDialog(json_str, self)
        dlg.exec()

    # ── Private ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(sweep_page_stylesheet())

        # ── Page header ───────────────────────────────────────────────────────
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
        hh.addStretch()

        self._export_btn = QPushButton("Generate JSON")
        self._export_btn.setStyleSheet(export_btn_stylesheet())
        self._export_btn.clicked.connect(self.export_requested)
        hh.addWidget(self._export_btn)

        root.addWidget(header)

        # ── Error bar (hidden by default) ─────────────────────────────────────
        self._error_bar = QLabel("")
        self._error_bar.setStyleSheet(error_bar_stylesheet())
        self._error_bar.setWordWrap(True)
        self._error_bar.setVisible(False)
        root.addWidget(self._error_bar)

        # ── Scrollable two-column body ────────────────────────────────────────
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

        # Left column
        left = QWidget()
        left.setFixedWidth(400)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(20)
        left_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._summary_sec = _ChannelSummarySection()
        self._meas_sec = _MeasSetupSection()
        self._timing_sec = _SweepTimingSection()

        for w in (self._summary_sec, self._meas_sec, self._timing_sec):
            left_v.addWidget(w)
        left_v.addStretch()

        # Right column
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(20)
        right_v.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._var1_sec = _VAR1Section()
        self._var2_sec = _VAR2Section()
        self._vard_sec = _VARDSection()
        self._display_vars_sec = _DisplayVarsSection()

        for w in (
            self._var1_sec,
            self._var2_sec,
            self._vard_sec,
            self._display_vars_sec,
        ):
            right_v.addWidget(w)
        right_v.addStretch()

        body_h.addWidget(left)
        body_h.addWidget(right, stretch=1)

        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

    def _wire_sections(self) -> None:
        s = self._summary_sec
        s.smu_standby_changed.connect(self.smu_standby_changed)

        m = self._meas_sec
        m.integration_mode_changed.connect(self.integration_mode_changed)
        m.short_time_committed.connect(self.short_time_committed)
        m.long_cycles_changed.connect(self.long_cycles_changed)
        m.wait_time_committed.connect(self.wait_time_committed)

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
