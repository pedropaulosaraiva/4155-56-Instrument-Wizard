"""
app.py
------
Application bootstrap.

Sets up:
    - QApplication with Fusion style (cross-platform dark-theme baseline)
    - Application-wide QPalette sourced from PALETTE constants
    - MainWindow instantiation

Separated from __init__.py so the application can be imported and tested
without executing sys.exit().
"""

import sys
from importlib.metadata import PackageNotFoundError, version

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from wizard_4155_4156 import resources_rc  # noqa: F401  (registers :/icons)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.main_window import MainWindow


def _app_version() -> str:
    try:
        return version("wizard_4155_4156")
    except PackageNotFoundError:
        # Frozen build (Nuitka): package metadata is not bundled.
        return "0.2.0"


def build_palette() -> QPalette:
    palette = QPalette()
    R = QPalette.ColorRole  # alias for color role

    palette.setColor(R.Window, QColor(P.BG_DEEP))
    palette.setColor(R.WindowText, QColor(P.TEXT_PRIMARY))
    palette.setColor(R.Base, QColor(P.BG_PANEL))
    palette.setColor(R.AlternateBase, QColor(P.BG_ELEVATED))
    palette.setColor(R.ToolTipBase, QColor(P.BG_DEEP))
    palette.setColor(R.ToolTipText, QColor(P.TEXT_SECONDARY))
    palette.setColor(R.Text, QColor(P.TEXT_SECONDARY))
    palette.setColor(R.Button, QColor(P.BG_PANEL))
    palette.setColor(R.ButtonText, QColor(P.TEXT_SECONDARY))
    palette.setColor(R.Highlight, QColor(P.ACCENT))
    palette.setColor(R.HighlightedText, QColor(P.TEXT_WHITE))
    palette.setColor(R.Link, QColor(P.ACCENT_HOVER))
    palette.setColor(R.BrightText, QColor(P.TEXT_WHITE))
    return palette


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setApplicationName("Wizard 4155/4156")
    app.setApplicationVersion(_app_version())

    window = MainWindow()
    window.show()

    return app.exec()
