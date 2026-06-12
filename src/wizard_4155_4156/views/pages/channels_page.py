"""
views/pages/channels_page.py
-----------------------------
Channels configuration page — pure View layer.

Layout
------
┌─────────────────────────────────────────────────────┐
│  _ConfigPanel (fixed height, no scroll)             │
│   Instrument model | Measurement mode               │
│   Common to Ground | Interlock Open                 │
├─────────────────────────────────────────────────────┤
│  QScrollArea                                        │
│   ── SOURCE MONITOR UNITS ──────────────────────    │
│   [SMU1] [SMU2] [SMU3] [SMU4]                       │
│   ── VOLTAGE MONITOR UNITS ─────────────────────    │
│   [VMU1] [VMU2]                                     │
│   ── VOLTAGE SOURCE UNITS ──────────────────────    │
│   [VSU1] [VSU2]                                     │
└─────────────────────────────────────────────────────┘

MVP rules
---------
- No model imports (ChannelsConfig etc.) — view only receives/emits primitives.
- QSignalBlocker wraps every widget write in display_* methods to prevent
  re-entrant signal emission back to the presenter.
- All QSS comes from stylesheets.py; no hex literals appear here.
"""

from __future__ import annotations

from typing import override

from PySide6.QtCore import QRegularExpression, QSignalBlocker, Qt, Signal, Slot
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

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
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
    unit_card_mode_badge_stylesheet,
    unit_card_note_stylesheet,
    unit_card_row_label_stylesheet,
    unit_card_separator_stylesheet,
    unit_enable_checkbox_stylesheet,
    unit_group_header_stylesheet,
    unit_group_separator_stylesheet,
    units_container_stylesheet,
    units_scroll_area_stylesheet,
    units_scroll_viewport_stylesheet,
    validation_status_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage

# ── Internal helpers ─────────────────────────────────────────────────────────
_NAME_VALIDATOR = QRegularExpressionValidator(
    QRegularExpression(r"[A-Za-z_][A-Za-z0-9_]{0,5}")
)
_CARD_WIDTH = 210
_LABEL_WIDTH = 68
_ROW_HEIGHT = 26


def _set_combo_signal_free(combo: QComboBox, value: str) -> None:
    with QSignalBlocker(combo):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)


def _populate_combo_signal_free(
    combo: QComboBox,
    items: list[str],  # display text == userData for enum values
    current: str = "",
) -> None:
    with QSignalBlocker(combo):
        combo.clear()
        for item in items:
            combo.addItem(item, item)
        idx = combo.findData(current)
        combo.setCurrentIndex(max(idx, 0))


def _set_checkbox_signal_free(checkbox: QCheckBox, state: bool) -> None:
    with QSignalBlocker(checkbox):
        checkbox.setChecked(state)


def _set_linetxt_signal_free(linetxt: QLineEdit, text: str) -> None:
    with QSignalBlocker(linetxt):
        linetxt.setText(text)


def _make_row(
    label_text: str,
    control: QWidget,
    label_width: int = _LABEL_WIDTH,
) -> QWidget:
    """Return a fixed-label + control row widget."""
    row = QWidget()
    row.setFixedHeight(_ROW_HEIGHT)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    label = QLabel(label_text)
    label.setFixedWidth(label_width)
    # TODO: Correct background color
    label.setStyleSheet(unit_card_row_label_stylesheet())
    row_layout.addWidget(label)
    row_layout.addWidget(control, stretch=1)
    return row


def _make_name_edit() -> QLineEdit:
    edit = QLineEdit()
    edit.setMaxLength(6)
    edit.setValidator(_NAME_VALIDATOR)
    # TODO: Correct background color
    edit.setStyleSheet(unit_card_line_edit_stylesheet())
    return edit


