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

from PySide6.QtCore import (
    QRegularExpression,
    QSignalBlocker,
    QSize,
    Qt,
    Signal,
    Slot,
)
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
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.icons import AppIcon24, app_icon
from wizard_4155_4156.styles.stylesheets import (
    bottom_panel_stylesheet,
    channels_page_stylesheet,
    config_combo_stylesheet,
    config_panel_stylesheet,
    config_section_label_stylesheet,
    configure_measure_button_stylesheet,
    global_option_checkbox_stylesheet,
    transparent_container_stylesheet,
    unit_card_combo_stylesheet,
    unit_card_line_edit_stylesheet,
    unit_card_mode_badge_stylesheet,
    unit_card_note_stylesheet,
    unit_card_row_label_stylesheet,
    unit_card_separator_stylesheet,
    unit_card_stylesheet,
    unit_enable_checkbox_stylesheet,
    units_container_stylesheet,
    units_scroll_area_stylesheet,
    units_scroll_viewport_stylesheet,
    validation_status_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.doc_tooltip import (
    DocTooltipButton,
    SectionHeader,
)
from wizard_4155_4156.views.widgets.icon_label import IconTextLabel

# ── Internal helpers ─────────────────────────────────────────────────────────
_NAME_VALIDATOR = QRegularExpressionValidator(
    QRegularExpression(r"[A-Za-z][A-Za-z0-9]{0,5}")
)
# Wide enough for the friendly mode/function labels stacked under their
# caption.  Four SMU cards (4×276 + 3×12 spacing) still fit inside the
# WINDOW_MIN_WIDTH design minimum without a horizontal scrollbar.
_CARD_WIDTH = 276
_LABEL_WIDTH = 68
_ROW_HEIGHT = 26
_COMBO_MIN_CHARS = 10  # lets a combo shrink below its widest item
_POPUP_PADDING = 32  # px — scrollbar + margins added to the popup width


# ── Friendly labels ──────────────────────────────────────────────────────────
# The instrument's raw tokens (SMUMode / VMUMode / UnitFunction values) are
# what the presenter sends and expects back, so they stay as the combo item
# *userData*.  Only the item *text* is user-facing, and it carries the raw
# token in parentheses so the 4155/56 User's Guide stays searchable.
#
# Built lazily (not at import time) so tr_ui() runs with the app alive.
# Any value missing from a table falls back to the raw token.


def _smu_mode_labels() -> dict[str, str]:
    return {
        "V": tr_ui(CommandWizardText.CHAN_SMU_MODE_V),
        "I": tr_ui(CommandWizardText.CHAN_SMU_MODE_I),
        "VPULSE": tr_ui(CommandWizardText.CHAN_SMU_MODE_VPULSE),
        "IPULSE": tr_ui(CommandWizardText.CHAN_SMU_MODE_IPULSE),
        "COMM": tr_ui(CommandWizardText.CHAN_SMU_MODE_COMM),
    }


def _vmu_mode_labels() -> dict[str, str]:
    return {
        "V": tr_ui(CommandWizardText.CHAN_VMU_MODE_V),
        "DVOLT": tr_ui(CommandWizardText.CHAN_VMU_MODE_DVOLT),
    }


def _unit_function_labels() -> dict[str, str]:
    return {
        "CONST": tr_ui(CommandWizardText.CHAN_FUNC_CONST),
        "VAR1": tr_ui(CommandWizardText.CHAN_FUNC_VAR1),
        "VAR2": tr_ui(CommandWizardText.CHAN_FUNC_VAR2),
        "VAR1'": tr_ui(CommandWizardText.CHAN_FUNC_VARD),
    }


def _set_combo_signal_free(combo: QComboBox, value: str) -> None:
    with QSignalBlocker(combo):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)


def _populate_combo_signal_free(
    combo: QComboBox,
    items: list[str],  # raw enum values — kept as userData
    current: str = "",
    labels: dict[str, str] | None = None,
) -> None:
    """Fill *combo* with friendly text over raw-value userData."""
    labels = labels or {}
    with QSignalBlocker(combo):
        combo.clear()
        for item in items:
            text = labels.get(item, item)
            combo.addItem(text, item)
            # QComboBox never elides, so the tooltip carries the full text.
            combo.setItemData(
                combo.count() - 1, text, Qt.ItemDataRole.ToolTipRole
            )
        idx = combo.findData(current)
        combo.setCurrentIndex(max(idx, 0))
    _fit_combo_popup(combo)
    combo.setToolTip(combo.currentText())


