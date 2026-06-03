"""
views/pages/channels_page.py
-----------------------------
Channels configuration page — pure View layer.

Layout
------
┌─────────────────────────────────────────────────────┐
│  _ConfigPanel (fixed height, no scroll)             │
│   Instrument model | Measurement mode               │
│   GNDU to Common   | InLink Available               │
├─────────────────────────────────────────────────────┤
│  QScrollArea                                        │
│   ── SOURCE MONITOR UNITS ──────────────────────    │
│   [SMU1] [SMU2] [SMU3] [SMU4]                       │
│   ── VOLTAGE MONITOR UNITS ─────────────────────    │
│   [VMU1] [VMU2]          (hidden for 4155 models)   │
│   ── VOLTAGE SOURCE UNITS ──────────────────────    │
│   [VSU1] [VSU2]                                     │
└─────────────────────────────────────────────────────┘

MVP rules
---------
- No model imports (ChannelsConfig etc.) — view only receives/emits primitives.
- blockSignals(True/False) wraps every widget write in display_* methods to
  prevent re-entrant signal emission back to the presenter.
- All QSS comes from stylesheets.py; no hex literals appear here.
"""

from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.styles.stylesheets import (
    bottom_panel_stylesheet,
    channels_page_stylesheet,
    config_combo_stylesheet,
    config_panel_stylesheet,
    config_section_label_stylesheet,
    configure_measure_button_stylesheet,
    global_option_checkbox_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_disabled_stylesheet,
    unit_card_enabled_stylesheet,
    unit_card_line_edit_stylesheet,
    unit_card_row_label_stylesheet,
    unit_card_separator_stylesheet,
    unit_card_title_stylesheet,
    unit_enable_checkbox_stylesheet,
    unit_group_header_stylesheet,
    unit_group_separator_stylesheet,
    validation_status_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage

# ── Internal helpers ─────────────────────────────────────────────────────────

_NAME_VALIDATOR = QRegularExpressionValidator(
    QRegularExpression(r"[A-Za-z_][A-Za-z0-9_]{0,5}")
)
_CARD_WIDTH = 210
_LABEL_WIDTH = 68
_ROW_HEIGHT = 26


def _set_combo(combo: QComboBox, value: str) -> None:
    """
    Select the item whose userData matches *value* without emitting signals.
    """
    combo.blockSignals(True)
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    combo.blockSignals(False)


def _populate_combo(
    combo: QComboBox,
    items: List[str],  # display text == userData for enum values
    current: str = "",
) -> None:
    """Rebuild combo items and restore selection, signal-free."""
    combo.blockSignals(True)
    combo.clear()
    for item in items:
        combo.addItem(item, item)
    idx = combo.findData(current)
    combo.setCurrentIndex(max(idx, 0))
    combo.blockSignals(False)


def _set_check(cb: QCheckBox, state: bool) -> None:
    cb.blockSignals(True)
    cb.setChecked(state)
    cb.blockSignals(False)


def _set_text(edit: QLineEdit, text: str) -> None:
    edit.blockSignals(True)
    edit.setText(text)
    edit.blockSignals(False)


def _make_row(
    label_text: str,
    control: QWidget,
    label_width: int = _LABEL_WIDTH,
) -> QWidget:
    """Return a fixed-label + control row widget."""
    row = QWidget()
    row.setFixedHeight(_ROW_HEIGHT)
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(label_width)
    lbl.setStyleSheet(unit_card_row_label_stylesheet())
    h.addWidget(lbl)
    h.addWidget(control, stretch=1)
    return row


def _make_name_edit() -> QLineEdit:
    edit = QLineEdit()
    edit.setMaxLength(6)
    edit.setValidator(_NAME_VALIDATOR)
    edit.setStyleSheet(unit_card_line_edit_stylesheet())
    return edit


# ── Unit cards ───────────────────────────────────────────────────────────────


class SMUCard(QFrame):
    """
    Configuration card for one SMU channel.

    Signals (user intents → ChannelsPageView → ChannelsPresenter)
    """

    enabled_toggled = Signal(bool)
    mode_changed = Signal(str)  # SMUMode.value
    function_changed = Signal(str)  # UnitFunction.value
    vname_changed = Signal(str)
    iname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._enabled = True
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("unit_card")
        self.setFixedWidth(_CARD_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        self._setup_ui()
        self._apply_styles()
        self._wire_internal()

    # ── Display API ──────────────────────────────────────────────────────────

    def display_state(
        self,
        enabled: bool,
        mode: str,
        function: str,
        voltage_name: str,
        current_name: str,
    ) -> None:
        self._enabled = enabled
        _set_check(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo(self._mode_combo, mode)
        _set_combo(self._func_combo, function)
        _set_text(self._vname_edit, voltage_name)
        _set_text(self._iname_edit, current_name)
        self._refresh_card_style(enabled)
        if enabled:
            self._enable_cb.setText(f"SMU{self._index}")
        else:
            self._enable_cb.setText(f"SMU{self._index} (disabled)")

    def display_available_functions(self, functions: List[str]) -> None:
        current = self._func_combo.currentData() or ""
        _populate_combo(self._func_combo, functions, current)

    def display_function_locked(self, locked: bool) -> None:
        """Disable function combo when SMU mode is COMM."""
        self._func_combo.setEnabled(not locked)
        if locked:
            _set_combo(self._func_combo, "CONST")

    def display_mode_usable(self, usable: bool) -> None:
        """Called for mode-based restrictions (not user toggle)."""
        self.setEnabled(usable)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Header: enable LED + title
        header = QWidget()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.setSpacing(8)
        self._enable_cb = QCheckBox(f"SMU{self._index}")
        self._enable_cb.setChecked(True)
        hh.addWidget(self._enable_cb)
        hh.addStretch()
        root.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(unit_card_separator_stylesheet())
        root.addWidget(sep)

        # Content (disabled when card is user-disabled)
        self._content = QWidget()
        cv = QVBoxLayout(self._content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(4)

        self._mode_combo = QComboBox()
        for m in ("V", "I", "VPULSE", "IPULSE", "COMM"):
            self._mode_combo.addItem(m, m)
        cv.addWidget(_make_row("Mode", self._mode_combo))

        self._func_combo = QComboBox()
        for f in ("CONST", "VAR1", "VAR2", "VAR1'"):
            self._func_combo.addItem(f, f)
        cv.addWidget(_make_row("Function", self._func_combo))

        self._vname_edit = _make_name_edit()
        cv.addWidget(_make_row("V-Name", self._vname_edit))

        self._iname_edit = _make_name_edit()
        cv.addWidget(_make_row("I-Name", self._iname_edit))

        root.addWidget(self._content)

    def _apply_styles(self) -> None:
        self.setStyleSheet(unit_card_enabled_stylesheet())
        self._enable_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_internal(self) -> None:
        self._enable_cb.toggled.connect(self._on_enable_toggled)
        self._mode_combo.currentTextChanged.connect(self.mode_changed)
        self._func_combo.currentTextChanged.connect(self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)
        self._iname_edit.textChanged.connect(self.iname_changed)

    def _on_enable_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self._content.setEnabled(checked)
        self._refresh_card_style(checked)
        if checked:
            self._enable_cb.setText(f"SMU{self._index}")
        else:
            self._enable_cb.setText(f"SMU{self._index} (disabled)")
        self.enabled_toggled.emit(checked)

    def _refresh_card_style(self, enabled: bool) -> None:
        self.setStyleSheet(
            unit_card_enabled_stylesheet(self._hovered)
            if enabled
            else unit_card_disabled_stylesheet(self._hovered)
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._refresh_card_style(self._enabled)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._refresh_card_style(self._enabled)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._enable_cb.underMouse()
        ):
            self._enable_cb.setChecked(not self._enabled)
        super().mousePressEvent(event)


class VMUCard(QFrame):
    """Configuration card for one VMU channel."""

    enabled_toggled = Signal(bool)
    mode_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._enabled = True
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("unit_card")
        self.setFixedWidth(_CARD_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        self._setup_ui()
        self._apply_styles()
        self._wire_internal()

    def display_state(
        self,
        enabled: bool,
        mode: str,
        voltage_name: str,
    ) -> None:
        self._enabled = enabled
        _set_check(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo(self._mode_combo, mode)
        _set_text(self._vname_edit, voltage_name)
        self._refresh_card_style(enabled)
        if enabled:
            self._enable_cb.setText(f"VMU{self._index}")
        else:
            self._enable_cb.setText(f"VMU{self._index} (disabled)")

    def display_mode_usable(self, usable: bool) -> None:
        """Called when measurement mode disables VMU (Sampling / QSCV)."""
        self.setEnabled(usable)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        header = QWidget()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.setSpacing(8)
        self._enable_cb = QCheckBox(f"VMU{self._index}")
        self._enable_cb.setChecked(True)
        hh.addWidget(self._enable_cb)
        hh.addStretch()
        root.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(unit_card_separator_stylesheet())
        root.addWidget(sep)

        self._content = QWidget()
        cv = QVBoxLayout(self._content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(4)

        self._mode_combo = QComboBox()
        for m in ("V", "DVOLT"):
            self._mode_combo.addItem(m, m)
        cv.addWidget(_make_row("Mode", self._mode_combo))

        self._vname_edit = _make_name_edit()
        cv.addWidget(_make_row("V-Name", self._vname_edit))

        # Informational label — VMUs have no sweep function
        note = QLabel("Monitor only — no function")
        note.setStyleSheet(
            f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
            "background: transparent; font-style: italic;"
        )
        cv.addWidget(note)

        root.addWidget(self._content)

    def _apply_styles(self) -> None:
        self.setStyleSheet(unit_card_enabled_stylesheet())
        self._enable_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_internal(self) -> None:
        self._enable_cb.toggled.connect(self._on_enable_toggled)
        self._mode_combo.currentTextChanged.connect(self.mode_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)

    def _on_enable_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self._content.setEnabled(checked)
        self._refresh_card_style(checked)
        if checked:
            self._enable_cb.setText(f"VMU{self._index}")
        else:
            self._enable_cb.setText(f"VMU{self._index} (disabled)")
        self.enabled_toggled.emit(checked)

    def _refresh_card_style(self, enabled: bool) -> None:
        self.setStyleSheet(
            unit_card_enabled_stylesheet(self._hovered)
            if enabled
            else unit_card_disabled_stylesheet(self._hovered)
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._refresh_card_style(self._enabled)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._refresh_card_style(self._enabled)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._enable_cb.underMouse()
        ):
            self._enable_cb.setChecked(not self._enabled)
        super().mousePressEvent(event)


class VSUCard(QFrame):
    """Configuration card for one VSU channel."""

    enabled_toggled = Signal(bool)
    function_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index
        self._enabled = True
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("unit_card")
        self.setFixedWidth(_CARD_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum
        )
        self._setup_ui()
        self._apply_styles()
        self._wire_internal()

    def display_state(
        self,
        enabled: bool,
        function: str,
        voltage_name: str,
    ) -> None:
        self._enabled = enabled
        _set_check(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo(self._func_combo, function)
        _set_text(self._vname_edit, voltage_name)
        self._refresh_card_style(enabled)
        if enabled:
            self._enable_cb.setText(f"VSU{self._index}")
        else:
            self._enable_cb.setText(f"VSU{self._index} (disabled)")

    def display_available_functions(self, functions: List[str]) -> None:
        current = self._func_combo.currentData() or ""
        _populate_combo(self._func_combo, functions, current)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        header = QWidget()
        hh = QHBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.setSpacing(8)
        self._enable_cb = QCheckBox(f"VSU{self._index}")
        self._enable_cb.setChecked(True)
        hh.addWidget(self._enable_cb)
        hh.addStretch()

        # VSU mode is always V — show as a static badge
        mode_badge = QLabel("V")
        mode_badge.setStyleSheet(
            f"color: {P.ACCENT_HOVER}; font-size: {P.FONT_SIZE_XS}; "
            f"font-weight: bold; background: {P.ACCENT_MUTED}; "
            f"padding: 1px 6px; border-radius: {P.RADIUS_SM};"
        )
        hh.addWidget(mode_badge)

        root.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(unit_card_separator_stylesheet())
        root.addWidget(sep)

        self._content = QWidget()
        cv = QVBoxLayout(self._content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(4)

        self._func_combo = QComboBox()
        for f in ("CONST", "VAR1", "VAR2", "VAR1'"):
            self._func_combo.addItem(f, f)
        cv.addWidget(_make_row("Function", self._func_combo))

        self._vname_edit = _make_name_edit()
        cv.addWidget(_make_row("V-Name", self._vname_edit))

        root.addWidget(self._content)

    def _apply_styles(self) -> None:
        self.setStyleSheet(unit_card_enabled_stylesheet())
        self._enable_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_internal(self) -> None:
        self._enable_cb.toggled.connect(self._on_enable_toggled)
        self._func_combo.currentTextChanged.connect(self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)

    def _on_enable_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self._content.setEnabled(checked)
        self._refresh_card_style(checked)
        if checked:
            self._enable_cb.setText(f"VSU{self._index}")
        else:
            self._enable_cb.setText(f"VSU{self._index} (disabled)")
        self.enabled_toggled.emit(checked)

    def _refresh_card_style(self, enabled: bool) -> None:
        self.setStyleSheet(
            unit_card_enabled_stylesheet(self._hovered)
            if enabled
            else unit_card_disabled_stylesheet(self._hovered)
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._refresh_card_style(self._enabled)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._refresh_card_style(self._enabled)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._enable_cb.underMouse()
        ):
            self._enable_cb.setChecked(not self._enabled)
        super().mousePressEvent(event)


# ── Configuration panel ──────────────────────────────────────────────────────


class _ConfigPanel(QFrame):
    """
    Fixed top panel: instrument model selector, measurement mode selector.
    """

    instrument_model_changed = Signal(str)  # InstrumentModel.value
    measurement_mode_changed = Signal(str)  # MeasurementMode.value

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("config_panel")
        self._setup_ui()
        self._apply_styles()
        self._wire_internal()

    # ── Display API ──────────────────────────────────────────────────────────

    def display_available_modes(self, modes: List[str]) -> None:
        current = self._mode_combo.currentData() or ""
        _populate_combo(self._mode_combo, modes, current)

    def display_state(
        self,
        model: str,
        mode: str,
    ) -> None:
        _set_combo(self._model_combo, model)
        _set_combo(self._mode_combo, mode)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(14)

        # ── Row 1: selectors ─────────────────────────────────────────────────
        selectors_row = QWidget()
        sr = QHBoxLayout(selectors_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(40)

        # Instrument model
        model_col = QVBoxLayout()
        model_col.setSpacing(4)
        model_lbl = QLabel("INSTRUMENT MODEL")
        model_lbl.setStyleSheet(config_section_label_stylesheet())
        model_col.addWidget(model_lbl)
        self._model_combo = QComboBox()
        for m in ("4155B", "4156B", "4155C", "4156C"):
            self._model_combo.addItem(m, m)
        self._model_combo.setCurrentIndex(2)  # default: 4155C
        model_col.addWidget(self._model_combo)
        sr.addLayout(model_col)

        # Measurement mode
        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_lbl = QLabel("MEASUREMENT MODE")
        mode_lbl.setStyleSheet(config_section_label_stylesheet())
        mode_col.addWidget(mode_lbl)
        self._mode_combo = QComboBox()
        for mo in ("SWEEP", "SAMPLING", "QSCV"):
            self._mode_combo.addItem(mo, mo)
        mode_col.addWidget(self._mode_combo)
        sr.addLayout(mode_col)

        sr.addStretch()
        root.addWidget(selectors_row)

    def _apply_styles(self) -> None:
        self.setStyleSheet(config_panel_stylesheet())
        self._model_combo.setStyleSheet(config_combo_stylesheet())
        self._mode_combo.setStyleSheet(config_combo_stylesheet())

    def _wire_internal(self) -> None:
        self._model_combo.currentTextChanged.connect(
            self.instrument_model_changed
        )
        self._mode_combo.currentTextChanged.connect(
            self.measurement_mode_changed
        )


# ── Unit group container ─────────────────────────────────────────────────────


def _make_unit_group(title: str, cards: List[QFrame]) -> QWidget:
    """Return a titled section containing a horizontal row of cards."""
    group = QWidget()
    v = QVBoxLayout(group)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(10)

    # Header row: label + horizontal rule
    header_row = QWidget()
    hr = QHBoxLayout(header_row)
    hr.setContentsMargins(0, 0, 0, 0)
    hr.setSpacing(12)

    lbl = QLabel(title)
    lbl.setStyleSheet(unit_group_header_stylesheet())
    hr.addWidget(lbl)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(unit_group_separator_stylesheet())
    hr.addWidget(sep, stretch=1)
    v.addWidget(header_row)

    # Card row
    cards_widget = QWidget()
    ch = QHBoxLayout(cards_widget)
    ch.setContentsMargins(0, 0, 0, 0)
    ch.setSpacing(12)
    ch.setAlignment(Qt.AlignmentFlag.AlignLeft)
    for card in cards:
        ch.addWidget(card)
    v.addWidget(cards_widget)

    return group


# ── Main page view ───────────────────────────────────────────────────────────


class ChannelsPageView(BasePage):
    """
    Channels configuration page — composes _ConfigPanel and unit card groups.

    User-intent signals (→ ChannelsPresenter)
    ------------------------------------------
    instrument_model_changed(str)
    measurement_mode_changed(str)
    gndu_changed(bool)
    inlink_changed(bool)
    smu_enabled_changed(int, bool)      index, value
    smu_mode_changed(int, str)
    smu_function_changed(int, str)
    smu_vname_changed(int, str)
    smu_iname_changed(int, str)
    vmu_enabled_changed(int, bool)
    vmu_mode_changed(int, str)
    vmu_vname_changed(int, str)
    vsu_enabled_changed(int, bool)
    vsu_function_changed(int, str)
    vsu_vname_changed(int, str)

    Display methods (← ChannelsPresenter)
    ---------------------------------------
    display_config(...)                 full page refresh from config snapshot
    display_available_modes(modes)      update mode combo options
    display_vmu_section_visible(bool)   show/hide VMU group
    display_smu_functions(idx, fns)     update one SMU's function combo
    display_smu_function_locked(idx, b) lock/unlock function combo (COMM mode)
    display_vmu_card_usable(idx, bool)  enable/disable one VMU (mode-based)
    display_vsu_functions(idx, fns)     update one VSU's function combo
    """

    # ── User-intent signals ──────────────────────────────────────────────────
    instrument_model_changed = Signal(str)
    measurement_mode_changed = Signal(str)
    gndu_changed = Signal(bool)
    inlink_changed = Signal(bool)

    smu_enabled_changed = Signal(int, bool)
    smu_mode_changed = Signal(int, str)
    smu_function_changed = Signal(int, str)
    smu_vname_changed = Signal(int, str)
    smu_iname_changed = Signal(int, str)

    vmu_enabled_changed = Signal(int, bool)
    vmu_mode_changed = Signal(int, str)
    vmu_vname_changed = Signal(int, str)

    vsu_enabled_changed = Signal(int, bool)
    vsu_function_changed = Signal(int, str)
    vsu_vname_changed = Signal(int, str)
    configure_measure_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._smu_cards: Dict[int, SMUCard] = {}
        self._vmu_cards: Dict[int, VMUCard] = {}
        self._vsu_cards: Dict[int, VSUCard] = {}
        self._setup_ui()
        self._wire_cards()

    # ── Display API (called by ChannelsPresenter) ────────────────────────────

    def display_config(
        self,
        model: str,
        mode: str,
        gndu: bool,
        inlink: bool,
        smu_states: Dict[int, dict],
        vmu_states: Dict[int, dict],
        vsu_states: Dict[int, dict],
    ) -> None:
        """
        Full snapshot refresh.  All dicts contain plain-string field values.
        """
        self._config_panel.display_state(model, mode)
        _set_check(self._gndu_cb, gndu)
        _set_check(self._inlink_cb, inlink)
        for idx, state in smu_states.items():
            self._smu_cards[idx].display_state(**state)
        for idx, state in vmu_states.items():
            self._vmu_cards[idx].display_state(**state)
        for idx, state in vsu_states.items():
            self._vsu_cards[idx].display_state(**state)

    def display_validation_status(self, is_valid: bool, message: str) -> None:
        """Update the bottom panel validation status label."""
        self._configure_btn.setEnabled(is_valid)
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

    def display_available_modes(self, modes: List[str]) -> None:
        self._config_panel.display_available_modes(modes)

    def display_vmu_section_visible(self, visible: bool) -> None:
        self._vmu_group.setVisible(visible)

    def display_smu_functions(self, index: int, functions: List[str]) -> None:
        self._smu_cards[index].display_available_functions(functions)

    def display_smu_function_locked(self, index: int, locked: bool) -> None:
        self._smu_cards[index].display_function_locked(locked)

    def display_vmu_card_usable(self, index: int, usable: bool) -> None:
        self._vmu_cards[index].display_mode_usable(usable)

    def display_vsu_functions(self, index: int, functions: List[str]) -> None:
        self._vsu_cards[index].display_available_functions(functions)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet(channels_page_stylesheet())

        # Fixed config panel
        self._config_panel = _ConfigPanel()
        root.addWidget(self._config_panel)

        # Scrollable units area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        units_widget = QWidget()
        units_widget.setStyleSheet(f"background-color: {P.BG_DEEP};")
        uv = QVBoxLayout(units_widget)
        uv.setContentsMargins(24, 24, 24, 32)
        uv.setSpacing(28)
        uv.setAlignment(Qt.AlignmentFlag.AlignTop)

        # SMU section (always visible)
        smu_cards = []
        for i in range(1, 5):
            card = SMUCard(i)
            self._smu_cards[i] = card
            smu_cards.append(card)
        uv.addWidget(
            _make_unit_group("SOURCE MONITOR UNITS  (SMU)", smu_cards)
        )

        # VMU section (hidden for 4155 models)
        vmu_cards = []
        for i in range(1, 3):
            card = VMUCard(i)
            self._vmu_cards[i] = card
            vmu_cards.append(card)
        self._vmu_group = _make_unit_group("VOLTAGE MONITOR UNITS ", vmu_cards)
        uv.addWidget(self._vmu_group)

        # VSU section (always visible)
        vsu_cards = []
        for i in range(1, 3):
            card = VSUCard(i)
            self._vsu_cards[i] = card
            vsu_cards.append(card)
        uv.addWidget(
            _make_unit_group("VOLTAGE SOURCE UNITS  (VSU)", vsu_cards)
        )

        scroll.setWidget(units_widget)
        root.addWidget(scroll, stretch=1)

        # Bottom panel
        self._bottom_panel = QFrame()
        self._bottom_panel.setObjectName("bottom_panel")
        self._bottom_panel.setStyleSheet(bottom_panel_stylesheet())

        bp_layout = QHBoxLayout(self._bottom_panel)
        bp_layout.setContentsMargins(24, 16, 24, 16)
        bp_layout.setSpacing(32)

        self._gndu_cb = QCheckBox("GNDU Connected to Common")
        self._gndu_cb.setChecked(True)
        self._gndu_cb.setStyleSheet(global_option_checkbox_stylesheet())
        bp_layout.addWidget(self._gndu_cb)

        self._inlink_cb = QCheckBox("InLink Available")
        self._inlink_cb.setChecked(False)
        self._inlink_cb.setStyleSheet(global_option_checkbox_stylesheet())
        bp_layout.addWidget(self._inlink_cb)

        self._validation_lbl = QLabel()
        bp_layout.addWidget(self._validation_lbl)

        bp_layout.addStretch()

        self._configure_btn = QPushButton("⚙️  Configure Measure")
        self._configure_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._configure_btn.setStyleSheet(
            configure_measure_button_stylesheet()
        )
        self._configure_btn.setFixedHeight(36)
        bp_layout.addWidget(self._configure_btn)

        root.addWidget(self._bottom_panel)

    def _wire_cards(self) -> None:
        """Forward each card signal as an indexed page-level signal."""
        # Config panel
        self._config_panel.instrument_model_changed.connect(
            self.instrument_model_changed
        )
        self._config_panel.measurement_mode_changed.connect(
            self.measurement_mode_changed
        )
        self._gndu_cb.toggled.connect(self.gndu_changed)
        self._inlink_cb.toggled.connect(self.inlink_changed)

        # SMU cards
        for idx, card in self._smu_cards.items():
            card.enabled_toggled.connect(
                lambda v, i=idx: self.smu_enabled_changed.emit(i, v)
            )
            card.mode_changed.connect(
                lambda v, i=idx: self.smu_mode_changed.emit(i, v)
            )
            card.function_changed.connect(
                lambda v, i=idx: self.smu_function_changed.emit(i, v)
            )
            card.vname_changed.connect(
                lambda v, i=idx: self.smu_vname_changed.emit(i, v)
            )
            card.iname_changed.connect(
                lambda v, i=idx: self.smu_iname_changed.emit(i, v)
            )

        # VMU cards
        for idx, card in self._vmu_cards.items():
            card.enabled_toggled.connect(
                lambda v, i=idx: self.vmu_enabled_changed.emit(i, v)
            )
            card.mode_changed.connect(
                lambda v, i=idx: self.vmu_mode_changed.emit(i, v)
            )
            card.vname_changed.connect(
                lambda v, i=idx: self.vmu_vname_changed.emit(i, v)
            )

        # VSU cards
        for idx, card in self._vsu_cards.items():
            card.enabled_toggled.connect(
                lambda v, i=idx: self.vsu_enabled_changed.emit(i, v)
            )
            card.function_changed.connect(
                lambda v, i=idx: self.vsu_function_changed.emit(i, v)
            )
            card.vname_changed.connect(
                lambda v, i=idx: self.vsu_vname_changed.emit(i, v)
            )

        self._configure_btn.clicked.connect(self.configure_measure_clicked)
