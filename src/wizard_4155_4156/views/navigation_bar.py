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

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QSizePolicy,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.styles.icons import AppIcon, nav_icon
from wizard_4155_4156.styles.stylesheets import (
    nav_button_stylesheet,
    navigation_bar_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import Page

# ── Navigation item registry ─────────────────────────────────────────────────
#
# Each tuple: (Page, icon-resource-path, signature-color, tooltip text)
# The signature color tints the icon when its page is selected and colors the
# active pill behind it (styles/icons.py + nav_button_stylesheet).
# Add / reorder entries here to change the sidebar — no other file needs
# to change as long as the Page enum and QStackedWidget order stay in sync.

_NAV_ITEMS: list[tuple[Page, str, str, str]] = [
    (Page.HOME, AppIcon.HOME, P.NAV_SIG_HOME, "Home"),
    (Page.CHANNELS, AppIcon.CHANNELS, P.NAV_SIG_CHANNELS, "Channels"),
    (
        Page.MEASURE_CONFIG,
        AppIcon.MEASURE_CONFIG,
        P.NAV_SIG_MEASURE_CONFIG,
        "Measure Config (generate from the Channels page or "
        "copy an existing setup)",
    ),
    (
        Page.RUNS,
        AppIcon.RUNS,
        P.NAV_SIG_RUNS,
        "Project data",
    ),
    (Page.GRAPH, AppIcon.GRAPH, P.NAV_SIG_GRAPH, "Graph View"),
    (Page.TABLE, AppIcon.TABLE, P.NAV_SIG_TABLE, "Export/Table View"),
]

# Message shown (as a tooltip anchored to the button) when a user clicks a
# page that is currently locked.  Falls back to a generic line for any page.
_LOCK_HINTS: dict[Page, str] = {
    Page.MEASURE_CONFIG: (
        "Measurement Configuration is not available yet. Generate it "
        "from the Channels page or copy an existing setup."
    ),
}
_LOCK_HINT_DEFAULT = "Create or open a project to access this page."


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
        self._locked: set[Page] = set()
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
        Lock/unlock a page button (e.g. Measure Config stays locked until a
        configuration page has been generated).

        A locked button is *not* Qt-disabled: it stays clickable so that a
        click can explain — via a tooltip anchored to the button — why the
        page is unavailable (see ``_on_button_clicked``).  It is made
        non-checkable so the click can't steal the current selection, dimmed
        via the opacity effect, and given a "forbidden" cursor so it reads as
        non-navigable against the brighter, enabled icons.
        """
        btn = self._buttons[page]
        if enabled:
            self._locked.discard(page)
            btn.setCheckable(True)
            btn.graphicsEffect().setOpacity(1.0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._locked.add(page)
            btn.setChecked(False)
            btn.setCheckable(False)
            btn.graphicsEffect().setOpacity(P.NAV_DISABLED_OPACITY)
            btn.setCursor(Qt.CursorShape.ForbiddenCursor)

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

        for page, icon, signature, tooltip in _NAV_ITEMS:
            btn = self._make_button(icon, signature, tooltip)
            self._buttons[page] = btn
            self._group.addButton(btn, int(page))
            layout.addWidget(btn)

        layout.addStretch()

        # Wire group → handler (idClicked passes the button's integer id).
        # A locked page is intercepted there rather than navigated to.
        self._group.idClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, page_id: int) -> None:
        """Navigate — unless the page is locked, in which case explain why."""
        page = Page(page_id)
        if page in self._locked:
            self._show_lock_hint(page)
            return
        self.page_changed.emit(page)

    def _show_lock_hint(self, page: Page) -> None:
        """Pop a tooltip anchored to the locked button (hard to miss)."""
        btn = self._buttons[page]
        anchor = btn.mapToGlobal(QPoint(btn.width() - 2, btn.height() // 2))
        QToolTip.showText(
            anchor, _LOCK_HINTS.get(page, _LOCK_HINT_DEFAULT), btn
        )

    @staticmethod
    def _make_button(icon: str, signature: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        # Stateful icon: dim idle grey → signature hue when selected.
        btn.setIcon(nav_icon(icon, signature, P.NAV_ICON_SIZE))
        btn.setIconSize(QSize(P.NAV_ICON_SIZE, P.NAV_ICON_SIZE))
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(P.NAV_WIDTH, P.NAV_BTN_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # ToolButtonIconOnly so Qt renders the SVG icon, not any text label.
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        # Tooltip shows on hover after a short delay — no extra label needed.
        btn.setToolTipDuration(0)
        # Opacity effect dims the button when disabled (see set_page_enabled).
        # A fresh effect defaults to 0.7, so start it fully opaque — buttons
        # that never call set_page_enabled (e.g. Home) must not look dimmed.
        effect = QGraphicsOpacityEffect(btn)
        effect.setOpacity(1.0)
        btn.setGraphicsEffect(effect)
        # Per-button QSS carries this page's signature pill color (and the
        # "QToolButton" selector must be applied per-button so it doesn't
        # match nested widgets we might add later).
        btn.setStyleSheet(nav_button_stylesheet(signature))
        return btn

    def _apply_styles(self) -> None:
        self.setStyleSheet(navigation_bar_stylesheet())