def _fit_combo_popup(combo: QComboBox) -> None:
    """Widen the drop-down to its longest item.

    Qt sizes the popup to the combo itself, which is narrower than the
    friendly labels — without this the names are elided in the list too.
    """
    metrics = combo.fontMetrics()
    widest = max(
        (
            metrics.horizontalAdvance(combo.itemText(index))
            for index in range(combo.count())
        ),
        default=0,
    )
    combo.view().setMinimumWidth(widest + _POPUP_PADDING)


class _ElidingComboBox(QComboBox):
    """Combo that elides its closed-state text instead of cutting it off.

    The friendly mode/function labels are longer than a card is wide, and
    Qt would otherwise chop the tail mid-word ("… Measure Current (CO").
    The full text stays available in the tooltip and in the drop-down.
    """

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        field = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            self,
        )
        option.currentText = option.fontMetrics.elidedText(
            option.currentText,
            Qt.TextElideMode.ElideRight,
            field.width(),
        )
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)


def _make_card_combo() -> QComboBox:
    """Combo sized to its container, not to its widest item.

    Cards have a fixed width, so the default size hint (the longest item)
    would fight it and clip the content instead of the combo shrinking.
    """
    combo = _ElidingComboBox()
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(_COMBO_MIN_CHARS)
    combo.setFixedHeight(_ROW_HEIGHT)
    return combo


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
    # Transparent so the card frame's color (not the darker page) shows.
    row.setStyleSheet(transparent_container_stylesheet())
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


def _make_stacked_field(caption_text: str, control: QWidget) -> QWidget:
    """Return a caption-above-control field.

    Used for the mode/function combos: the friendly labels are far too long
    for a side label, so the control gets the card's full inner width.
    """
    field = QWidget()
    field.setStyleSheet(transparent_container_stylesheet())
    field_layout = QVBoxLayout(field)
    field_layout.setContentsMargins(0, 0, 0, 0)
    field_layout.setSpacing(2)
    caption = QLabel(caption_text)
    caption.setStyleSheet(unit_card_row_label_stylesheet())
    field_layout.addWidget(caption)
    field_layout.addWidget(control)
    return field


def _with_doc_icon(
    widget: QWidget, doc_topic: DocTopic, doc_sink: Signal
) -> QWidget:
    """Pair a widget with its documentation icon, sized to their content.

    Unlike ``_label_with_tooltip`` this adds no trailing stretch, so the
    pair can sit in a row alongside other controls.
    """
    row = QWidget()
    row.setStyleSheet(transparent_container_stylesheet())
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    row_layout.addWidget(widget)
    button = DocTooltipButton(doc_topic)
    button.requested.connect(doc_sink)
    row_layout.addWidget(button)
    return row


