"""
views/pages/stub_pages.py
-------------------------
Placeholder implementations for pages not yet built.

Each class inherits BasePage and renders a centred label so the
navigation bar can switch between real pages immediately.
Replace with full implementations incrementally — the interface
(BasePage.on_activate, signals) stays constant.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from wizard_4155_4156.styles.icons import AppIcon, tinted_pixmap
from wizard_4155_4156.styles.stylesheets import (
    stub_page_stylesheet,
    stub_page_subtitle_stylesheet,
    stub_page_title_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage


def _make_stub(icon_path: str, title: str, subtitle: str) -> type[BasePage]:
    """
    Factory that produces a BasePage subclass at runtime.
    Avoids copy-pasting the same five-line body for every stub.
    """

    class StubPage(BasePage):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setStyleSheet(stub_page_stylesheet())

            layout = QVBoxLayout(self)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.setSpacing(12)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(tinted_pixmap(icon_path, P.TEXT_MUTED, 56))
            icon_lbl.setStyleSheet("background: transparent;")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_lbl)

            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(stub_page_title_stylesheet())
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_lbl)

            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(stub_page_subtitle_stylesheet())
            sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(sub_lbl)

    StubPage.__name__ = title.replace(" ", "") + "Page"
    StubPage.__qualname__ = StubPage.__name__
    return StubPage


ChannelsPage = _make_stub(
    AppIcon.CHANNELS,
    "Channels",
    "Select and configure SMU channels for measurement.",
)

SweepConfigPage = _make_stub(
    AppIcon.MEASURE_CONFIG,
    "Sweep / Sampling / QSCV Config",
    "Define sweep parameters, sampling intervals, and QSCV settings.",
)
