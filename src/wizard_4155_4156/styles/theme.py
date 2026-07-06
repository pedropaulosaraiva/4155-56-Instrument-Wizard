"""
styles/theme.py
---------------
Central design-token registry for the Wizard 4155/4156 application.

# TODO: remove "should" in the phrase bellow if all color,... live here
All color, spacing, and typography values should live here.
Views and stylesheets MUST reference PALETTE constants —
never hard-code hex strings anywhere else in the codebase.
"""

from dataclasses import dataclass


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
    TEXT_WHITE: str = "#ffffff"

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
    NAV_DISABLED_OPACITY: float = 0.35  # dim factor for disabled nav buttons

    # ── Typography ───────────────────────────────────────────────────────────
    FONT_FAMILY_UI: str = "Segoe UI, Arial, sans-serif"
    FONT_FAMILY_MONO: str = "Consolas, Monaco, monospace"
    FONT_SIZE_XS: str = "11px"
    FONT_SIZE_SM: str = "12px"
    FONT_SIZE_MD: str = "13px"
    FONT_SIZE_LG: str = "15px"
    FONT_SIZE_XL: str = "20px"
    FONT_SIZE_ICON_NAV: str = "22px"  # emoji icon in nav buttons

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


PALETTE = _Palette()
