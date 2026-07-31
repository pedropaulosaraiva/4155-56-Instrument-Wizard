"""
views/widgets/queue_button.py
-----------------------------
Toolbar button that opens the measurement queue, carrying a count badge.

Pure view: it emits :attr:`clicked` and renders whatever state is pushed in
through :meth:`set_queue_state`.  The badge is a ``QLabel`` laid out *inside*
the button rather than a painted overlay, so it inherits the theme through a
stylesheet like every other pill in the application (there is no painted-badge
precedent to follow).  The badge hides at zero, keeping the idle toolbar quiet
— but it keeps its space, so the toolbar never shifts as runs are queued.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from wizard_4155_4156.gui_text.general_text import CommandWizardText, tr_ui
from wizard_4155_4156.styles.icons import AppIcon24, app_icon
from wizard_4155_4156.styles.stylesheets import (
    queue_badge_stylesheet,
    runs_primary_button_stylesheet,
)

_T = CommandWizardText

#: Queue state (``QueueState`` value) → badge appearance key.
_BADGE_KIND = {
    "RUNNING": "running",
    "PENDING": "pending",
    "PAUSED": "paused",
    "IDLE": "idle",
}

#: Right padding reserved inside the button for the badge, so the label text
#: never slides sideways as the count appears, grows or disappears.  Sized for
#: a two-digit pill plus its inset and a little air — a longer queue than
#: anyone schedules by hand.
_BADGE_RESERVE = 50
#: Gap between the pill and the button's right edge, wide enough that the pill
#: clears the button's own rounded corner.
_BADGE_INSET = 11


class QueueButton(QWidget):
    """A "Queue" button with the pending count riding inside it."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.set_queue_state(0, "IDLE")

    # ── Display API (called by the page/presenter) ───────────────────────────

    def set_queue_state(self, count: int, state: str) -> None:
        """Show ``count`` active entries, tinted by the queue ``state``."""
        self._badge.setText(str(count))
        self._badge.setVisible(count > 0)
        self._badge.setStyleSheet(
            queue_badge_stylesheet(_BADGE_KIND.get(state, "idle"))
        )

    # ── Build ────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._button = QPushButton(tr_ui(_T.QUEUE_BTN_OPEN))
        # The layers glyph ships white for accent fills — draw it as-is rather
        # than re-tinting it (see AppIcon24.LAYERS).
        self._button.setIcon(app_icon(AppIcon24.LAYERS))
        self._button.setIconSize(QSize(16, 16))
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.setToolTip(tr_ui(_T.QUEUE_TT_OPEN))
        # Reserve the pill's strip on the right so the label keeps its place
        # whether or not a count is showing.
        self._button.setStyleSheet(
            runs_primary_button_stylesheet()
            + f"QPushButton {{ padding-right: {_BADGE_RESERVE}px; }}"
        )
        self._button.clicked.connect(self.clicked)
        row.addWidget(self._button)

        # Laid out inside the button: a child widget of a QPushButton still
        # forwards its clicks to the button underneath, so the pill is part of
        # the same hit target rather than a dead spot beside it.
        inner = QHBoxLayout(self._button)
        inner.setContentsMargins(0, 0, _BADGE_INSET, 0)
        inner.setSpacing(0)
        inner.addStretch()

        self._badge = QLabel("0")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self._badge.setToolTip(tr_ui(_T.QUEUE_TT_OPEN))
        policy = self._badge.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self._badge.setSizePolicy(policy)
        # AlignVCenter, not the default fill: stretched to the button's full
        # height the pill would read as a second button rather than a badge,
        # and its radius would no longer be half its height.
        inner.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)
