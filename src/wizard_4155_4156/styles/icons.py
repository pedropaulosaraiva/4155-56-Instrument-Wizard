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

The 24 px sets are different: they ship **pre-colored** per theme (two SVG
sets, ``:/icons/24/dark`` and ``:/icons/24/light``), and the active set is
picked once at import time from ``theme.ICON_VARIANT`` — light themes (light,
france) use the light set, dark themes (dark, brasil) the dark set.

Exposes:
    - ``AppIcon``      — semantic resource paths (decoupled from filenames).
    - ``AppIcon24``    — semantic paths into the theme-matched 24 px set.
    - ``app_icon``     — plain ``QIcon`` from a resource path (untinted).
    - ``logo_pixmap``  — a brand asset rendered untinted into a w×h box.
    - ``tinted_pixmap``— a single recolored ``QPixmap``.
    - ``accent_button_icon`` — icon tinted for ACCENT-filled buttons.
    - ``hover_tinted_icon``  — two-state icon for hover-repainted buttons.
    - ``nav_icon``     — a stateful ``QIcon`` for checkable nav buttons:
      dim idle, brighter on hover, signature hue when the page is selected.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap

from wizard_4155_4156 import resources_rc  # noqa: F401  (registers :/icons)
from wizard_4155_4156.styles.theme import ICON_VARIANT
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
    MAIN_LOGO = ":/branding/main_logo"  # full-color 128 px PNG, theme-free
    # GREYC institutional logo — 320×80 SVG shipped in two variants: the
    # full-color violet original for light backgrounds, a monochrome white cut
    # for dark ones.  Picked once at import time, like the 24 px icon sets.
    GREYC_LOGO = f":/branding/greyc/{ICON_VARIANT}"


def themed_icon_path(name: str) -> str:
    """Resource path of ``name`` in the active theme's pre-colored 24px set."""
    return f":/icons/24/{ICON_VARIANT}/{name}"


class AppIcon24:
    """Semantic paths into the theme-matched pre-colored 24 px icon set.

    These icons carry their own semantic colors (red trash, amber warning…)
    tuned per theme background — use them as-is on panel/transparent
    surfaces.  On ACCENT-filled buttons use :func:`accent_button_icon`
    instead (the shipped ``plus`` is already white for exactly that use).
    """

    ALERT_TRIANGLE = themed_icon_path("alert-triangle")
    ARROW_DOWN = themed_icon_path("arrow-down")
    ARROW_UP = themed_icon_path("arrow-up")
    BAR_CHART = themed_icon_path("bar-chart")
    BOOK = themed_icon_path("book")
    BOOKMARK = themed_icon_path("bookmark")
    CHECK = themed_icon_path("check")
    COPY = themed_icon_path("copy")  # white — accent backgrounds only
    DOWNLOAD = themed_icon_path("download")  # white — accent bkgrs only
    EDIT = themed_icon_path("edit")
    EDIT_PENCIL = themed_icon_path("edit-3")
    FOLDER = themed_icon_path("folder")
    HELP_CIRCLE = themed_icon_path("help-circle")
    INFO = themed_icon_path("info")
    LAYERS = themed_icon_path("layers")  # white — accent backgrounds only
    PLAY = themed_icon_path("play")
    PLUS = themed_icon_path("plus")  # white — accent backgrounds only
    SAVE = themed_icon_path("save")
    SEARCH = themed_icon_path("search")
    SETTINGS = themed_icon_path("settings")
    TABLE = themed_icon_path("table")
    TOOL = themed_icon_path("tool")
    TRASH = themed_icon_path("trash-2")
    X = themed_icon_path("x")


def app_icon(path: str) -> QIcon:
    """Load an untinted ``QIcon`` from a ``:/icons/...`` resource path."""
    return QIcon(path)


def logo_pixmap(path: str, width: int, height: int) -> QPixmap:
    """Render a brand asset into a ``width`` × ``height`` box, untinted.

    Unlike :func:`tinted_pixmap` this keeps the source's own colors and takes
    a non-square box, so a wide logo is not letterboxed inside a square one.
    The pixmap is rendered at the screen's device-pixel ratio and tagged with
    it, so an SVG stays crisp under Windows display scaling instead of being
    upscaled from its logical size.
    """
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen is not None else 1.0
    return QIcon(path).pixmap(QSize(width, height), dpr)


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


def accent_button_icon(path: str, size: int = 16) -> QIcon:
    """Icon tinted ``TEXT_ON_ACCENT`` for use on ACCENT-filled buttons.

    Pre-colored 24 px icons would clash with a solid accent background, so
    the glyph is repainted in the on-accent text color instead.
    """
    return QIcon(tinted_pixmap(path, P.TEXT_ON_ACCENT, size))


def hover_tinted_icon(
    path: str, idle_color: str, hover_color: str, size: int
) -> QIcon:
    """Two-state ``QIcon``: ``idle_color`` normally, ``hover_color`` on hover.

    For buttons whose hover state repaints the background (e.g. the red
    remove buttons) where a single fixed icon color would lose contrast.
    """
    base = QIcon(path).pixmap(QSize(size, size))
    icon = QIcon()
    icon.addPixmap(_tint(base, idle_color), QIcon.Mode.Normal)
    icon.addPixmap(_tint(base, hover_color), QIcon.Mode.Active)
    return icon


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