def _connect_combo_data(combo: QComboBox, sink: Signal) -> None:
    """Emit the selected item's *userData* (the raw instrument token).

    Never ``currentTextChanged`` — that carries the friendly label, which
    the presenter cannot convert back into an enum.
    """

    def _emit(_index: int) -> None:
        combo.setToolTip(combo.currentText())
        value = combo.currentData()
        if isinstance(value, str):
            sink.emit(value)

    combo.currentIndexChanged.connect(_emit)


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
    Hover feedback is pure QSS (unit_card_stylesheet) — the optional
    ``accent`` tints the hover border to the unit group's color.
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
        accent: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._prefix = prefix
        self._index = index
        self._enabled = True
        self._accent = accent
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

    def set_unit_prefix(self, prefix: str) -> None:
        """Retitle the card (e.g. SMU2 → MPSMU2 on a 4155 mainframe)."""
        self._prefix = prefix
        self._update_enable_label(self._enabled)

    # ── Construction ─────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Header: enable checkbox + optional trailing widgets
        header = QWidget()
        header.setStyleSheet(transparent_container_stylesheet())
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
        self._content.setStyleSheet(transparent_container_stylesheet())
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
        self.setStyleSheet(unit_card_stylesheet(True, self._accent))
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
        self.setStyleSheet(unit_card_stylesheet(enabled, self._accent))

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
        super().__init__("SMU", index, parent, accent=P.UNIT_SMU)

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
        _populate_combo_signal_free(
            self._func_combo, functions, current, _unit_function_labels()
        )

    def display_available_modes(self, modes: list[str]) -> None:
        current = self._mode_combo.currentData() or ""
        _populate_combo_signal_free(
            self._mode_combo, modes, current, _smu_mode_labels()
        )

    def display_function_locked(self, locked: bool) -> None:
        """Disable function combo when SMU mode is COMM."""
        self._func_combo.setEnabled(not locked)
        if locked:
            _set_combo_signal_free(self._func_combo, "CONST")

    # ── Construction ─────────────────────────────────────────────────────────

    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._mode_combo = _make_card_combo()
        _populate_combo_signal_free(
            self._mode_combo,
            ["V", "I", "VPULSE", "IPULSE", "COMM"],
            labels=_smu_mode_labels(),
        )
        content_layout.addWidget(
            _make_stacked_field(
                tr_ui(CommandWizardText.CHAN_FIELD_MODE), self._mode_combo
            )
        )

        self._func_combo = _make_card_combo()
        _populate_combo_signal_free(
            self._func_combo,
            ["CONST", "VAR1", "VAR2", "VAR1'"],
            labels=_unit_function_labels(),
        )
        content_layout.addWidget(
            _make_stacked_field(
                tr_ui(CommandWizardText.CHAN_FIELD_FUNCTION), self._func_combo
            )
        )

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(
            _make_row(
                tr_ui(CommandWizardText.CHAN_FIELD_VNAME), self._vname_edit
            )
        )

        self._iname_edit = _make_name_edit()
        content_layout.addWidget(
            _make_row(
                tr_ui(CommandWizardText.CHAN_FIELD_INAME), self._iname_edit
            )
        )

    def _apply_content_styles(self) -> None:
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        _connect_combo_data(self._mode_combo, self.mode_changed)
        _connect_combo_data(self._func_combo, self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)
        self._iname_edit.textChanged.connect(self.iname_changed)


class VMUCard(_BaseUnitCard):
    mode_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__("VMU", index, parent, accent=P.UNIT_VMU)

    # ── Display API ──────────────────────────────────────────────────────────
    def display_state(
        self,
        enabled: bool,
        mode: str,
        voltage_name: str,
        vname_locked: bool = False,
    ) -> None:
        self._enabled = enabled
        _set_checkbox_signal_free(self._enable_cb, enabled)
        self._content.setEnabled(enabled)
        _set_combo_signal_free(self._mode_combo, mode)
        # In a dvol pair, the secondary VMU's name is auto-nulled by the
        # instrument — disable and clear the field to communicate that.
        if vname_locked:
            _set_linetxt_signal_free(self._vname_edit, "")
            self._vname_edit.setEnabled(False)
        else:
            _set_linetxt_signal_free(self._vname_edit, voltage_name)
            self._vname_edit.setEnabled(True)
        self._refresh_card_style(enabled)
        self._update_enable_label(enabled)

    # ── Private ──────────────────────────────────────────────────────────
    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._mode_combo = _make_card_combo()
        _populate_combo_signal_free(
            self._mode_combo, ["V", "DVOLT"], labels=_vmu_mode_labels()
        )
        content_layout.addWidget(
            _make_stacked_field(
                tr_ui(CommandWizardText.CHAN_FIELD_MODE), self._mode_combo
            )
        )

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(
            _make_row(
                tr_ui(CommandWizardText.CHAN_FIELD_VNAME), self._vname_edit
            )
        )

        # Informational label — VMUs have no sweep function
        note = QLabel("Monitor only — no function")
        note.setStyleSheet(unit_card_note_stylesheet())
        content_layout.addWidget(note)

    def _apply_content_styles(self) -> None:
        self._mode_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        _connect_combo_data(self._mode_combo, self.mode_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)