# ── Unit cards ───────────────────────────────────────────────────────────────
class _BaseUnitCard(QFrame):
    """
    Shared shell for SMU/VMU/VSU configuration cards.

    Owns the common card chrome (header checkbox, separator, content
    container), hover/enable styling, and the enable-toggle behavior.
    Subclasses declare their own user-intent signals and fill in their
    specific rows via _setup_content(); optional hooks _extend_header(),
    _apply_content_styles() and _wire_content() cover the rest.
    """

    enabled_toggled = Signal(bool)

    def __init__(
        self,
        prefix: str,
        index: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._prefix = prefix
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

    def display_mode_usable(self, usable: bool) -> None:
        """Enable/disable the whole card from mode-based restrictions."""
        self.setEnabled(usable)

    # ── Construction ─────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Header: enable checkbox + optional trailing widgets
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self._enable_cb = QCheckBox(f"{self._prefix}{self._index}")
        self._enable_cb.setChecked(True)
        header_layout.addWidget(self._enable_cb)
        header_layout.addStretch()
        self._extend_header(header_layout)
        root.addWidget(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(unit_card_separator_stylesheet())
        root.addWidget(separator)

        # Content is disabled when card is user-disabled
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        self._setup_content(content_layout)
        root.addWidget(self._content)

    def _extend_header(self, header_layout: QHBoxLayout) -> None:
        """Hook: append trailing header widgets (e.g. a static badge)."""

    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        """Build the card's specific rows into the content layout."""
        raise NotImplementedError

    def _apply_styles(self) -> None:
        self.setStyleSheet(unit_card_enabled_stylesheet())
        self._enable_cb.setStyleSheet(unit_enable_checkbox_stylesheet())
        self._apply_content_styles()

    def _apply_content_styles(self) -> None:
        """Hook: style content-specific widgets (combos)."""

    def _wire_internal(self) -> None:
        self._enable_cb.toggled.connect(self._on_enable_toggled)
        self._wire_content()

    def _wire_content(self) -> None:
        """Hook: wire content-specific widget signals."""

    # ── Shared behavior ──────────────────────────────────────────────────────

    def _update_enable_label(self, enabled: bool) -> None:
        label = f"{self._prefix}{self._index}"
        self._enable_cb.setText(label if enabled else f"{label} (disabled)")

    @Slot(bool)
    def _on_enable_toggled(self, checked: bool) -> None:
        self._enabled = checked
        self._content.setEnabled(checked)
        self._refresh_card_style(checked)
        self._update_enable_label(checked)
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


class SMUCard(_BaseUnitCard):
    mode_changed = Signal(str)  # SMUMode.value
    function_changed = Signal(str)  # UnitFunction.value
    vname_changed = Signal(str)
    iname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__("SMU", index, parent)

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
        _set_checkbox_signal_free(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo_signal_free(self._mode_combo, mode)
        _set_combo_signal_free(self._func_combo, function)
        _set_linetxt_signal_free(self._vname_edit, voltage_name)
        _set_linetxt_signal_free(self._iname_edit, current_name)
        self._refresh_card_style(enabled)
        self._update_enable_label(enabled)

    def display_available_functions(self, functions: list[str]) -> None:
        current = self._func_combo.currentData() or ""
        _populate_combo_signal_free(self._func_combo, functions, current)

    def display_function_locked(self, locked: bool) -> None:
        """Disable function combo when SMU mode is COMM."""
        self._func_combo.setEnabled(not locked)
        if locked:
            _set_combo_signal_free(self._func_combo, "CONST")

    # ── Construction ─────────────────────────────────────────────────────────

    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._mode_combo = QComboBox()
        for mode_value in ("V", "I", "VPULSE", "IPULSE", "COMM"):
            self._mode_combo.addItem(mode_value, mode_value)
        content_layout.addWidget(_make_row("Mode", self._mode_combo))

        self._func_combo = QComboBox()
        for function_value in ("CONST", "VAR1", "VAR2", "VAR1'"):
            self._func_combo.addItem(function_value, function_value)
        content_layout.addWidget(_make_row("Function", self._func_combo))

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(_make_row("V-Name", self._vname_edit))

        self._iname_edit = _make_name_edit()
        content_layout.addWidget(_make_row("I-Name", self._iname_edit))

    def _apply_content_styles(self) -> None:
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        self._mode_combo.currentTextChanged.connect(self.mode_changed)
        self._func_combo.currentTextChanged.connect(self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)
        self._iname_edit.textChanged.connect(self.iname_changed)


class VMUCard(_BaseUnitCard):
    mode_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__("VMU", index, parent)

    # ── Display API ──────────────────────────────────────────────────────────
    def display_state(
        self,
        enabled: bool,
        mode: str,
        voltage_name: str,
    ) -> None:
        self._enabled = enabled
        _set_checkbox_signal_free(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo_signal_free(self._mode_combo, mode)
        _set_linetxt_signal_free(self._vname_edit, voltage_name)
        self._refresh_card_style(enabled)
        self._update_enable_label(enabled)

    # ── Private ──────────────────────────────────────────────────────────
    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._mode_combo = QComboBox()
        for mode_value in ("V", "DVOLT"):
            self._mode_combo.addItem(mode_value, mode_value)
        content_layout.addWidget(_make_row("Mode", self._mode_combo))

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(_make_row("V-Name", self._vname_edit))

        # Informational label — VMUs have no sweep function
        note = QLabel("Monitor only — no function")
        note.setStyleSheet(unit_card_note_stylesheet())
        content_layout.addWidget(note)

    def _apply_content_styles(self) -> None:
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        self._mode_combo.currentTextChanged.connect(self.mode_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)


class VSUCard(_BaseUnitCard):
    function_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__("VSU", index, parent)

    def display_state(
        self,
        enabled: bool,
        function: str,
        voltage_name: str,
    ) -> None:
        self._enabled = enabled
        _set_checkbox_signal_free(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo_signal_free(self._func_combo, function)
        _set_linetxt_signal_free(self._vname_edit, voltage_name)
        self._refresh_card_style(enabled)
        self._update_enable_label(enabled)

    def display_available_functions(self, functions: list[str]) -> None:
        current = self._func_combo.currentData() or ""
        _populate_combo_signal_free(self._func_combo, functions, current)

    @override
    def _extend_header(self, header_layout: QHBoxLayout) -> None:
        # VSU mode is always V — show as a static badge
        mode_badge = QLabel("V")
        mode_badge.setStyleSheet(unit_card_mode_badge_stylesheet())
        header_layout.addWidget(mode_badge)

    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._func_combo = QComboBox()
        for function_value in ("CONST", "VAR1", "VAR2", "VAR1'"):
            self._func_combo.addItem(function_value, function_value)
        content_layout.addWidget(_make_row("Function", self._func_combo))

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(_make_row("V-Name", self._vname_edit))

    def _apply_content_styles(self) -> None:
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        self._func_combo.currentTextChanged.connect(self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)


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

    def display_available_modes(self, modes: list[str]) -> None:
        current = self._mode_combo.currentData() or ""
        _populate_combo_signal_free(self._mode_combo, modes, current)

    def display_state(
        self,
        model: str,
        mode: str,
    ) -> None:
        _set_combo_signal_free(self._model_combo, model)
        _set_combo_signal_free(self._mode_combo, mode)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(14)

        # ── Row 1: selectors ─────────────────────────────────────────────────
        selectors_row = QWidget()
        selectors_layout = QHBoxLayout(selectors_row)
        selectors_layout.setContentsMargins(0, 0, 0, 0)
        selectors_layout.setSpacing(40)

        # Instrument model
        model_col = QVBoxLayout()
        model_col.setSpacing(4)
        model_label = QLabel("INSTRUMENT MODEL")
        model_label.setStyleSheet(config_section_label_stylesheet())
        model_col.addWidget(model_label)
        self._model_combo = QComboBox()
        for model_value in ("4155B", "4156B", "4155C", "4156C"):
            self._model_combo.addItem(model_value, model_value)
        # No hardcoded default here: the presenter pushes the authoritative
        # model on init via display_state (passive-view contract).
        model_col.addWidget(self._model_combo)
        selectors_layout.addLayout(model_col)

        # Measurement mode
        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_label = QLabel("MEASUREMENT MODE")
        mode_label.setStyleSheet(config_section_label_stylesheet())
        mode_col.addWidget(mode_label)
        self._mode_combo = QComboBox()
        for mode_value in ("SWEEP", "SAMPLING", "QSCV"):
            self._mode_combo.addItem(mode_value, mode_value)
        mode_col.addWidget(self._mode_combo)
        selectors_layout.addLayout(mode_col)

        selectors_layout.addStretch()
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


def _make_unit_group(title: str, cards: list[QFrame]) -> QWidget:
    """Return a titled section containing a horizontal row of cards."""
    group = QWidget()
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(10)

    # Header row: label + horizontal rule
    header_row = QWidget()
    header_layout = QHBoxLayout(header_row)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(12)

    title_label = QLabel(title)
    title_label.setStyleSheet(unit_group_header_stylesheet())
    header_layout.addWidget(title_label)

    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet(unit_group_separator_stylesheet())
    header_layout.addWidget(separator, stretch=1)
    group_layout.addWidget(header_row)

    # Card row
    cards_widget = QWidget()
    cards_layout = QHBoxLayout(cards_widget)
    cards_layout.setContentsMargins(0, 0, 0, 0)
    cards_layout.setSpacing(12)
    cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    for card in cards:
        cards_layout.addWidget(card)
    group_layout.addWidget(cards_widget)

    return group


# ── Main page view ───────────────────────────────────────────────────────────


class ChannelsPageView(BasePage):
    """
    Channels configuration page — composes _ConfigPanel and unit card groups.

    User-intent signals (→ ChannelsPresenter)
    ------------------------------------------
    instrument_model_changed(str)
    measurement_mode_changed(str)
    ground_changed(bool)
    interlock_changed(bool)
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
    display_smu_functions(idx, fns)     update one SMU's function combo
    display_smu_function_locked(idx, b) lock/unlock function combo (COMM mode)
    display_vmu_card_usable(idx, bool)  enable/disable one VMU (mode-based)
    display_vsu_functions(idx, fns)     update one VSU's function combo
    """

    # ── User-intent signals ──────────────────────────────────────────────────
    instrument_model_changed = Signal(str)
    measurement_mode_changed = Signal(str)
    ground_changed = Signal(bool)
    interlock_changed = Signal(bool)

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
        self._smu_cards: dict[int, SMUCard] = {}
        self._vmu_cards: dict[int, VMUCard] = {}
        self._vsu_cards: dict[int, VSUCard] = {}
        self._setup_ui()
        self._wire_cards()

    # ── Display API (called by ChannelsPresenter) ────────────────────────────

    def display_config(
        self,
        model: str,
        mode: str,
        common_to_ground: bool,
        interlock_open: bool,
        smu_states: dict[int, dict],
        vmu_states: dict[int, dict],
        vsu_states: dict[int, dict],
    ) -> None:
        """
        Full snapshot refresh.  All dicts contain plain-string field values.
        """
        self._config_panel.display_state(model, mode)
        _set_checkbox_signal_free(self._ground_cb, common_to_ground)
        _set_checkbox_signal_free(self._interlock_cb, interlock_open)
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
            self._validation_lbl.setText(
                tr_ui(CommandWizardText.CHAN_VALIDATION_VALID).format(
                    message=message
                )
            )
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("valid")
            )
        else:
            self._validation_lbl.setText(
                tr_ui(CommandWizardText.CHAN_VALIDATION_INVALID).format(
                    message=message
                )
            )
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("warning")
            )

    def display_available_modes(self, modes: list[str]) -> None:
        self._config_panel.display_available_modes(modes)

    def display_smu_functions(self, index: int, functions: list[str]) -> None:
        self._smu_cards[index].display_available_functions(functions)

    def display_smu_function_locked(self, index: int, locked: bool) -> None:
        self._smu_cards[index].display_function_locked(locked)

    def display_vmu_card_usable(self, index: int, usable: bool) -> None:
        self._vmu_cards[index].display_mode_usable(usable)

    def display_vsu_functions(self, index: int, functions: list[str]) -> None:
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
        scroll.setStyleSheet(units_scroll_area_stylesheet())
        scroll.viewport().setStyleSheet(units_scroll_viewport_stylesheet())
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        units_widget = QWidget()
        units_widget.setStyleSheet(units_container_stylesheet())
        units_layout = QVBoxLayout(units_widget)
        units_layout.setContentsMargins(24, 24, 24, 32)
        units_layout.setSpacing(28)
        units_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # SMU section
        smu_cards = []
        for index in range(1, 5):
            card = SMUCard(index)
            self._smu_cards[index] = card
            smu_cards.append(card)
        units_layout.addWidget(
            _make_unit_group("SOURCE MONITOR UNITS  (SMU)", smu_cards)
        )

        # VMU section
        vmu_cards = []
        for index in range(1, 3):
            card = VMUCard(index)
            self._vmu_cards[index] = card
            vmu_cards.append(card)
        units_layout.addWidget(
            _make_unit_group("VOLTAGE MONITOR UNITS ", vmu_cards)
        )

        # VSU section
        vsu_cards = []
        for index in range(1, 3):
            card = VSUCard(index)
            self._vsu_cards[index] = card
            vsu_cards.append(card)
        units_layout.addWidget(
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

        self._ground_cb = QCheckBox(
            tr_ui(CommandWizardText.CHAN_OPT_COMMON_TO_GROUND)
        )
        self._ground_cb.setChecked(True)
        self._ground_cb.setStyleSheet(global_option_checkbox_stylesheet())
        bp_layout.addWidget(self._ground_cb)

        self._interlock_cb = QCheckBox(
            tr_ui(CommandWizardText.CHAN_OPT_INTERLOCK_OPEN)
        )
        self._interlock_cb.setChecked(False)
        self._interlock_cb.setStyleSheet(global_option_checkbox_stylesheet())
        bp_layout.addWidget(self._interlock_cb)

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
        self._ground_cb.toggled.connect(self.ground_changed)
        self._interlock_cb.toggled.connect(self.interlock_changed)

        # SMU cards
        for idx, card in self._smu_cards.items():
            card.enabled_toggled.connect(
                lambda value, index=idx: self.smu_enabled_changed.emit(
                    index, value
                )
            )
            card.mode_changed.connect(
                lambda value, index=idx: self.smu_mode_changed.emit(
                    index, value
                )
            )
            card.function_changed.connect(
                lambda value, index=idx: self.smu_function_changed.emit(
                    index, value
                )
            )
            card.vname_changed.connect(
                lambda value, index=idx: self.smu_vname_changed.emit(
                    index, value
                )
            )
            card.iname_changed.connect(
                lambda value, index=idx: self.smu_iname_changed.emit(
                    index, value
                )
            )

        # VMU cards
        for idx, card in self._vmu_cards.items():
            card.enabled_toggled.connect(
                lambda value, index=idx: self.vmu_enabled_changed.emit(
                    index, value
                )
            )
            card.mode_changed.connect(
                lambda value, index=idx: self.vmu_mode_changed.emit(
                    index, value
                )
            )
            card.vname_changed.connect(
                lambda value, index=idx: self.vmu_vname_changed.emit(
                    index, value
                )
            )

        # VSU cards
        for idx, card in self._vsu_cards.items():
            card.enabled_toggled.connect(
                lambda value, index=idx: self.vsu_enabled_changed.emit(
                    index, value
                )
            )
            card.function_changed.connect(
                lambda value, index=idx: self.vsu_function_changed.emit(
                    index, value
                )
            )
            card.vname_changed.connect(
                lambda value, index=idx: self.vsu_vname_changed.emit(
                    index, value
                )
            )

        self._configure_btn.clicked.connect(self.configure_measure_clicked)
