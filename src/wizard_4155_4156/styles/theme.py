"""
styles/theme.py
---------------
Central design-token registry for the Wizard 4155/4156 application.

# TODO: remove "should" in the phrase bellow if all color,... live here
All color, spacing, and typography values should live here.
Views and stylesheets MUST reference PALETTE constants —
never hard-code hex strings anywhere else in the codebase.

Theming
-------
Four selectable themes ship with the app: ``dark`` (UI label "Black" — the
dataclass defaults), ``light`` (the default when no preference is saved),
``france`` (light, blue-tinted) and ``brasil`` (dark, green-tinted).  The
active theme is chosen **once, at import time**:
``_read_theme_preference()`` reads the persisted ``theme`` key from
``~/.wizard4155/settings.json`` (the ``WIZARD_THEME`` environment variable
wins over the file — useful for testing), and ``PALETTE`` is built from the
matching override dict.  Because every stylesheet f-string reads ``PALETTE``
tokens when widgets are constructed, a theme change simply requires an
application restart — no re-styling machinery exists or is needed.

This module stays Qt-free.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class _Palette:
    # ── Backgrounds ──────────────────────────────────────────────────────────
    BG_DEEP: str = "#1e1e1e"  # Window / deepest layer
    BG_PANEL: str = "#252526"  # Panels, cards, inputs
    BG_ELEVATED: str = "#2d2d30"  # Hover states, elevated surfaces
    BG_NAVBAR: str = "#181818"  # Navigation bar (slightly deeper)
    BG_INPUT: str = "#121212"  # Input background (very dark for contrast)
    BG_TOPBAR: str = "#333337"  # setup-page top bar (clearly gray vs. #252526)

    # ── Borders ──────────────────────────────────────────────────────────────
    BORDER: str = "#3e3e42"
    BORDER_FOCUS: str = "#007acc"

    # ── Accent (shades of blue) ──────────────────────────────────────
    ACCENT: str = "#007acc"
    ACCENT_HOVER: str = "#0098ff"
    ACCENT_PRESSED: str = "#005f9e"
    ACCENT_MUTED: str = "#094771"

    # ── Text ─────────────────────────────────────────────────────────────────
    TEXT_PRIMARY: str = "#e0e0e0"
    TEXT_SECONDARY: str = "#cccccc"
    TEXT_MUTED: str = "#858585"
    TEXT_DISABLED: str = "#656565"
    TEXT_DISABLED_SOFT: str = "#8a8a8a"  # disabled text on darkest bgs
    TEXT_WHITE: str = "#ffffff"  # strongest foreground (dark in light themes)
    TEXT_ON_ACCENT: str = "#ffffff"  # text/icons on ACCENT-filled surfaces

    # ── Semantic status ──────────────────────────────────────────────────────
    STATUS_OK: str = "#4ec9b0"
    STATUS_ERROR: str = "#f48771"
    STATUS_WARN: str = "#dcdcaa"
    STATUS_CAUTION: str = "#ce9178"  # non-blocking warnings (amber)
    STATUS_INFO: str = "#9cdcfe"

    # ── Sweep function colors (VARx color language) ──────────────────────────
    # Shared by the channel-summary badges and the VARx section accents.
    FUNC_VAR1: str = "#4ec9b0"  # teal (same hue as STATUS_OK)
    FUNC_VAR2: str = "#dcdcaa"  # amber (same hue as STATUS_WARN)
    FUNC_VARD: str = "#c586c0"  # purple
    FUNC_PULSE: str = "#d19a66"  # orange (SMU pulse source)

    # ── Unit-type colors (channels page group accents) ───────────────────────
    UNIT_SMU: str = "#0098ff"  # blue (same hue as ACCENT_HOVER)
    UNIT_VMU: str = "#9cdcfe"  # light blue (same hue as STATUS_INFO)
    UNIT_VSU: str = "#4ec9b0"  # teal (same hue as STATUS_OK)

    # ── Graphs page ──────────────────────────────────────────────────────────
    # Trace color cycle (round-robin) — hues that read well on BG_DEEP.
    GRAPH_TRACE_COLORS: tuple = (
        "#4ec9b0",  # teal
        "#0098ff",  # blue
        "#dcdcaa",  # amber
        "#c586c0",  # purple
        "#f48771",  # coral
        "#9cdcfe",  # light blue
        "#b5cea8",  # sage
        "#ce9178",  # copper
    )
    GRAPH_GRID_ALPHA: float = 0.22  # pyqtgraph showGrid alpha (data > grid)
    GRAPH_SIDEBAR_WIDTH: int = 340  # px — scene sidebar default splitter size
    GRAPH_SIDEBAR_MIN_WIDTH: int = 280  # px — splitter lower bound
    GRAPH_SIDEBAR_MAX_WIDTH: int = 560  # px — splitter upper bound
    GRAPH_PLOT_MIN_WIDTH: int = 360  # px — plot area can't be crushed
    SCROLLBAR_THIN: int = 8  # px — thin themed scrollbar width
    GRAPH_CURSOR: str = "#f48771"  # cursor line/marker (coral)
    GRAPH_CURSOR_ALT: str = "#dcdcaa"  # second cursor (amber)
    GRAPH_ROI: str = "#094771"  # ROI region fill base (ACCENT_MUTED)
    GRAPH_ROI_ALPHA: float = 0.15  # ROI fill opacity (range hint, not a veil)
    GRAPH_FIT_COLOR: str = "#ffffff"  # default fit-trace color
    # Sidebar tab hue families (section headers, separators, selected-tab
    # marker) — one hue per sidebar tab: Data / Plot / Tools / Analysis.
    GRAPH_TAB_DATA: str = "#4ec9b0"  # teal (same hue as STATUS_OK)
    GRAPH_TAB_PLOT: str = "#0098ff"  # blue (same hue as ACCENT_HOVER)
    GRAPH_TAB_TOOLS: str = "#dcdcaa"  # amber (same hue as STATUS_WARN)
    GRAPH_TAB_ANALYSIS: str = "#c586c0"  # purple (same hue as FUNC_VARD)

    # ── Navigation bar ───────────────────────────────────────────────────────
    NAV_ACTIVE_BG: str = "#094771"
    NAV_ACTIVE_INDICATOR: str = "#007acc"
    NAV_HOVER_BG: str = "#2d2d30"
    NAV_WIDTH: int = 56  # px — fixed sidebar width
    NAV_BTN_SIZE: int = 52  # px — icon button square
    NAV_ICON_SIZE: int = 24  # px — SVG icon drawn inside the nav button
    NAV_DISABLED_OPACITY: float = 0.35  # dim factor for disabled nav buttons
    # Nav icons ship as one monochrome source each, tinted in code per state
    # (styles/icons.py::nav_icon).  Idle is a dim grey; the active page's icon
    # takes its signature hue below.  A future light theme swaps these tokens.
    NAV_ICON_IDLE: str = "#8a8a90"  # unselected nav icon (legible grey)
    NAV_ICON_HOVER: str = "#d0d0d6"  # hovered, unselected nav icon
    # Per-page signature accents — active icon + its inset pill.  Values mirror
    # the app's existing hues so the nav stays in the same color language.
    NAV_SIG_HOME: str = "#9cdcfe"  # light blue (as STATUS_INFO)
    NAV_SIG_CHANNELS: str = "#dcdcaa"  # amber (as STATUS_WARN)
    NAV_SIG_MEASURE_CONFIG: str = "#4ec9b0"  # teal (as STATUS_OK)
    NAV_SIG_RUNS: str = "#c586c0"  # purple (as FUNC_VARD)
    NAV_SIG_GRAPH: str = "#f48771"  # coral (as STATUS_ERROR)
    NAV_SIG_TABLE: str = "#b5cea8"  # sage

    # ── Typography ───────────────────────────────────────────────────────────
    FONT_FAMILY_UI: str = "Segoe UI, Arial, sans-serif"
    FONT_FAMILY_MONO: str = "Consolas, Monaco, monospace"
    FONT_SIZE_XS: str = "11px"
    FONT_SIZE_SM: str = "12px"
    FONT_SIZE_MD: str = "13px"
    FONT_SIZE_LG: str = "15px"
    FONT_SIZE_XL: str = "20px"

    # ── Geometry ─────────────────────────────────────────────────────────────
    RADIUS_SM: str = "4px"
    RADIUS_MD: str = "6px"
    RADIUS_LG: str = "8px"
    RADIUS_PILL: str = "14px"
    # TODO: int values bellow go to Qt layout math,
    # while the str values are for QSS strings so this shouldn't be mixed
    WINDOW_MIN_WIDTH: int = 1300  # px — MainWindow design minimum width
    WINDOW_MIN_HEIGHT: int = 760  # px — MainWindow design minimum height
    WINDOW_FRAME_ALLOWANCE: int = 32  # px — OS title bar / frame headroom
    TOP_BAR_HEIGHT: int = 84  # px — ConnectionTopBar fixed height
    CARD_WIDTH: int = 220  # px — ProjectCard fixed width
    CARD_HEIGHT: int = 180  # px — ProjectCard fixed height
    CARD_COLUMNS: int = 4  # cards per grid row


# ── Theme override dicts ─────────────────────────────────────────────────────
# Only color tokens may be overridden — typography, geometry and alpha values
# are shared by every theme.  ``dark`` (UI label "Black") is the dataclass
# defaults and therefore needs no dict.

_LIGHT_OVERRIDES: dict = {
    # Backgrounds — inverted layering: deepest is light grey, panels white.
    "BG_DEEP": "#f4f5f7",
    "BG_PANEL": "#ffffff",
    "BG_ELEVATED": "#e9ebef",
    "BG_NAVBAR": "#e6e8ec",
    "BG_INPUT": "#ffffff",
    "BG_TOPBAR": "#dfe2e7",
    # Borders
    "BORDER": "#d0d4db",
    "BORDER_FOCUS": "#0067c0",
    # Accent — darker blue for AA contrast on white; MUTED becomes a wash.
    "ACCENT": "#0067c0",
    "ACCENT_HOVER": "#0078d4",
    "ACCENT_PRESSED": "#005a9e",
    "ACCENT_MUTED": "#cce4f7",
    # Text — TEXT_WHITE flips to "strongest foreground" (near-black);
    # TEXT_ON_ACCENT is deliberately NOT overridden (stays white).
    "TEXT_PRIMARY": "#1b1f24",
    "TEXT_SECONDARY": "#33383f",
    "TEXT_MUTED": "#6b7178",
    "TEXT_DISABLED": "#a4a9af",
    "TEXT_DISABLED_SOFT": "#8d9298",
    "TEXT_WHITE": "#111418",
    # Semantic status — same hues, darkened for white backgrounds.
    "STATUS_OK": "#0f7b6c",
    "STATUS_ERROR": "#c53929",
    "STATUS_WARN": "#9a7b00",
    "STATUS_CAUTION": "#b45f2a",
    "STATUS_INFO": "#0b6bcb",
    # Sweep function colors
    "FUNC_VAR1": "#0f7b6c",
    "FUNC_VAR2": "#9a7b00",
    "FUNC_VARD": "#8e3fa8",
    "FUNC_PULSE": "#b45f06",
    # Unit-type colors
    "UNIT_SMU": "#0067c0",
    "UNIT_VMU": "#0b6bcb",
    "UNIT_VSU": "#0f7b6c",
    # Graphs page — dark trace hues that read well on white.
    "GRAPH_TRACE_COLORS": (
        "#0f766e",  # teal
        "#1d4ed8",  # blue
        "#a16207",  # amber
        "#7e22ce",  # purple
        "#dc2626",  # red
        "#0369a1",  # light blue
        "#4d7c0f",  # sage
        "#c2410c",  # copper
    ),
    "GRAPH_CURSOR": "#c53929",
    "GRAPH_CURSOR_ALT": "#9a7b00",
    "GRAPH_ROI": "#cce4f7",
    "GRAPH_FIT_COLOR": "#111418",
    "GRAPH_TAB_DATA": "#0f7b6c",
    "GRAPH_TAB_PLOT": "#0b6bcb",
    "GRAPH_TAB_TOOLS": "#9a7b00",
    "GRAPH_TAB_ANALYSIS": "#8e3fa8",
    # Navigation bar — icons are tinted from these tokens, so the light
    # theme needs no new icon assets for the nav.
    "NAV_ACTIVE_BG": "#cce4f7",
    "NAV_ACTIVE_INDICATOR": "#0067c0",
    "NAV_HOVER_BG": "#dde1e6",
    "NAV_ICON_IDLE": "#5f666d",
    "NAV_ICON_HOVER": "#2b3036",
    "NAV_SIG_HOME": "#0b6bcb",
    "NAV_SIG_CHANNELS": "#9a7b00",
    "NAV_SIG_MEASURE_CONFIG": "#0f7b6c",
    "NAV_SIG_RUNS": "#8e3fa8",
    "NAV_SIG_GRAPH": "#c53929",
    "NAV_SIG_TABLE": "#4d7c0f",
}

# France — the light theme with blue-tinted surfaces and French-blue accents.
_FRANCE_OVERRIDES: dict = {
    **_LIGHT_OVERRIDES,
    "BG_DEEP": "#d9e4f3",
    "BG_PANEL": "#ecf2fa",
    "BG_ELEVATED": "#c9d9ee",
    "BG_NAVBAR": "#c0d3eb",
    "BG_TOPBAR": "#b8cde9",
    "BG_INPUT": "#f7fafd",
    "BORDER": "#9fbbdf",
    "BORDER_FOCUS": "#0055a4",
    "ACCENT": "#0055a4",  # flag blue
    "ACCENT_HOVER": "#2a72c3",
    "ACCENT_PRESSED": "#003f7d",
    "ACCENT_MUTED": "#aecbec",
    "NAV_ACTIVE_BG": "#aecbec",
    "NAV_ACTIVE_INDICATOR": "#0055a4",
    "NAV_HOVER_BG": "#cddef1",
    "UNIT_SMU": "#0055a4",
}

# Brasil — the dark theme with green-tinted surfaces and green accents.  The
# teal family is lifted so it separates from the green accent/backgrounds.
_BRASIL_OVERRIDES: dict = {
    "BG_DEEP": "#1b2a22",
    "BG_PANEL": "#243830",
    "BG_ELEVATED": "#2f4a3c",
    "BG_NAVBAR": "#16231c",
    "BG_INPUT": "#132019",
    "BG_TOPBAR": "#3a5a48",
    "BORDER": "#446353",
    "BORDER_FOCUS": "#2bb673",
    "ACCENT": "#1e9e5a",  # flag green
    "ACCENT_HOVER": "#2fca77",
    "ACCENT_PRESSED": "#177a45",
    "ACCENT_MUTED": "#1d5b3b",
    "STATUS_OK": "#63dfc6",
    "FUNC_VAR1": "#63dfc6",
    "UNIT_VSU": "#63dfc6",
    "GRAPH_TRACE_COLORS": (
        "#5fd8bf",  # teal (lifted off the green surfaces)
        "#0098ff",  # blue
        "#dcdcaa",  # amber
        "#c586c0",  # purple
        "#f48771",  # coral
        "#9cdcfe",  # light blue
        "#b5cea8",  # sage
        "#ce9178",  # copper
    ),
    "GRAPH_ROI": "#1d5b3b",
    "GRAPH_TAB_DATA": "#63dfc6",
    "NAV_ACTIVE_BG": "#1d5b3b",
    "NAV_ACTIVE_INDICATOR": "#2fca77",
    "NAV_HOVER_BG": "#2f4a3c",
    "NAV_SIG_MEASURE_CONFIG": "#63dfc6",
}

_THEMES: dict[str, dict] = {
    "dark": {},
    "light": _LIGHT_OVERRIDES,
    "france": _FRANCE_OVERRIDES,
    "brasil": _BRASIL_OVERRIDES,
}

# Which pre-colored 24px icon set (:/icons/24/<variant>/...) each theme uses.
_ICON_VARIANTS: dict[str, str] = {
    "dark": "dark",
    "light": "light",
    "france": "light",
    "brasil": "dark",
}

_SETTINGS_PATH = Path.home() / ".wizard4155" / "settings.json"

#: Theme used when no (valid) preference exists — first launch shows Light.
_DEFAULT_THEME = "light"


def load_palette(name: str) -> _Palette:
    """Build the palette for ``name``; unknown names fall back to light."""
    key = str(name).strip().lower()
    if key not in _THEMES:
        key = _DEFAULT_THEME
    return _Palette(**_THEMES[key])


def _read_theme_preference(path: Path | None = None) -> str:
    """Return the persisted theme name, defaulting to ``light``.

    The ``WIZARD_THEME`` environment variable wins over the settings file.
    The file is read directly (not through ``GlobalSettingsManager``) so this
    module stays import-light and Qt-free at interpreter start-up.
    """
    env = os.environ.get("WIZARD_THEME", "").strip().lower()
    if env in _THEMES:
        return env
    target = path if path is not None else _SETTINGS_PATH
    try:
        with open(target, encoding="utf-8") as fh:
            name = str(json.load(fh).get("theme", "")).strip().lower()
    except Exception:  # noqa: BLE001  (missing/corrupt file → default)
        return _DEFAULT_THEME
    return name if name in _THEMES else _DEFAULT_THEME


_THEME_NAME = _read_theme_preference()
PALETTE = load_palette(_THEME_NAME)
ICON_VARIANT: str = _ICON_VARIANTS[_THEME_NAME]
