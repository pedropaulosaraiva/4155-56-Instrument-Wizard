"""
views/widgets/action_menu.py
----------------------------
A small popup "ellipsis" (⋮) menu — pure View layer.

Unlike ``QMenu``, unavailable entries stay hoverable: they highlight in a muted
grey (never the accent blue) and surface a tooltip explaining *why* they are
unavailable, instead of being silently skipped. Every entry carries an emoji
icon. The owner rebuilds the menu on each open so entry availability reflects
the current selection.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget

from wizard_4155_4156.styles.stylesheets import (
    action_menu_item_stylesheet,
    action_menu_separator_stylesheet,
    action_menu_stylesheet,
)


class ActionMenu(QFrame):
    """Frameless popup of stacked action rows shown under an anchor widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("action_menu")
        # Transient: rebuilt on every open, so free it once it closes.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(action_menu_stylesheet())
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(6, 6, 6, 6)
        self._lay.setSpacing(2)

    def add_item(
        self,
        text: str,
        *,
        icon: str = "",
        callback: Optional[Callable[[], None]] = None,
        available: bool = True,
        unavailable_reason: str = "",
    ) -> None:
        btn = QPushButton(f"{icon}  {text}" if icon else text)
        btn.setCursor(
            Qt.CursorShape.PointingHandCursor
            if available
            else Qt.CursorShape.ArrowCursor
        )
        btn.setStyleSheet(action_menu_item_stylesheet(available))
        if available and callback is not None:
            btn.clicked.connect(lambda: self._choose(callback))
        elif unavailable_reason:
            # Kept enabled so hover + tooltip still fire; clicking is a no-op.
            btn.setToolTip(unavailable_reason)
        self._lay.addWidget(btn)

    def add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(action_menu_separator_stylesheet())
        self._lay.addWidget(line)

    def popup_under(self, anchor: QWidget) -> None:
        """Show the menu right-aligned under ``anchor``."""
        self.adjustSize()
        bottom_right = anchor.mapToGlobal(
            QPoint(anchor.width(), anchor.height())
        )
        x = max(0, bottom_right.x() - self.width())
        self.move(x, bottom_right.y() + 2)
        self.show()

    def _choose(self, callback: Callable[[], None]) -> None:
        self.close()
        callback()
