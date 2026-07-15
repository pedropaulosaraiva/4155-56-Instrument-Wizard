"""
styles/icons.py
---------------
Central accessor + tinting factory for the application's SVG icons.

Icons ship as a single **monochrome** source each, inside the compiled Qt
resource (``resources_rc.py``, generated from ``assets/icons/icons.qrc`` via
``uv run task rcc``).  Rather than shipping a separate colored file per state
or theme, colors are applied in code: the source shape is rendered once, then
recolored with a ``QPainter`` ``SourceIn`` fill from a ``PALETTE`` token.  This
gives real per-state feedback (idle / hover / selected) and makes a future
light theme a palette-token swap rather than a new set of assets.

Exposes:
    - ``AppIcon``      — semantic resource paths (decoupled from filenames).
    - ``app_icon``     — plain ``QIcon`` from a resource path (untinted).
    - ``tinted_pixmap``— a single recolored ``QPixmap``.
    - ``nav_icon``     — a stateful ``QIcon`` for checkable nav buttons:
      dim idle, brighter on hover, signature hue when the page is selected.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from wizard_4155_4156 import resources_rc  # noqa: F401  (registers :/icons)
from wizard_4155_4156.styles.theme import PALETTE as P


class AppIcon:
    """Semantic resource paths for the shipped SVG icons."""

    HOME = ":/icons/home"
    CHANNELS = ":/icons/channels"
    MEASURE_CONFIG = ":/icons/measure_config"
    RUNS = ":/icons/runs"
    GRAPH = ":/icons/graph"
    TABLE = ":/icons/table"
    NEW_PROJECT = ":/icons/new_project"
    OPEN_PROJECT = ":/icons/open_project"


def app_icon(path: str) -> QIcon:
    """Load an untinted ``QIcon`` from a ``:/icons/...`` resource path."""
    return QIcon(path)


def _tint(source: QPixmap, color: str) -> QPixmap:
    """Recolor ``source`` to ``color`` in place, preserving its alpha shape.

    A ``SourceIn`` fill keeps only the pixels the source already covers, so the
    monochrome glyph is repainted in the target hue at its original coverage.
    """
    out = QPixmap(source.size())
    out.setDevicePixelRatio(source.devicePixelRatio())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), QColor(color))
    painter.end()
    return out


def tinted_pixmap(path: str, color: str, size: int) -> QPixmap:
    """Render ``path`` at ``size`` px and recolor it to ``color``."""
    base = QIcon(path).pixmap(QSize(size, size))
    return _tint(base, color)


def nav_icon(path: str, active_color: str, size: int) -> QIcon:
    """Build a stateful nav ``QIcon`` from a monochrome source.

    State map (as a checkable ``QToolButton`` reads it):
        Off / Normal   → dim idle grey
        Off / Active   → brighter grey on hover
        On  / *        → ``active_color`` (the selected page's signature hue)
    Disabled dimming is handled separately by the button's opacity effect.
    """
    base = QIcon(path).pixmap(QSize(size, size))
    idle = _tint(base, P.NAV_ICON_IDLE)
    hover = _tint(base, P.NAV_ICON_HOVER)
    selected = _tint(base, active_color)
    icon = QIcon()
    icon.addPixmap(idle, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(hover, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(selected, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(selected, QIcon.Mode.Active, QIcon.State.On)
    return icon
