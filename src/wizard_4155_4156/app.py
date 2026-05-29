"""
app.py
------
Application bootstrap.

Sets up:
    - QApplication with Fusion style (cross-platform dark-theme baseline)
    - Application-wide QPalette sourced from PALETTE constants
    - MainWindow instantiation

Separated from main.py so the application can be imported and tested
without executing sys.exit().
"""
import sys

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.main_window import MainWindow


def build_palette() -> QPalette:
    """Construct a QPalette from PALETTE constants."""
    pal = QPalette()
    R = QPalette.ColorRole  # alias for

    pal.setColor(R.Window, QColor(P.BG_DEEP))
    pal.setColor(R.WindowText, QColor(P.TEXT_PRIMARY))
    pal.setColor(R.Base, QColor(P.BG_PANEL))
    pal.setColor(R.AlternateBase, QColor(P.BG_ELEVATED))
    pal.setColor(R.ToolTipBase, QColor(P.BG_DEEP))
    pal.setColor(R.ToolTipText, QColor(P.TEXT_SECONDARY))
    pal.setColor(R.Text, QColor(P.TEXT_SECONDARY))
    pal.setColor(R.Button, QColor(P.BG_PANEL))
    pal.setColor(R.ButtonText, QColor(P.TEXT_SECONDARY))
    pal.setColor(R.Highlight, QColor(P.ACCENT))
    pal.setColor(R.HighlightedText, QColor(P.TEXT_WHITE))
    pal.setColor(R.Link, QColor(P.ACCENT_HOVER))
    pal.setColor(R.BrightText, QColor(P.TEXT_WHITE))
    return pal


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setApplicationName("Wizard 4155/4156")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    return app.exec()
