"""
views/widgets/config_sections.py
--------------------------------
Shared building blocks for the measurement configuration pages — pure
View layer.  Extracted verbatim from sweep_config_page.py so the sweep
and sampling pages can reuse the same sections.

Validation philosophy
---------------------
SciDoubleEdit handles its own per-widget parsing; bounds context is
pushed in via update_bounds().  Cross-parameter rules live in the
presenters/models, never here.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QApplication,
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
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.models.sweep_config import (
    COMP_I_MAX,
    COMP_I_MIN,
    COMP_V_ILOCK_MAX,
    COMP_V_MAX,
    COMP_V_MIN,
    CURRENT_MAX,
    CURRENT_MIN,
    LONG_CYCLES_MAX,
    LONG_CYCLES_MIN,
    RANGE_VALUES_HRSMU_CURRENT,
    RANGE_VALUES_MPSMU_CURRENT,
    RANGE_VALUES_SMU_VOLTAGE,
    RANGE_VALUES_VMU_DVOL,
    RANGE_VALUES_VMU_V,
    SHORT_TIME_MAX,
    SHORT_TIME_MIN,
    VOLTAGE_ILOCK_MAX,
    VOLTAGE_MAX,
    VOLTAGE_MIN,
    VSU_VOLTAGE_MAX,
    VSU_VOLTAGE_MIN,
    WAIT_MULT_MAX,
    WAIT_MULT_MIN,
)
from wizard_4155_4156.styles.stylesheets import (
    channel_row_badge_stylesheet,
    export_btn_stylesheet,
    form_label_stylesheet,
    section_card_stylesheet,
    segmented_btn_checked_stylesheet,
    segmented_btn_unchecked_stylesheet,
    sweep_spinbox_stylesheet,
    transparent_container_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
    unit_enable_checkbox_stylesheet,
    unit_label_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.doc_tooltip import SectionHeader

_SCI_DISPLAY_LOWER = 0.01
_SCI_DISPLAY_UPPER = 1e5
_MAX_SCI_PARTS = 2

# ── Shared helpers ──────────────────────────────────────────────


def form_row(
    label_text: str, widget: QWidget, label_width: int = 160
) -> QWidget:
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(label_width)
    lbl.setStyleSheet(form_label_stylesheet())
    lbl.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    h.addWidget(lbl)
    h.addWidget(widget, stretch=1)
    return row


def combo(options: List[str], default: str = "") -> QComboBox:
    cb = QComboBox()
    cb.setStyleSheet(unit_card_combo_stylesheet())
    for opt in options:
        cb.addItem(opt, opt)
    idx = cb.findData(default)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    return cb


def spinbox(lo: int, hi: int, default: int) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(lo, hi)
    sb.setValue(default)
    sb.setStyleSheet(sweep_spinbox_stylesheet())
    return sb


# ── Table grid (shared header + data rows) ──────────────────────
#
# A measurement-config table is a single QGridLayout: row 0 holds the
# column headers, row 1 a full-width divider and each data row is added
# cell by cell beneath them.  Because the header and every row share the
# same grid, the columns line up automatically from the widest cell in
# each column — there are no per-widget fixed widths to keep in sync.
# Per-table column stretch factors let the data-entry columns grow to
# fill a wide section instead of clustering on the left.

# A zero alignment lets a cell widget fill its grid cell horizontally;
# an explicit alignment keeps the widget at its natural size.
CELL_FILL = Qt.AlignmentFlag(0)
CELL_CENTER = Qt.AlignmentFlag.AlignCenter
CELL_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

TableHeader = Tuple[str, Qt.AlignmentFlag]  # (title, header alignment)
TableCell = Tuple[QWidget, Qt.AlignmentFlag]  # (widget, cell alignment)


def _create_header_label(text: str, alignment: Qt.AlignmentFlag) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_XS}; "
        "font-weight: bold; letter-spacing: 1px; background: transparent;"
    )
    label.setAlignment(alignment)
    return label


class TableGrid(QWidget):
    """A header row and data rows sharing one QGridLayout so columns stay
    aligned without fixed widths.  ``column_stretch`` maps a column index
    to a stretch factor so the chosen columns expand to fill a wide
    section."""

    _HEADER_ROW = 0
    _DIVIDER_ROW = 1
    _FIRST_DATA_ROW = 2

    def __init__(
        self,
        headers: List[TableHeader],
        column_stretch: Dict[int, int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(transparent_container_stylesheet())
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(6)
        self._next_data_row = self._FIRST_DATA_ROW

        for column, (text, alignment) in enumerate(headers):
            self._grid.addWidget(
                _create_header_label(text, alignment),
                self._HEADER_ROW,
                column,
            )
        self._grid.addWidget(
            create_horizontal_divider(),
            self._DIVIDER_ROW,
            0,
            1,
            len(headers),
        )
        for column, factor in column_stretch.items():
            self._grid.setColumnStretch(column, factor)

    def add_row(self, cells: List[TableCell]) -> None:
        for column, (widget, alignment) in enumerate(cells):
            self._grid.addWidget(
                widget, self._next_data_row, column, alignment
            )
        self._next_data_row += 1


def create_horizontal_divider() -> QFrame:
    div = QFrame()
    div.setFrameShape(QFrame.Shape.HLine)
    div.setStyleSheet(f"background-color: {P.BORDER}; max-height: 1px;")
    return div


def _placeholder_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
        "font-style: italic; background: transparent;"
    )
    return label


def _create_unit_badge(text: str, color: str = P.ACCENT_HOVER) -> QLabel:
    """Pill-style unit/function badge.  Sizes to its text (the badge
    stylesheet supplies the padding/border), so it needs no fixed width."""
    badge = QLabel(text)
    badge.setStyleSheet(channel_row_badge_stylesheet(color))
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return badge


def _create_name_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color:{P.TEXT_SECONDARY};font-size:{P.FONT_SIZE_SM};"
        f"font-family:{P.FONT_FAMILY_MONO};"
        "background:transparent;"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class SciDoubleValidator(QValidator):
    def __init__(self, min_val: float, max_val: float, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_str: str, pos: int):
        val_str = input_str.replace(",", ".").strip()
        return self._determine_state(val_str), input_str, pos

    def _classify_scientific_notation(
        self,
        val_str: str,
    ) -> QValidator.State | None:
        parts = val_str.lower().split("e")
        if len(parts) > _MAX_SCI_PARTS:
            return QValidator.State.Invalid
        mantissa, exponent = parts[0], parts[1]
        if mantissa not in ("", "-", "+", "-.", "+."):
            try:
                float(mantissa)
            except ValueError:
                return QValidator.State.Invalid
        if exponent in ("", "-", "+"):
            return QValidator.State.Intermediate
        try:
            int(exponent)
        except ValueError:
            return QValidator.State.Invalid
        return None

    def _determine_state(
        self,
        val_str: str,
    ) -> QValidator.State:
        if not val_str or val_str in ("-", "+", "-.", "+."):
            return QValidator.State.Intermediate

        if "e" in val_str.lower():
            result = self._classify_scientific_notation(val_str)
            if result is not None:
                return result
        else:
            try:
                float(val_str)
            except ValueError:
                if val_str in (".", "0.", "-0.", "+0."):
                    return QValidator.State.Intermediate
                return QValidator.State.Invalid

        try:
            val = float(val_str)
        except ValueError:
            return QValidator.State.Invalid
        return (
            QValidator.State.Acceptable
            if self.min_val <= val <= self.max_val
            else QValidator.State.Intermediate
        )


class SciDoubleEdit(QWidget):
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
            self._unit_lbl.setStyleSheet(unit_label_stylesheet())
            self._unit_lbl.setFixedWidth(32)
            h.addWidget(self._unit_lbl)
        else:
            self._unit_lbl = None

        self._edit.editingFinished.connect(self._on_finish)

    # ── Public API ──────────────────────────────────────────────

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
        self._edit.setToolTip(
            f"Range: {min_v:.3g} – {max_v:.3g} {unit}".rstrip()
        )

    def set_error(self, msg: str = "") -> None:
        pass

    def clear_error(self) -> None:
        pass

    def validate_value(self) -> bool:
        """Always returns True if a float can be parsed."""
        return self.get_value() is not None

    # ── Private ─────────────────────────────────────────────────

    def _set_text(self, val: float) -> None:
        if val != 0 and (
            abs(val) < _SCI_DISPLAY_LOWER or abs(val) >= _SCI_DISPLAY_UPPER
        ):
            self._edit.setText(f"{val:.3e}")
        else:
            self._edit.setText(f"{val:.6g}")

    def _on_finish(self) -> None:
        v = self.get_value()
        if v is not None:
            self.value_committed.emit(v)


# ── SegmentedGroup ──────────────────────────────────────────────


class SegmentedGroup(QWidget):
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


# ── SectionFrame ────────────────────────────────────────────────


class SectionFrame(QFrame):
    # Re-exposes the header's doc icon click; the owning page forwards this
    # to its own documentation_requested signal.
    doc_requested = Signal(str)  # DocTopic value

    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        accent: str | None = None,
        doc_topic: DocTopic | None = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = SectionHeader(title, accent=accent, doc_topic=doc_topic)
        header.doc_requested.connect(self.doc_requested)
        root.addWidget(header)

        self._card = QFrame()
        self._card.setObjectName("section_card")
        self._card.setStyleSheet(section_card_stylesheet(accent))
        self._body = QVBoxLayout(self._card)
        self._body.setContentsMargins(16, 14, 16, 14)
        self._body.setSpacing(10)
        root.addWidget(self._card)

    def body(self) -> QVBoxLayout:
        return self._body

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# ── Section widgets ─────────────────────────────────────────────


class ChannelSummarySection(SectionFrame):
    smu_standby_changed = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Channel Assignments",
            parent,
            doc_topic=DocTopic.CHANNEL_ASSIGNMENTS,
        )
        self._standby_cbs: Dict[str, QCheckBox] = {}

    def display_channels(self, active_channels: List[dict]) -> None:
        self._clear_body()
        self._standby_cbs.clear()

        if not active_channels:
            self.body().addWidget(
                _placeholder_label(
                    "No channels enabled — configure the Channels page first."
                )
            )
            return

        headers: List[TableHeader] = [
            ("Channel", CELL_CENTER),
            ("Function", CELL_CENTER),
            ("Mode", CELL_CENTER),
            ("V-Name", CELL_CENTER),
            ("I-Name", CELL_CENTER),
            ("Standby", CELL_CENTER),
        ]
        # Spread the columns evenly so the table fills the panel width.
        column_stretch = {col: 1 for col in range(len(headers))}
        table = TableGrid(headers, column_stretch)

        fn_colors = {
            "VAR1": P.FUNC_VAR1,
            "VAR2": P.FUNC_VAR2,
            "VAR1'": P.FUNC_VARD,
            "CONST": P.TEXT_SECONDARY,
            "MONITOR": P.TEXT_SECONDARY,
        }

        for ch in active_channels:
            ch_id = ch["id"]
            is_smu = ch.get("unit_type") == "SMU"
            fn = ch.get("function", "CONST")
            mode = ch.get("mode", "")

            fn_display = "MONIT" if fn == "MONITOR" else fn
            mode_display = mode
            if mode == "VPULSE":
                mode_display = "VPUL"
            elif mode == "IPULSE":
                mode_display = "IPUL"

            fn_color = fn_colors.get(fn, P.TEXT_MUTED)
            i_text = ch.get("i_name", "") if is_smu else "—"
            table.add_row(
                [
                    (_create_unit_badge(ch_id), CELL_CENTER),
                    (_create_unit_badge(fn_display, fn_color), CELL_CENTER),
                    (_create_unit_badge(mode_display, fn_color), CELL_CENTER),
                    (_create_name_label(ch.get("v_name", "")), CELL_CENTER),
                    (_create_name_label(i_text), CELL_CENTER),
                    (
                        self._build_standby_cell(
                            ch_id, is_smu, ch.get("standby", False)
                        ),
                        CELL_CENTER,
                    ),
                ]
            )

        self.body().addWidget(table)

    def _build_standby_cell(
        self,
        ch_id: str,
        is_smu: bool,
        standby: bool,
    ) -> QWidget:
        if is_smu:
            cb = QCheckBox()
            cb.setChecked(standby)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(unit_enable_checkbox_stylesheet())
            cb.toggled.connect(
                lambda checked, cid=ch_id: self.smu_standby_changed.emit(
                    cid, checked
                )
            )
            self._standby_cbs[ch_id] = cb
            return cb

        dash = QLabel("—")
        dash.setStyleSheet(form_label_stylesheet())
        dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return dash

    def set_standby(self, ch_id: str, on: bool) -> None:
        if ch_id in self._standby_cbs:
            self._standby_cbs[ch_id].blockSignals(True)
            self._standby_cbs[ch_id].setChecked(on)
            self._standby_cbs[ch_id].blockSignals(False)


class MeasSetupSection(SectionFrame):
    integration_mode_changed = Signal(str)
    short_time_committed = Signal(float)
    long_cycles_changed = Signal(int)
    wait_multiplier_committed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Measurement Setup",
            parent,
            doc_topic=DocTopic.MEASUREMENT_SETUP,
        )
        self._setup_widgets()

    def _setup_widgets(self) -> None:
        self._mode_seg = SegmentedGroup(["SHORT", "MED", "LONG"], "MED")
        self.body().addWidget(form_row("Integration Time", self._mode_seg))

        self._short_edit = SciDoubleEdit(
            2e-4, SHORT_TIME_MIN, SHORT_TIME_MAX, "s"
        )
        self._short_edit._edit.setToolTip(
            f"Range: {SHORT_TIME_MIN:.0e} – {SHORT_TIME_MAX:.2e} s"
        )
        self._short_row = form_row("Short Aperture", self._short_edit)
        self._short_row.setVisible(False)
        self.body().addWidget(self._short_row)

        self._long_sb = spinbox(LONG_CYCLES_MIN, LONG_CYCLES_MAX, 50)
        self._long_sb.setToolTip(
            f"Range: {LONG_CYCLES_MIN} – {LONG_CYCLES_MAX} PLC"
        )
        self._long_row = form_row("Integration Cycles", self._long_sb)
        self._long_row.setVisible(False)
        self.body().addWidget(self._long_row)

        self._wait_edit = SciDoubleEdit(1.0, WAIT_MULT_MIN, WAIT_MULT_MAX, "×")
        self._wait_edit._edit.setToolTip(
            "Dimensionless wait-time multiplier (0.0 – 10.0)"
        )
        self.body().addWidget(form_row("Wait Multiplier", self._wait_edit))

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


MODE_DISPLAY_TO_INTERNAL = {
    "Automatic": "AUTO",
    "Automatic with limitation": "LIM",
    "Fixed": "FIX",
}
MODE_INTERNAL_TO_DISPLAY = {v: k for k, v in MODE_DISPLAY_TO_INTERNAL.items()}


class RangeRow(QObject):
    """Builds the cells of one Measurement-Ranges row and exposes them via
    ``cells`` for a TableGrid to mount.  Not a widget itself, so the cells
    live directly in the shared grid and align with the header."""

    changed = Signal(str, object)  # (mode, value)

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        unit_mode: str,
        instrument_model: str,
        initial_mode: str = "AUTO",
        initial_value: Optional[float] = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.unit_mode = unit_mode
        self.instrument_model = instrument_model

        # Determine range options
        self.options = self._get_options()

        # 1. Badge / Name
        self.badge = _create_unit_badge(unit_id)

        # 2. Mode combo box
        self.mode_combo = QComboBox()
        self.mode_combo.setStyleSheet(unit_card_combo_stylesheet())
        for label in ["Automatic", "Automatic with limitation", "Fixed"]:
            self.mode_combo.addItem(label)

        display_mode = MODE_INTERNAL_TO_DISPLAY.get(initial_mode, "Automatic")
        self.mode_combo.setCurrentText(display_mode)

        # 3. Value combo box
        self.val_combo = QComboBox()
        self.val_combo.setStyleSheet(unit_card_combo_stylesheet())

        self._repopulate_values(initial_value)

        # Connect signals
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.val_combo.currentIndexChanged.connect(self._on_value_changed)

        self.cells: List[TableCell] = [
            (self.badge, CELL_CENTER),
            (self.mode_combo, CELL_FILL),
            (self.val_combo, CELL_FILL),
        ]

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

        mode = MODE_DISPLAY_TO_INTERNAL.get(
            self.mode_combo.currentText(), "AUTO"
        )
        self.val_combo.setEnabled(mode in ("LIM", "FIX"))

    def _on_mode_changed(self, display_mode: str) -> None:
        mode = MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        self.val_combo.setEnabled(mode in ("LIM", "FIX"))
        self.changed.emit(mode, self.current_value())

    def _on_value_changed(self, idx: int) -> None:
        display_mode = self.mode_combo.currentText()
        mode = MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        self.changed.emit(mode, self.current_value())

    def current_value(self) -> Optional[float]:
        display_mode = self.mode_combo.currentText()
        mode = MODE_DISPLAY_TO_INTERNAL.get(display_mode, "AUTO")
        if mode == "AUTO":
            return None
        idx = self.val_combo.currentIndex()
        if 0 <= idx < len(self.options):
            return self.options[idx][1]
        return None


class RangesSection(SectionFrame):
    range_changed = Signal(str, str, object)  # (unit_id, mode, value)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Measurement Ranges",
            parent,
            doc_topic=DocTopic.MEASUREMENT_RANGES,
        )
        self._rows: Dict[str, RangeRow] = {}

    def display_ranges(
        self,
        active_channels: List[dict],
        instrument_model: str,
        ranges_config: Dict[str, dict],
    ) -> None:
        self._clear_body()
        self._rows.clear()

        eligible_channels = [
            ch for ch in active_channels if ch["unit_type"] in ("SMU", "VMU")
        ]

        if not eligible_channels:
            self.body().addWidget(
                _placeholder_label("No active measurement units (SMU/VMU).")
            )
            return

        # Column headers — the two data-entry columns share the surplus
        # width so the section fills out instead of clustering on the left.
        headers: List[TableHeader] = [
            ("Unit", CELL_CENTER),
            ("Range Mode", CELL_LEFT),
            ("Range Value", CELL_LEFT),
        ]
        table = TableGrid(headers, column_stretch={1: 3, 2: 2})

        for ch in eligible_channels:
            ch_id = ch["id"]
            r_data = ranges_config.get(ch_id, {})
            mode = r_data.get("mode", "AUTO")
            value = r_data.get("value")

            row = RangeRow(
                unit_id=ch_id,
                unit_type=ch.get("unit_type", "SMU"),
                unit_mode=ch.get("mode", ""),
                instrument_model=instrument_model,
                initial_mode=mode,
                initial_value=value,
                parent=table,
            )
            row.changed.connect(
                lambda m, v, cid=ch_id: self.range_changed.emit(cid, m, v)
            )
            self._rows[ch_id] = row
            table.add_row(row.cells)

        self.body().addWidget(table)


class ConstantRow(QObject):
    """Builds the cells of one Constant-Sources row and exposes them via
    ``cells`` for a TableGrid to mount."""

    source_changed = Signal(str, float)
    compliance_changed = Signal(str, float)

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        unit_mode: str,
        initial_source: float,
        initial_compliance: Optional[float] = None,
        interlock_open: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.unit_mode = unit_mode

        # 1. Badge / Name
        self.badge = _create_unit_badge(unit_id)

        # 2. Source input
        if unit_type == "VSU":
            min_s, max_s, unit_s = VSU_VOLTAGE_MIN, VSU_VOLTAGE_MAX, "V"
        elif unit_mode in ("V", "VPULSE"):
            if interlock_open:
                min_s, max_s = -VOLTAGE_ILOCK_MAX, VOLTAGE_ILOCK_MAX
            else:
                min_s, max_s = VOLTAGE_MIN, VOLTAGE_MAX
            unit_s = "V"
        else:
            min_s, max_s, unit_s = CURRENT_MIN, CURRENT_MAX, "A"

        self.source_edit = SciDoubleEdit(initial_source, min_s, max_s, unit_s)
        self.source_edit._edit.setToolTip(
            f"Range: {min_s:.3g} – {max_s:.3g} {unit_s}"
        )
        self.source_edit.value_committed.connect(
            lambda val: self.source_changed.emit(self.unit_id, val)
        )

        # 3. Compliance input (SMU only)
        if unit_type == "SMU":
            if unit_mode in ("V", "VPULSE"):
                min_c, max_c, unit_c = COMP_I_MIN, COMP_I_MAX, "A"
            else:
                min_c = COMP_V_MIN
                max_c = COMP_V_ILOCK_MAX if interlock_open else COMP_V_MAX
                unit_c = "V"

            comp_val = (
                initial_compliance if initial_compliance is not None else 0.01
            )
            self.compliance_edit = SciDoubleEdit(
                comp_val, min_c, max_c, unit_c
            )
            self.compliance_edit._edit.setToolTip(
                f"Range: {min_c:.3g} – {max_c:.3g} {unit_c}"
            )
            self.compliance_edit.value_committed.connect(
                lambda val: self.compliance_changed.emit(self.unit_id, val)
            )
            compliance_cell: TableCell = (self.compliance_edit, CELL_FILL)
        else:
            self.compliance_edit = None
            dash = QLabel("—")
            dash.setStyleSheet(form_label_stylesheet())
            dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
            compliance_cell = (dash, CELL_CENTER)

        self.cells: List[TableCell] = [
            (self.badge, CELL_CENTER),
            (self.source_edit, CELL_FILL),
            compliance_cell,
        ]


class ConstantsSection(SectionFrame):
    const_source_changed = Signal(str, float)
    const_compliance_changed = Signal(str, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Constant Sources",
            parent,
            doc_topic=DocTopic.CONSTANT_SOURCES,
        )
        self._rows: Dict[str, ConstantRow] = {}

    def display_constants(
        self,
        active_channels: List[dict],
        constants_config: Dict[str, dict],
        interlock_open: bool = False,
    ) -> None:
        self._clear_body()
        self._rows.clear()

        eligible_channels = [
            ch
            for ch in active_channels
            if ch.get("function") == "CONST"
            and ch.get("unit_type") in ("SMU", "VSU")
            and ch.get("mode") != "COMM"
        ]

        if not eligible_channels:
            self.body().addWidget(
                _placeholder_label("No constant source units configured.")
            )
            return

        # Column headers — the source and compliance columns share the
        # surplus width so the section fills out evenly.
        headers: List[TableHeader] = [
            ("Unit", CELL_CENTER),
            ("Constant Source", CELL_LEFT),
            ("Compliance Limit", CELL_LEFT),
        ]
        table = TableGrid(headers, column_stretch={1: 1, 2: 1})

        for ch in eligible_channels:
            ch_id = ch["id"]
            c_data = constants_config.get(ch_id, {})
            source_val = c_data.get("source", 0.0)
            comp_val = (
                c_data.get("compliance", 0.01)
                if ch.get("unit_type") == "SMU"
                else None
            )

            row = ConstantRow(
                unit_id=ch_id,
                unit_type=ch.get("unit_type", "SMU"),
                unit_mode=ch.get("mode", ""),
                initial_source=source_val,
                initial_compliance=comp_val,
                interlock_open=interlock_open,
                parent=table,
            )
            row.source_changed.connect(self.const_source_changed)
            row.compliance_changed.connect(self.const_compliance_changed)
            self._rows[ch_id] = row
            table.add_row(row.cells)

        self.body().addWidget(table)

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
                        f"{ch_id} Constant Compliance:"
                        " value is empty or invalid"
                    )
        return errors


class DisplayVarsSection(SectionFrame):
    var_toggled = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Display Variables",
            parent,
            doc_topic=DocTopic.DISPLAY_VARIABLES,
        )
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


# ── JSON preview dialog ─────────────────────────────────────────


class JsonPreviewDialog(QDialog):
    def __init__(
        self,
        json_str: str,
        parent: QWidget | None = None,
        title: str = "Generated JSON — Sweep Configuration",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
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
        QApplication.clipboard().setText(self._text.toPlainText())