class VSUCard(_BaseUnitCard):
    function_changed = Signal(str)
    vname_changed = Signal(str)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__("VSU", index, parent, accent=P.UNIT_VSU)

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
        _populate_combo_signal_free(
            self._func_combo, functions, current, _unit_function_labels()
        )

    @override
    def _extend_header(self, header_layout: QHBoxLayout) -> None:
        # VSU mode is always V — show as a static badge
        mode_badge = QLabel("V")
        mode_badge.setStyleSheet(unit_card_mode_badge_stylesheet())
        header_layout.addWidget(mode_badge)

    def _setup_content(self, content_layout: QVBoxLayout) -> None:
        self._func_combo = _make_card_combo()
        _populate_combo_signal_free(
            self._func_combo,
            ["CONST", "VAR1", "VAR2", "VAR1'"],
            labels=_unit_function_labels(),
        )
        content_layout.addWidget(
            _make_stacked_field(
                tr_ui(CommandWizardText.CHAN_FIELD_FUNCTION), self._func_combo
            )
        )

        self._vname_edit = _make_name_edit()
        content_layout.addWidget(
            _make_row(
                tr_ui(CommandWizardText.CHAN_FIELD_VNAME), self._vname_edit
            )
        )

    def _apply_content_styles(self) -> None:
        self._func_combo.setStyleSheet(unit_card_combo_stylesheet())

    def _wire_content(self) -> None:
        _connect_combo_data(self._func_combo, self.function_changed)
        self._vname_edit.textChanged.connect(self.vname_changed)


# ── Configuration panel ──────────────────────────────────────────────────────
class _ConfigPanel(QFrame):
    """
    Fixed top panel: instrument model selector, measurement mode selector.
    """

    instrument_model_changed = Signal(str)  # InstrumentModel.value
    measurement_mode_changed = Signal(str)  # MeasurementMode.value
    documentation_requested = Signal(str)  # DocTopic value

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
        # Transparent so the panel frame's color (not the darker page) shows.
        selectors_row.setStyleSheet(transparent_container_stylesheet())
        selectors_layout = QHBoxLayout(selectors_row)
        selectors_layout.setContentsMargins(0, 0, 0, 0)
        selectors_layout.setSpacing(40)

        # Instrument model
        model_col = QVBoxLayout()
        model_col.setSpacing(4)
        model_label = QLabel("INSTRUMENT MODEL")
        model_label.setStyleSheet(config_section_label_stylesheet())
        model_col.addLayout(
            _label_with_tooltip(
                model_label,
                DocTopic.CHANNELS_INSTRUMENT_MODEL,
                self.documentation_requested,
            )
        )
        self._model_combo = QComboBox()
        # A-series mainframes share the B-series implementation, so both are
        # offered under one label whose userData stays the B-series value.
        for model_label, model_value in (
            ("4155A/B", "4155B"),
            ("4156A/B", "4156B"),
            ("4155C", "4155C"),
            ("4156C", "4156C"),
        ):
            self._model_combo.addItem(model_label, model_value)
        # No hardcoded default here: the presenter pushes the authoritative
        # model on init via display_state (passive-view contract).
        model_col.addWidget(self._model_combo)
        selectors_layout.addLayout(model_col)

        # Measurement mode
        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_label = QLabel("MEASUREMENT MODE")
        mode_label.setStyleSheet(config_section_label_stylesheet())
        mode_col.addLayout(
            _label_with_tooltip(
                mode_label,
                DocTopic.CHANNELS_MEASUREMENT_MODE,
                self.documentation_requested,
            )
        )
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
        _connect_combo_data(self._model_combo, self.instrument_model_changed)
        _connect_combo_data(self._mode_combo, self.measurement_mode_changed)


# ── Unit group container ─────────────────────────────────────────────────────


