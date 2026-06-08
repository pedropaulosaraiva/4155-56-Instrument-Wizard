"""
styles/theme.py
---------------
Central design-token registry for the Wizard 4155/4156 application.

All color, spacing, and typography values live here.
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

    # ── Borders ──────────────────────────────────────────────────────────────
    BORDER: str = "#3e3e42"
    BORDER_FOCUS: str = "#007acc"

    # ── Accent (VS Code / AutoCAD blue) ──────────────────────────────────────
    ACCENT: str = "#007acc"
    ACCENT_HOVER: str = "#0098ff"
    ACCENT_PRESSED: str = "#005f9e"
    ACCENT_MUTED: str = "#094771"

    # ── Text ─────────────────────────────────────────────────────────────────
    TEXT_PRIMARY: str = "#e0e0e0"
    TEXT_SECONDARY: str = "#cccccc"
    TEXT_MUTED: str = "#858585"
    TEXT_DISABLED: str = "#656565"
    TEXT_WHITE: str = "#ffffff"

    # ── Semantic status ──────────────────────────────────────────────────────
    STATUS_OK: str = "#4ec9b0"
    STATUS_ERROR: str = "#f48771"
    STATUS_WARN: str = "#dcdcaa"
    STATUS_INFO: str = "#9cdcfe"

    # ── Navigation bar ───────────────────────────────────────────────────────
    NAV_ACTIVE_BG: str = "#094771"
    NAV_ACTIVE_INDICATOR: str = "#007acc"
    NAV_HOVER_BG: str = "#2d2d30"
    NAV_WIDTH: int = 56  # px — fixed sidebar width
    NAV_BTN_SIZE: int = 52  # px — icon button square

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

    TOP_BAR_HEIGHT: int = 84  # px — ConnectionTopBar fixed height
    CARD_WIDTH: int = 220  # px — ProjectCard fixed width
    CARD_HEIGHT: int = 180  # px — ProjectCard fixed height
    CARD_COLUMNS: int = 4  # cards per grid row


PALETTE = _Palette()
