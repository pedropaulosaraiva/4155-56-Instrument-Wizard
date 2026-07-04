"""
views/navigation_bar.py
-----------------------
Vertical icon-only navigation sidebar.

Design contract:
    - Fixed width (PALETTE.NAV_WIDTH px); grows to full window height.
    - One QToolButton per page, arranged top-to-bottom with a spacer below.
    - Buttons are checkable and grouped exclusively (QButtonGroup).
    - A 3 px left-edge blue line on the :checked button acts as the
    active-page indicator (applied entirely through QSS).
    - Emits page_changed(Page) when a button is clicked.
    - set_active_page(Page) lets external code drive selection (e.g.
    when the MainWindow navigates programmatically).
    - Tooltips provide the label that would otherwise live next to the icon.
"""

from typing import Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.styles.stylesheets import (
    nav_button_stylesheet,
    navigation_bar_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import Page

# ── Navigation item registry ─────────────────────────────────────────────────
#
# Each tuple: (Page, emoji-icon, tooltip text)
# Add / reorder entries here to change the sidebar — no other file needs
# to change as long as the Page enum and QStackedWidget order stay in sync.

_NAV_ITEMS: list[tuple[Page, str, str]] = [
    (Page.HOME, "🏠", "Home"),
    (Page.CHANNELS, "🔌", "Channels"),
    (
        Page.MEASURE_CONFIG,
        "⚙️",
        "Measure Config (generate from the Channels page)",
    ),
    (Page.RUNS, "🗄️", "Measurement Runs (project database)"),
    (Page.GRAPH, "📈", "Graph View"),
    (Page.TABLE, "📊", "Table View"),
]


class NavigationBar(QFrame):
    """
    Vertical sidebar that owns page-switching responsibilities.

    Signals
    -------
    page_changed(Page)
        Emitted when the user clicks a navigation button.
        MainWindow connects this to QStackedWidget.setCurrentIndex.
    """

    page_changed: Signal = Signal(Page)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: Dict[Page, QToolButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._setup_ui()
        self._apply_styles()
        # Default selection — must come after _setup_ui so buttons exist.
        self._buttons[Page.HOME].setChecked(True)

    # ── Public API ───────────────────────────────────────────────────────────

    def set_active_page(self, page: Page) -> None:
        """
        Programmatically highlight a page button without emitting
        page_changed (blockSignals ensures no re-entrant navigation).
        """
        self._group.blockSignals(True)
        self._buttons[page].setChecked(True)
        self._group.blockSignals(False)

    def set_page_enabled(self, page: Page, enabled: bool) -> None:
        """
        Enable/disable a page button (e.g. Measure Config stays
        disabled until a configuration page has been generated).
        A dimming opacity effect provides the visual cue, because the
        color-emoji glyphs ignore the QSS :disabled color property.
        """
        btn = self._buttons[page]
        btn.setEnabled(enabled)
        opacity = 1.0 if enabled else P.NAV_DISABLED_OPACITY
        btn.graphicsEffect().setOpacity(opacity)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setFixedWidth(P.NAV_WIDTH)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for page, icon, tooltip in _NAV_ITEMS:
            btn = self._make_button(icon, tooltip)
            self._buttons[page] = btn
            self._group.addButton(btn, int(page))
            layout.addWidget(btn)

        layout.addStretch()

        # Wire group → signal (idClicked passes the button's integer id)
        self._group.idClicked.connect(
            lambda page_id: self.page_changed.emit(Page(page_id))
        )

    @staticmethod
    def _make_button(icon: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(icon)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(P.NAV_WIDTH, P.NAV_BTN_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # ToolButtonTextOnly so Qt renders the emoji string, not an icon file.
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        # Tooltip shows on hover after a short delay — no extra label needed.
        btn.setToolTipDuration(0)
        # Opacity effect dims the button when disabled (see set_page_enabled).
        # A fresh effect defaults to 0.7, so start it fully opaque — buttons
        # that never call set_page_enabled (e.g. Home) must not look dimmed.
        effect = QGraphicsOpacityEffect(btn)
        effect.setOpacity(1.0)
        btn.setGraphicsEffect(effect)
        return btn

    def _apply_styles(self) -> None:
        self.setStyleSheet(navigation_bar_stylesheet())
        # Nav button QSS must be applied to each button individually because
        # the class selector "QToolButton" inside NavigationBar's stylesheet
        # would also match any nested widgets we might add later.
        for btn in self._buttons.values():
            btn.setStyleSheet(nav_button_stylesheet())
