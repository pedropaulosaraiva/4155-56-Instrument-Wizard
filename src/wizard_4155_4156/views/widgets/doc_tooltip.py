"""
views/widgets/doc_tooltip.py
----------------------------
Reusable documentation widgets — pure View layer.

- ``SectionHeader`` — the "coloured title + horizontal rule" header used across
  the config pages, now with an optional documentation ``ⓘ`` icon at the right
  end (the rule runs from the title to the icon).
- ``DocTooltipButton`` — the standalone circular info icon; drop it in anywhere
  with a ``DocTopic``.

Both expose a Qt signal carrying the requested ``DocTopic`` value.  The owning
page re-exposes a single ``documentation_requested(str)`` signal that
MainWindow connects (the same pattern as the pages' ``save_to_db_requested``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from wizard_4155_4156.gui_text.documentation import DocTopic
from wizard_4155_4156.styles.stylesheets import (
    doc_tooltip_icon_stylesheet,
    unit_group_header_stylesheet,
    unit_group_separator_stylesheet,
)


class DocTooltipButton(QToolButton):
    """A clickable circular ``ⓘ`` icon linked to a documentation page."""

    requested = Signal(str)  # DocTopic value

    def __init__(
        self,
        doc_topic: DocTopic,
        *,
        size: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._topic = doc_topic
        self.setText("i")
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Open documentation")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(doc_tooltip_icon_stylesheet(size))
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self.requested.emit(str(self._topic))


class SectionHeader(QWidget):
    """Coloured title + horizontal rule, with an optional doc icon."""

    doc_requested = Signal(str)  # DocTopic value

    def __init__(
        self,
        title: str,
        *,
        accent: str | None = None,
        doc_topic: DocTopic | None = None,
        muted: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        label = QLabel(title.upper())
        label.setStyleSheet(unit_group_header_stylesheet(accent, muted))
        row.addWidget(label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(unit_group_separator_stylesheet(accent))
        # Rule stretches between the title and the (optional) icon.
        row.addWidget(separator, stretch=1)

        if doc_topic is not None:
            button = DocTooltipButton(doc_topic)
            button.requested.connect(self.doc_requested)
            row.addWidget(button)