def _label_with_tooltip(
    label: QLabel, doc_topic: DocTopic, doc_sink: Signal
) -> QHBoxLayout:
    """Row: a section label followed by its standalone documentation icon."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(label)
    button = DocTooltipButton(doc_topic)
    button.requested.connect(doc_sink)
    row.addWidget(button)
    row.addStretch()
    return row


def _make_unit_group(
    title: str,
    cards: list[QFrame],
    accent: str | None = None,
    doc_topic: DocTopic | None = None,
    doc_sink: Signal | None = None,
) -> tuple[QWidget, SectionHeader]:
    """Return a titled section containing a horizontal row of cards.

    The header comes back with it so a caller can retitle the section later
    (the SMU group follows the selected instrument model).
    """
    group = QWidget()
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(10)

    header = SectionHeader(title, accent=accent, doc_topic=doc_topic)
    if doc_sink is not None:
        header.doc_requested.connect(doc_sink)
    group_layout.addWidget(header)

    # Card row
    cards_widget = QWidget()
    cards_layout = QHBoxLayout(cards_widget)
    cards_layout.setContentsMargins(0, 0, 0, 0)
    cards_layout.setSpacing(12)
    cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    for card in cards:
        cards_layout.addWidget(card)
    group_layout.addWidget(cards_widget)

    return group, header


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
    display_smu_naming(prefix, title)   MPSMU/HRSMU naming per instrument model
    display_smu_functions(idx, fns)     update one SMU's function combo
    display_smu_modes(idx, modes)       update one SMU's mode combo
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
    documentation_requested = Signal(str)  # DocTopic value

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
            self._validation_lbl.set_content(
                AppIcon24.CHECK,
                tr_ui(CommandWizardText.CHAN_VALIDATION_VALID).format(
                    message=message
                ),
            )
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("valid")
            )
        else:
            self._validation_lbl.set_content(
                AppIcon24.ALERT_TRIANGLE,
                tr_ui(CommandWizardText.CHAN_VALIDATION_INVALID).format(
                    message=message
                ),
            )
            self._validation_lbl.setStyleSheet(
                validation_status_stylesheet("warning")
            )

    def display_available_modes(self, modes: list[str]) -> None:
        self._config_panel.display_available_modes(modes)

    def display_smu_naming(self, prefix: str, section_title: str) -> None:
        """Retitle the SMU section and cards for the instrument model."""
        self._smu_header.set_title(section_title)
        for card in self._smu_cards.values():
            card.set_unit_prefix(prefix)

    def display_smu_functions(self, index: int, functions: list[str]) -> None:
        self._smu_cards[index].display_available_functions(functions)

    def display_smu_modes(self, index: int, modes: list[str]) -> None:
        self._smu_cards[index].display_available_modes(modes)

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

        # SMU section.  No hardcoded title/prefix here: the SMU family name
        # depends on the instrument model, so the presenter pushes it via
        # display_smu_naming on init (passive-view contract).
        smu_cards = []
        for index in range(1, 5):
            card = SMUCard(index)
            self._smu_cards[index] = card
            smu_cards.append(card)
        smu_group, self._smu_header = _make_unit_group(
            "SOURCE MONITOR UNITS",
            smu_cards,
            accent=P.UNIT_SMU,
            doc_topic=DocTopic.CHANNELS_SMU,
            doc_sink=self.documentation_requested,
        )
        units_layout.addWidget(smu_group)

        # VMU section
        vmu_cards = []
        for index in range(1, 3):
            card = VMUCard(index)
            self._vmu_cards[index] = card
            vmu_cards.append(card)
        vmu_group, _ = _make_unit_group(
            "VOLTAGE MONITOR UNITS (VMU)",
            vmu_cards,
            accent=P.UNIT_VMU,
            doc_topic=DocTopic.CHANNELS_VMU,
            doc_sink=self.documentation_requested,
        )
        units_layout.addWidget(vmu_group)

        # VSU section
        vsu_cards = []
        for index in range(1, 3):
            card = VSUCard(index)
            self._vsu_cards[index] = card
            vsu_cards.append(card)
        vsu_group, _ = _make_unit_group(
            "VOLTAGE SOURCE UNITS  (VSU)",
            vsu_cards,
            accent=P.UNIT_VSU,
            doc_topic=DocTopic.CHANNELS_VSU,
            doc_sink=self.documentation_requested,
        )
        units_layout.addWidget(vsu_group)

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
        bp_layout.addWidget(
            _with_doc_icon(
                self._ground_cb,
                DocTopic.CHANNELS_FLOATING,
                self.documentation_requested,
            )
        )

        self._interlock_cb = QCheckBox(
            tr_ui(CommandWizardText.CHAN_OPT_INTERLOCK_OPEN)
        )
        self._interlock_cb.setChecked(True)
        self._interlock_cb.setStyleSheet(global_option_checkbox_stylesheet())
        bp_layout.addWidget(
            _with_doc_icon(
                self._interlock_cb,
                DocTopic.CHANNELS_INTERLOCK,
                self.documentation_requested,
            )
        )

        self._validation_lbl = IconTextLabel()
        bp_layout.addWidget(self._validation_lbl)

        bp_layout.addStretch()

        self._configure_btn = QPushButton(
            tr_ui(CommandWizardText.CHAN_BTN_GENERATE_SETUP)
        )
        self._configure_btn.setIcon(app_icon(AppIcon24.SETTINGS))
        self._configure_btn.setIconSize(QSize(16, 16))
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
        self._config_panel.documentation_requested.connect(
            self.documentation_requested
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
