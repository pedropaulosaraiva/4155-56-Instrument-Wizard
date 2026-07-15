"""
views/widgets/icon_label.py
---------------------------
Small icon + text row used where a QLabel previously mixed an emoji with
text (project pill, validation status).

The icon is drawn as a real pixmap next to a plain text label rather than
as a rich-text ``<img>``: Qt's rich-text image handler resolves different
qrc SVG sources rendered at the same size to a single cached image, so two
labels showing different icons would both paint whichever loaded first.

Styling: callers apply their usual stylesheet to this widget.  ``QLabel``
selectors reach the text child; scoped ``QFrame#<objectName>`` selectors
paint the row itself (set ``object_name`` for pill-style backgrounds).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class IconTextLabel(QFrame):
    """QLabel-like row rendering an SVG icon pixmap followed by text."""

    def __init__(
        self,
        icon_size: int = 14,
        spacing: int = 6,
        object_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)
            # Needed so QFrame#<name> background/border rules paint.
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._icon_size = icon_size
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(spacing)
        self._icon = QLabel()
        self._text = QLabel()
        row.addWidget(self._icon)
        row.addWidget(self._text)

    def set_content(self, icon_path: str, text: str) -> None:
        """Show ``icon_path`` (pre-colored qrc SVG) next to ``text``."""
        size = QSize(self._icon_size, self._icon_size)
        self._icon.setPixmap(QIcon(icon_path).pixmap(size))
        self._text.setText(text)
