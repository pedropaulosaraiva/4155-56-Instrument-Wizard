"""
styles/stylesheets.py
---------------------
All QSS (Qt Style Sheet) strings for the application.

Rules:
    - Every function returns a complete, self-contained QSS string.
    - All color/size values come from PALETTE — never inline literals.
    - Views call these functions once in their _apply_styles() method.
    - Strings are kept as f-strings so PALETTE changes propagate globally.
"""

from wizard_4155_4156.styles.theme import PALETTE as P

# ── Application-wide ─────────────────────────────────────────────────────────


def application_stylesheet() -> str:
    return f"""
        QMainWindow {{
            background-color: {P.BG_DEEP};
        }}
        QMenuBar {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_SECONDARY};
            border-bottom: 1px solid {P.BORDER};
            padding: 4px;
        }}
        QMenuBar::item {{
            padding: 6px 14px;
            margin: 0px 2px;
            border-radius: {P.RADIUS_SM};
        }}
        QMenuBar::item:selected {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
        }}
        QMenu {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: {P.RADIUS_SM};
        }}
        QMenu::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {P.BORDER};
            margin: 4px 10px;
        }}
        QScrollBar:vertical {{
            background: {P.BG_DEEP};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {P.BORDER};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {P.TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """


def status_bar_stylesheet() -> str:
    return f"""
        QStatusBar {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_MUTED};
            font-size: {P.FONT_SIZE_MD};
            border-top: 1px solid {P.BORDER};
        }}
    """


def status_indicator_ready_stylesheet() -> str:
    return f"""
        color: {P.STATUS_OK};
        font-weight: bold;
        font-size: {P.FONT_SIZE_MD};
        padding-right: 12px;
        border-right: 1px solid {P.BORDER};
    """


def status_indicator_busy_stylesheet() -> str:
    return f"""
        color: {P.STATUS_WARN};
        font-weight: bold;
        font-size: {P.FONT_SIZE_MD};
        padding-right: 12px;
        border-right: 1px solid {P.BORDER};
    """


# ── Navigation Bar ───────────────────────────────────────────────────────────


def navigation_bar_stylesheet() -> str:
    return f"""
        NavigationBar {{
            background-color: {P.BG_NAVBAR};
            border-right: 1px solid {P.BORDER};
        }}
    """


def nav_button_stylesheet() -> str:
    """
    Checkable QToolButton used as nav item.
    The 3px left border on :checked acts as the active-page indicator.
    padding-left compensates for the border to keep the icon centered.
    """
    return f"""
        QToolButton {{
            background-color: transparent;
            border: none;
            border-left: 3px solid transparent;
            color: {P.TEXT_DISABLED};
            font-size: {P.FONT_SIZE_ICON_NAV};
            width: {P.NAV_BTN_SIZE}px;
            height: {P.NAV_BTN_SIZE}px;
            padding: 0px;
            border-radius: 0px;
        }}
        QToolButton:hover {{
            background-color: {P.NAV_HOVER_BG};
            color: {P.TEXT_PRIMARY};
        }}
        QToolButton:checked {{
            background-color: {P.NAV_ACTIVE_BG};
            border-left: 3px solid {P.NAV_ACTIVE_INDICATOR};
            color: {P.ACCENT_HOVER};
        }}
        QToolButton:checked:hover {{
            background-color: {P.ACCENT_MUTED};
        }}
        QToolButton:pressed {{
            background-color: {P.ACCENT_MUTED};
        }}
        QToolButton:disabled {{
            background-color: transparent;
            color: {P.TEXT_MUTED};
        }}
    """


# ── Connection Top Bar ───────────────────────────────────────────────────────


def connection_top_bar_stylesheet() -> str:
    return f"""
        ConnectionTopBar {{
            background-color: {P.BG_DEEP};
            border-bottom: 1px solid {P.BORDER};
        }}
    """


def top_bar_app_name_stylesheet() -> str:
    return f"""
        color: {P.TEXT_PRIMARY};
        font-weight: bold;
        font-size: 16px;
        background: transparent;
    """


def top_bar_label_stylesheet() -> str:
    return f"""
        color: {P.TEXT_MUTED};
        font-size: {P.FONT_SIZE_XS};
        letter-spacing: 1px;
        background: transparent;
    """


def top_bar_sys_status_stylesheet() -> str:
    return f"""
        color: {P.STATUS_OK};
        font-size: {P.FONT_SIZE_MD};
        font-weight: bold;
        background: transparent;
        padding: 6px 14px;
        border-radius: {P.RADIUS_PILL};
        border: 1px solid {P.STATUS_OK};
    """


# ── Compact Connector Widget ─────────────────────────────────────────────────


def compact_connector_stylesheet() -> str:
    """
    Dark-theme override for CompactConnectorWidget.
    Replaces the widget's default light background.
    Applied once in CompactConnectorWidget._apply_styles().
    """
    return f"""
        CompactConnectorWidget {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
        }}
        CompactConnectorWidget:hover {{
            background-color: {P.BG_ELEVATED};
            border: 1px solid {P.ACCENT};
        }}
    """


def connector_label_model_stylesheet() -> str:
    return f"""
        font-weight: bold;
        color: {P.TEXT_PRIMARY};
        font-size: {P.FONT_SIZE_MD};
        background: transparent;
    """


def connector_label_status_connected_stylesheet() -> str:
    return (
        f"font-size: {P.FONT_SIZE_SM}; color: {P.STATUS_OK}; "
        f"background: transparent;"
    )


def connector_label_status_disconnected_stylesheet() -> str:
    return (
        f"font-size: {P.FONT_SIZE_SM}; color: {P.STATUS_ERROR}; "
        f"background: transparent;"
    )


def connector_label_status_idle_stylesheet() -> str:
    """
    Applied when connected but idle (after setup finishes or on progress reset)
    """
    return (
        f"font-size: {P.FONT_SIZE_SM}; color: {P.TEXT_MUTED}; "
        f"background: transparent;"
    )


def connector_progress_bar_stylesheet() -> str:
    return f"""
        QProgressBar {{
            background-color: {P.BORDER};
            border-radius: 2px;
        }}
        QProgressBar::chunk {{
            background-color: {P.ACCENT};
            border-radius: 2px;
        }}
    """


# ── Quick Actions Panel ──────────────────────────────────────────────────────


def quick_actions_panel_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def section_title_stylesheet() -> str:
    return f"""
        color: {P.TEXT_PRIMARY};
        font-size: {P.FONT_SIZE_XL};
        font-weight: bold;
        margin-bottom: 4px;
    """


def subsection_title_stylesheet() -> str:
    return f"""
        color: {P.TEXT_PRIMARY};
        font-size: 14px;
        font-weight: bold;
        margin-top: 8px;
    """


def primary_action_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
            text-align: left;
        }}
        QPushButton:hover {{
            background-color: {P.BG_ELEVATED};
            border: 1px solid {P.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {P.ACCENT_MUTED};
        }}
    """


def resource_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            border: none;
            color: {P.TEXT_SECONDARY};
            text-align: left;
            padding: 10px 12px;
            font-size: {P.FONT_SIZE_MD};
            border-radius: {P.RADIUS_MD};
        }}
        QPushButton:hover {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
        }}
    """


def version_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
        "margin-top: 20px;"
    )


# ── Recent Projects Panel ────────────────────────────────────────────────────


def recent_panel_header_stylesheet() -> str:
    return f"""
        color: {P.TEXT_PRIMARY};
        font-size: {P.FONT_SIZE_XL};
        font-weight: bold;
    """


def recent_panel_count_stylesheet() -> str:
    return f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_MD};"


def clear_history_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {P.TEXT_MUTED};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 4px 12px;
            font-size: {P.FONT_SIZE_SM};
        }}
        QPushButton:hover {{
            color: {P.STATUS_ERROR};
            border-color: {P.STATUS_ERROR};
        }}
    """


def empty_projects_label_stylesheet() -> str:
    return f"color: {P.TEXT_DISABLED}; font-size: 14px; padding: 40px;"


# ── Project Card ─────────────────────────────────────────────────────────────


def project_card_stylesheet(hover: bool = False) -> str:
    if hover:
        return f"""
            ProjectCard {{
                background-color: {P.BG_ELEVATED};
                border: 1px solid {P.ACCENT};
                border-radius: {P.RADIUS_LG};
            }}
        """
    return f"""
        ProjectCard {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
        }}
    """


def card_thumbnail_stylesheet() -> str:
    return f"""
        background-color: {P.BG_DEEP};
        border: 1px solid {P.BORDER};
        border-radius: {P.RADIUS_SM};
    """


def card_name_stylesheet() -> str:
    return (
        f"color: {P.TEXT_PRIMARY}; font-weight: "
        f"bold;font-size: {P.FONT_SIZE_MD};"
    )


def card_path_stylesheet() -> str:
    return f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_XS};"


def card_date_stylesheet() -> str:
    return f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS};"


def card_remove_button_stylesheet() -> str:
    return f"""
        QToolButton {{
            background-color: {P.BORDER};
            color: {P.TEXT_SECONDARY};
            border: none;
            border-radius: 10px;
            font-size: {P.FONT_SIZE_XS};
            font-weight: bold;
            width: 20px;
            height: 20px;
        }}
        QToolButton:hover {{
            background-color: {P.STATUS_ERROR};
            color: {P.TEXT_WHITE};
        }}
    """


# ── Connector Modal ──────────────────────────────────────────────────────────


def connector_modal_stylesheet() -> str:
    return f"""
        QDialog {{
            background-color: {P.BG_DEEP};
        }}
        QGroupBox {{
            color: {P.TEXT_SECONDARY};
            font-weight: bold;
            font-size: {P.FONT_SIZE_MD};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            margin-top: 14px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 6px;
        }}
        QComboBox {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 6px 10px;
            font-size: {P.FONT_SIZE_MD};
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            selection-background-color: {P.ACCENT_MUTED};
            border: 1px solid {P.BORDER};
        }}
        QPushButton {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: none;
            border-radius: {P.RADIUS_SM};
            padding: 8px 18px;
            font-weight: bold;
            font-size: {P.FONT_SIZE_MD};
        }}
        QPushButton:hover {{ background-color: {P.ACCENT_HOVER}; }}
        QPushButton:pressed {{ background-color: {P.ACCENT_PRESSED}; }}
        QPushButton:disabled {{
            background-color: {P.BORDER};
            color: {P.TEXT_DISABLED};
        }}
        QTextEdit {{
            background-color: #0d0d0d;
            color: #d4d4d4;
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            font-family: {P.FONT_FAMILY_MONO};
            font-size: {P.FONT_SIZE_MD};
            padding: 8px;
        }}
        QProgressBar {{
            background-color: {P.BORDER};
            border-radius: {P.RADIUS_SM};
        }}
        QProgressBar::chunk {{
            background-color: {P.ACCENT};
            border-radius: {P.RADIUS_SM};
        }}
    """


# ── Splitter ─────────────────────────────────────────────────────────────────


def splitter_stylesheet() -> str:
    return f"""
        QSplitter::handle {{
            background-color: {P.BORDER};
        }}
    """


# ── Stub / Placeholder Pages ─────────────────────────────────────────────────


def stub_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def stub_page_title_stylesheet() -> str:
    return f"""
        color: {P.TEXT_MUTED};
        font-size: 28px;
        font-weight: bold;
        background: transparent;
    """


def stub_page_subtitle_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: 14px; background: transparent;"
    )


# ── Channels Page ────────────────────────────────────────────────────────────


def channels_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def units_scroll_area_stylesheet() -> str:
    return "background: transparent; border: none;"


def units_scroll_viewport_stylesheet() -> str:
    return "background: transparent;"


def units_container_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def config_panel_stylesheet() -> str:
    return f"""
        QFrame#config_panel {{
            background-color: {P.BG_PANEL};
            border-bottom: 1px solid {P.BORDER};
        }}
    """


def bottom_panel_stylesheet() -> str:
    return f"""
        QFrame#bottom_panel {{
            background-color: {P.BG_PANEL};
            border-top: 1px solid {P.BORDER};
        }}
    """


def config_section_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_XS}; "
        f"letter-spacing: 1px; background: transparent;"
    )


def config_combo_stylesheet() -> str:
    return f"""
        QComboBox {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 6px 12px;
            font-size: {P.FONT_SIZE_MD};
            font-weight: bold;
            min-width: 160px;
        }}
        QComboBox:hover {{ border-color: {P.ACCENT}; }}
        QComboBox:focus {{ border-color: {P.ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox QAbstractItemView {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            selection-background-color: {P.ACCENT_MUTED};
            border: 1px solid {P.BORDER};
            padding: 2px;
        }}
    """


def global_option_checkbox_stylesheet() -> str:
    return f"""
        QCheckBox {{
            color: {P.TEXT_SECONDARY};
            font-size: {P.FONT_SIZE_MD};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 15px; height: 15px;
            border-radius: {P.RADIUS_SM};
            border: 1px solid {P.BORDER};
        }}
        QCheckBox::indicator:checked {{
            background-color: {P.ACCENT};
            border-color: {P.ACCENT};
        }}
        QCheckBox::indicator:unchecked {{ background-color: {P.BG_DEEP}; }}
        QCheckBox::indicator:hover {{ border-color: {P.ACCENT_HOVER}; }}
    """


def unit_group_header_stylesheet(accent: str | None = None) -> str:
    return (
        f"color: {accent or P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_XS}; "
        f"font-weight: bold; letter-spacing: 2px; background: transparent;"
    )


def unit_group_separator_stylesheet(accent: str | None = None) -> str:
    return f"background-color: {accent or P.BORDER}; max-height: 1px;"


def unit_card_stylesheet(
    enabled: bool = True, accent: str | None = None
) -> str:
    """Unit card with QSS-driven hover — no enter/leave code in widgets.

    Enabled cards lift and take the accent border on hover; disabled cards
    keep their sunken look but still show the accent border, since they
    remain clickable to re-enable.
    """
    hover_border = accent or P.ACCENT
    if enabled:
        bg, border, bg_hover = P.BG_PANEL, P.BORDER, P.BG_ELEVATED
    else:
        bg, border, bg_hover = P.BG_DEEP, P.BG_ELEVATED, P.BG_DEEP
    return f"""
        QFrame#unit_card {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {P.RADIUS_LG};
        }}
        QFrame#unit_card:hover {{
            background-color: {bg_hover};
            border-color: {hover_border};
        }}
    """


def transparent_container_stylesheet() -> str:
    """Transparent background for a plain QWidget that merely groups other
    widgets (unit-card header/content/rows, the config-panel selector row).

    Such containers carry no background of their own, so they would
    otherwise inherit the page background (BG_DEEP) and render darker than
    the panel/card frame they sit on.  Keeping them transparent lets the
    parent frame's painted background show through — BG_PANEL normally (or
    BG_ELEVATED on a card's hover) — so the surface stays one uniform color.
    """
    return "background: transparent;"


def unit_card_title_stylesheet() -> str:
    return (
        f"color: {P.TEXT_PRIMARY}; font-weight: bold; "
        f"font-size: {P.FONT_SIZE_MD}; background: transparent;"
    )


def unit_card_row_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_SM}; "
        "background: transparent;"
    )


def unit_card_note_stylesheet() -> str:
    """Italic informational note inside a unit card (e.g. VMU monitor-only)."""
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_XS}; "
        f"background: transparent; font-style: italic;"
    )


def unit_card_mode_badge_stylesheet() -> str:
    """Static mode badge in a unit-card header (e.g. the VSU 'V' badge)."""
    return (
        f"color: {P.ACCENT_HOVER}; font-size: {P.FONT_SIZE_XS}; "
        f"font-weight: bold; background: {P.ACCENT_MUTED}; "
        f"padding: 1px 6px; border-radius: {P.RADIUS_SM};"
    )


def unit_card_separator_stylesheet() -> str:
    return f"background-color: {P.BORDER}; max-height: 1px;"


def unit_enable_checkbox_stylesheet() -> str:
    return f"""
        QCheckBox {{
            color: {P.TEXT_PRIMARY};
            font-weight: bold;
            font-size: {P.FONT_SIZE_MD};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 13px; height: 13px;
            border-radius: 7px;
            border: 1px solid {P.TEXT_DISABLED};
        }}
        QCheckBox::indicator:checked {{
            background-color: {P.STATUS_OK};
            border-color: {P.STATUS_OK};
        }}
        QCheckBox::indicator:unchecked {{
            background-color: {P.BG_DEEP};
            border-color: {P.TEXT_DISABLED};
        }}
        QCheckBox::indicator:disabled {{
            background-color: {P.BORDER};
            border-color: {P.BORDER};
        }}
    """


def unit_card_combo_stylesheet() -> str:
    return f"""
        QComboBox {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 4px 8px;
            font-size: {P.FONT_SIZE_SM};
        }}
        QComboBox:focus {{ border-color: {P.ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 18px; }}
        QComboBox QAbstractItemView {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            selection-background-color: {P.ACCENT_MUTED};
            border: 1px solid {P.BORDER};
        }}
        QComboBox:disabled {{
            color: {P.TEXT_DISABLED};
            border-color: {P.BG_ELEVATED};
        }}
    """


def unit_card_line_edit_stylesheet() -> str:
    return f"""
        QLineEdit {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 4px 8px;
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        QLineEdit:focus {{ border-color: {P.ACCENT}; }}
        QLineEdit:disabled {{
            color: {P.TEXT_DISABLED};
            border-color: {P.BG_ELEVATED};
        }}
    """


def validation_status_stylesheet(state: str) -> str:
    """
    state can be 'valid' (green), 'caution' (amber, non-blocking
    warnings) or 'warning' (yellow, blocking errors).
    """
    if state == "valid":
        color = P.STATUS_OK
    elif state == "caution":
        color = P.STATUS_CAUTION
    else:
        color = P.STATUS_WARN
    return f"""
        QLabel {{
            color: {color};
            font-size: {P.FONT_SIZE_MD};
            font-weight: bold;
            background: transparent;
        }}
    """


def configure_measure_button_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
            padding: 0px 16px;
            font-size: {P.FONT_SIZE_MD};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {P.BG_ELEVATED};
            border: 1px solid {P.ACCENT};
        }}
        QPushButton:pressed {{
            background-color: {P.ACCENT_MUTED};
        }}
        QPushButton:disabled {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_DISABLED};
            border: 1px solid {P.BORDER};
        }}
    """


# ── Measurement-config pages (sweep, sampling, and future modes) ─────────────


def config_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def section_card_stylesheet(accent: str | None = None) -> str:
    """Section card with an optional colored accent stripe on its left edge.

    Sections are informational, not clickable, so the background stays at a
    static elevated shade — only the border lights up to the section accent
    (global accent blue for neutral sections) on hover.  Background shifts
    on hover are reserved for clickable cards (see unit_card_stylesheet).
    The left corners are squared when a stripe is present so it ends flat
    instead of curling around the corner radius.

    Shared by every SectionFrame-based page — pass ``accent`` from the page
    to color a section; nothing page-specific belongs in here.
    """
    left_stripe = (
        f"border-left: 3px solid {accent}; "
        "border-top-left-radius: 0px; "
        "border-bottom-left-radius: 0px;"
        if accent
        else ""
    )
    hover_color = accent or P.ACCENT
    return f"""
        QFrame#section_card {{
            background-color: {P.BG_ELEVATED};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
            {left_stripe}
        }}
        QFrame#section_card:hover {{
            border-color: {hover_color};
        }}
    """


def channel_row_badge_stylesheet(color: str) -> str:
    return (
        f"color: {color}; font-size: {P.FONT_SIZE_XS}; font-weight: bold; "
        f"background: transparent; padding: 2px 8px; "
        f"border: 1px solid {color}; border-radius: {P.RADIUS_SM};"
    )


def input_error_stylesheet() -> str:
    """Applied to a _SciDoubleEdit or QSpinBox
    when its value is out of range."""
    return f"""
        QLineEdit {{
            background-color: rgba(244, 135, 113, 0.12);
            border: 1px solid {P.STATUS_ERROR};
            border-radius: {P.RADIUS_SM};
            color: {P.STATUS_ERROR};
            padding: 4px 8px;
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        QSpinBox {{
            background-color: rgba(244, 135, 113, 0.12);
            border: 1px solid {P.STATUS_ERROR};
            color: {P.STATUS_ERROR};
        }}
    """


def form_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_SECONDARY}; "
        f"font-size: {P.FONT_SIZE_SM}; "
        f"background: transparent;"
    )


def unit_label_stylesheet() -> str:
    return (
        f"color: {P.STATUS_INFO}; "
        f"font-size: {P.FONT_SIZE_SM}; "
        f"font-weight: bold; "
        f"font-family: {P.FONT_FAMILY_MONO}; "
        f"background: transparent; "
        f"min-width: 26px;"
    )


def segmented_btn_checked_stylesheet(compact: bool = False) -> str:
    """``compact`` shrinks the horizontal padding so many-option groups
    (e.g. the Graphs-page multiplier row) fit a narrow sidebar."""
    padding = "5px 4px" if compact else "5px 16px"
    return f"""
        QPushButton {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: 1px solid {P.ACCENT};
            padding: {padding};
            font-size: {P.FONT_SIZE_SM};
            font-weight: bold;
            border-radius: 0;
        }}
    """


def segmented_btn_unchecked_stylesheet(compact: bool = False) -> str:
    padding = "5px 4px" if compact else "5px 16px"
    return f"""
        QPushButton {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            padding: {padding};
            font-size: {P.FONT_SIZE_SM};
            border-radius: 0;
        }}
        QPushButton:hover {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
        }}
    """


def export_btn_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: none;
            border-radius: {P.RADIUS_MD};
            padding: 8px 22px;
            font-weight: bold;
            font-size: {P.FONT_SIZE_MD};
        }}
        QPushButton:hover {{ background-color: {P.ACCENT_HOVER}; }}
        QPushButton:pressed {{ background-color: {P.ACCENT_PRESSED}; }}
        QPushButton:disabled {{
            background-color: {P.BORDER};
            color: {P.TEXT_DISABLED};
        }}
    """


def error_bar_stylesheet() -> str:
    return f"""
        QLabel {{
            background-color: rgba(244, 135, 113, 0.15);
            color: {P.STATUS_ERROR};
            border: 1px solid {P.STATUS_ERROR};
            border-radius: {P.RADIUS_SM};
            padding: 6px 14px;
            font-size: {P.FONT_SIZE_SM};
        }}
    """


def sweep_spinbox_stylesheet() -> str:
    return f"""
        QSpinBox {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 4px 8px;
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        QSpinBox:focus {{ border-color: {P.ACCENT}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 16px;
            border: none;
            background: {P.BG_ELEVATED};
        }}
        QSpinBox:disabled {{
            color: {P.TEXT_DISABLED};
            border-color: {P.BG_ELEVATED};
        }}
    """


# ── Setup detail panel (Runs page) ───────────────────────────────────────


def meas_status_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_MD}; "
        f"background: transparent;"
    )


def config_preview_tree_stylesheet() -> str:
    return f"""
        QTreeWidget {{
            background-color: {P.BG_INPUT};
            alternate-background-color: {P.BG_PANEL};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
            outline: 0;
        }}
        QTreeWidget::item {{
            padding: 3px 4px;
            border: none;
        }}
        QTreeWidget::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        QHeaderView::section {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_SECONDARY};
            border: none;
            border-right: 1px solid {P.BORDER};
            border-bottom: 1px solid {P.BORDER};
            padding: 6px 10px;
            font-weight: bold;
            font-family: {P.FONT_FAMILY_UI};
        }}
    """


# ── Table View Page ──────────────────────────────────────────────────────


def table_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def data_table_stylesheet() -> str:
    return f"""
        QTableWidget {{
            background-color: {P.BG_INPUT};
            alternate-background-color: {P.BG_PANEL};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            gridline-color: {P.BORDER};
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        QHeaderView::section {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_SECONDARY};
            border: none;
            border-right: 1px solid {P.BORDER};
            border-bottom: 1px solid {P.BORDER};
            padding: 6px 10px;
            font-weight: bold;
        }}
        QTableWidget::item {{ padding: 2px 8px; }}
    """


def table_empty_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_LG}; "
        f"background: transparent;"
    )


def table_selector_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_MD}; "
        f"font-weight: bold; background: transparent;"
    )


def table_code_view_stylesheet() -> str:
    return f"""
        QPlainTextEdit {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            padding: 10px;
            font-family: {P.FONT_FAMILY_MONO};
            font-size: {P.FONT_SIZE_SM};
            selection-background-color: {P.ACCENT_MUTED};
        }}
    """


# ── Settings Dialog ──────────────────────────────────────────────────────


def settings_dialog_stylesheet() -> str:
    return f"""
        QDialog {{
            background-color: {P.BG_DEEP};
        }}
        QLabel {{
            color: {P.TEXT_SECONDARY};
            font-size: {P.FONT_SIZE_MD};
            background: transparent;
        }}
        QLabel#section {{
            color: {P.TEXT_PRIMARY};
            font-size: 14px;
            font-weight: bold;
        }}
        QLabel#hint {{
            color: {P.TEXT_DISABLED};
            font-size: {P.FONT_SIZE_XS};
            font-style: italic;
        }}
        QLineEdit {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 6px 10px;
            font-size: {P.FONT_SIZE_MD};
        }}
        QLineEdit:focus {{ border-color: {P.ACCENT}; }}
        QPlainTextEdit {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 6px 10px;
            font-size: {P.FONT_SIZE_MD};
        }}
        QPlainTextEdit:focus {{ border-color: {P.ACCENT}; }}
        QComboBox {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 6px 10px;
            font-size: {P.FONT_SIZE_MD};
        }}
        QComboBox:focus {{ border-color: {P.ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            selection-background-color: {P.ACCENT_MUTED};
            border: 1px solid {P.BORDER};
        }}
        QCheckBox {{
            color: {P.TEXT_SECONDARY};
            font-size: {P.FONT_SIZE_MD};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox:disabled {{ color: {P.TEXT_DISABLED}; }}
        QCheckBox::indicator {{
            width: 15px; height: 15px;
            border-radius: {P.RADIUS_SM};
            border: 1px solid {P.BORDER};
        }}
        QCheckBox::indicator:checked {{
            background-color: {P.ACCENT};
            border-color: {P.ACCENT};
        }}
        QPushButton {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 8px 18px;
            font-size: {P.FONT_SIZE_MD};
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {P.BG_ELEVATED};
            border-color: {P.ACCENT};
        }}
        QPushButton#primary {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: none;
        }}
        QPushButton#primary:hover {{ background-color: {P.ACCENT_HOVER}; }}
    """


# ── Measurement Runs (CRUD) Page ─────────────────────────────────────────


def runs_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def setup_summary_scroll_stylesheet() -> str:
    """Transparent scroll area wrapping the curated setup-summary cards."""
    return (
        "QScrollArea { background: transparent; border: none; } "
        "QScrollArea > QWidget > QWidget { background: transparent; }"
    )


def setup_summary_key_stylesheet() -> str:
    # Same tone as the setup-list card text (a touch lighter than muted).
    return (
        f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_SM}; "
        f"background: transparent;"
    )


def setup_summary_value_stylesheet() -> str:
    return (
        f"color: {P.TEXT_PRIMARY}; font-size: {P.FONT_SIZE_SM}; "
        f"font-weight: bold; background: transparent;"
    )


def setup_summary_chip_stylesheet(measured: bool = False) -> str:
    """Display-variable pill; measured variables are highlighted in accent,
    others stay transparent so they recede into the card."""
    bg = P.ACCENT_MUTED if measured else "transparent"
    fg = P.TEXT_WHITE if measured else P.TEXT_SECONDARY
    border = P.ACCENT if measured else P.BORDER
    return f"""
        QLabel {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: {P.RADIUS_SM};
            padding: 3px 11px;
            font-size: {P.FONT_SIZE_XS};
            font-weight: bold;
        }}
    """


def setup_summary_empty_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_MD}; "
        f"background: transparent; padding: 28px;"
    )


def runs_panel_title_stylesheet() -> str:
    return (
        f"color: {P.TEXT_PRIMARY}; font-size: 14px; font-weight: bold; "
        f"background: transparent;"
    )


def runs_list_stylesheet() -> str:
    return f"""
        QListWidget {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            font-size: {P.FONT_SIZE_SM};
            outline: 0;
            padding: 2px;
        }}
        QListWidget::item {{
            padding: 9px 10px;
            margin: 2px 0px;
            border-radius: {P.RADIUS_SM};
            border: 1px solid transparent;
        }}
        QListWidget::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
            border: 1px solid {P.ACCENT};
        }}
        QListWidget::item:hover:!selected {{
            background-color: {P.BG_ELEVATED};
        }}
    """


def runs_panel_stylesheet() -> str:
    """Framed container for each of the three Runs-page panes."""
    return f"""
        QFrame#runs_panel {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
        }}
    """


def runs_primary_button_stylesheet() -> str:
    """Prominent primary action button for the Runs toolbar."""
    return f"""
        QPushButton {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: none;
            border-radius: {P.RADIUS_MD};
            padding: 9px 18px;
            font-weight: bold;
            font-size: {P.FONT_SIZE_MD};
        }}
        QPushButton:hover {{ background-color: {P.ACCENT_HOVER}; }}
        QPushButton:pressed {{ background-color: {P.ACCENT_PRESSED}; }}
        QPushButton:disabled {{
            background-color: {P.BORDER};
            color: {P.TEXT_DISABLED};
        }}
    """


def runs_secondary_button_stylesheet() -> str:
    """Compact neutral button for per-panel actions (edit/delete/view…)."""
    return f"""
        QPushButton {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            padding: 5px 12px;
            font-size: {P.FONT_SIZE_SM};
        }}
        QPushButton:hover {{
            background-color: {P.BG_PANEL};
            border-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
        }}
        QPushButton:pressed {{ background-color: {P.ACCENT_MUTED}; }}
        QPushButton:disabled {{
            color: {P.TEXT_DISABLED};
            border-color: {P.BG_ELEVATED};
            background-color: {P.BG_DEEP};
        }}
    """


def runs_empty_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_MD}; "
        f"background: transparent; padding: 24px;"
    )


def runs_menu_button_stylesheet() -> str:
    """Three-dot (⋮) 'more actions' button in each Runs-page panel header."""
    return f"""
        QToolButton {{
            background-color: transparent;
            color: {P.TEXT_SECONDARY};
            border: 1px solid transparent;
            border-radius: {P.RADIUS_SM};
            padding: 0px 9px 5px 9px;
            font-size: {P.FONT_SIZE_XL};
            font-weight: bold;
        }}
        QToolButton:hover {{
            background-color: {P.BG_ELEVATED};
            border-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
        }}
        QToolButton:pressed {{ background-color: {P.ACCENT_MUTED}; }}
    """


def action_menu_stylesheet() -> str:
    """Popup frame for the custom ellipsis menu (ActionMenu)."""
    return f"""
        QFrame#action_menu {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
        }}
    """


def action_menu_item_stylesheet(available: bool = True) -> str:
    """One ActionMenu row.

    Available rows highlight in accent blue; unavailable rows stay hoverable
    (so their 'why disabled' tooltip can appear) but highlight in muted grey.
    """
    text = P.TEXT_SECONDARY if available else P.TEXT_DISABLED
    hover_bg = P.ACCENT_MUTED if available else P.BG_ELEVATED
    hover_text = P.TEXT_WHITE if available else P.TEXT_MUTED
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {text};
            border: none;
            border-radius: {P.RADIUS_SM};
            padding: 7px 16px 7px 10px;
            text-align: left;
            font-size: {P.FONT_SIZE_MD};
            font-weight: normal;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
            color: {hover_text};
        }}
    """


def action_menu_separator_stylesheet() -> str:
    return f"background-color: {P.BORDER}; border: none; max-height: 1px;"


# ── Documentation (tooltip icon, window, tree, viewer) ───────────────────────


def doc_tooltip_icon_stylesheet(size: int = 16) -> str:
    """Circular info ``ⓘ`` button — soft-white 'i' on a blue background."""
    radius = size // 2
    glyph = max(10, size - 5)
    return f"""
        QToolButton {{
            background-color: {P.ACCENT};
            color: #e8edf2;
            border: none;
            border-radius: {radius}px;
            font-family: Georgia, "Times New Roman", serif;
            font-style: italic;
            font-weight: bold;
            font-size: {glyph}px;
            padding: 0px;
        }}
        QToolButton:hover {{ background-color: {P.ACCENT_HOVER}; }}
        QToolButton:pressed {{ background-color: {P.ACCENT_PRESSED}; }}
    """


def documentation_window_stylesheet() -> str:
    return f"""
        QMainWindow, QWidget#doc_root {{
            background-color: {P.BG_DEEP};
        }}
        QSplitter::handle {{ background-color: {P.BORDER}; width: 1px; }}
    """


def documentation_tree_stylesheet() -> str:
    """Modern single-column nav tree: rounded hover/selection, roomy rows."""
    return f"""
        QTreeWidget {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: none;
            outline: 0;
            font-family: {P.FONT_FAMILY_UI};
            font-size: {P.FONT_SIZE_MD};
            padding: 8px 6px;
        }}
        QTreeWidget::item {{
            min-height: 24px;
            padding: 5px 6px;
            border: none;
            border-radius: {P.RADIUS_SM};
        }}
        QTreeWidget::item:hover {{
            background-color: {P.BG_ELEVATED};
        }}
        QTreeWidget::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        QTreeWidget::branch {{
            background: transparent;
        }}
    """


def documentation_viewer_stylesheet(font_px: int = 13) -> str:
    return f"""
        QTextBrowser {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_PRIMARY};
            border: none;
            padding: 12px 22px;
            font-family: {P.FONT_FAMILY_UI};
            font-size: {font_px}px;
        }}
    """


def documentation_zoom_bar_stylesheet() -> str:
    """Top-right zoom controls strip above the Markdown viewer."""
    return f"""
        QWidget#doc_zoombar {{
            background-color: {P.BG_DEEP};
            border-bottom: 1px solid {P.BORDER};
        }}
        QWidget#doc_zoombar QToolButton {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            min-width: 26px;
            min-height: 24px;
            font-family: {P.FONT_FAMILY_UI};
            font-size: 16px;
            font-weight: bold;
            padding: 0px;
        }}
        QWidget#doc_zoombar QToolButton:hover {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
            border-color: {P.ACCENT};
        }}
        QWidget#doc_zoombar QToolButton:pressed {{
            background-color: {P.ACCENT_MUTED};
        }}
        QWidget#doc_zoombar QToolButton:disabled {{
            color: {P.TEXT_DISABLED};
            border-color: {P.BORDER};
            background-color: {P.BG_DEEP};
        }}
    """


def documentation_document_css() -> str:
    """Default style sheet applied to the rendered Markdown (QTextDocument).

    Set via ``QTextBrowser.document().setDefaultStyleSheet(...)`` before
    ``setMarkdown`` so headings, links, code and tables follow the dark theme.
    """
    return f"""
        h1 {{ color: {P.TEXT_WHITE}; }}
        h2 {{ color: {P.STATUS_INFO}; }}
        h3 {{ color: {P.TEXT_PRIMARY}; }}
        a {{ color: {P.ACCENT_HOVER}; }}
        p, li {{ color: {P.TEXT_PRIMARY}; }}
        code {{
            background-color: {P.BG_INPUT};
            color: {P.STATUS_WARN};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        pre {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        blockquote {{ color: {P.TEXT_SECONDARY}; }}
        th {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
            padding: 6px 10px;
        }}
        td {{
            color: {P.TEXT_PRIMARY};
            padding: 6px 10px;
        }}
    """


# ── Measurement-config top bar & status widget ───────────────────────────────

_STATUS_COLORS = {
    "critical": P.STATUS_ERROR,
    "warning": P.STATUS_WARN,
    "info": P.STATUS_INFO,
    "ok": P.STATUS_OK,
    "muted": P.TEXT_MUTED,
}


def measurement_topbar_stylesheet() -> str:
    """Top bar of the setup pages.

    Scoped to ``QWidget#measurement_topbar`` (rather than a bare declaration)
    so the ``border-bottom`` stays on the bar itself and does not leak onto the
    child text labels as an underline.  Requires the widget to set
    ``WA_StyledBackground`` for the background to paint.
    """
    return (
        f"QWidget#measurement_topbar {{ "
        f"background-color: {P.BG_TOPBAR}; "
        f"border-bottom: 1px solid {P.BORDER}; }}"
    )


def measurement_topbar_title_stylesheet() -> str:
    return (
        f"color: {P.TEXT_PRIMARY}; font-size: {P.FONT_SIZE_XL}; "
        "font-weight: bold; background: transparent;"
    )


def measurement_status_card_stylesheet() -> str:
    """Clickable compact status card in the centre of the top bar."""
    return f"""
        QFrame#status_card {{
            background-color: {P.BG_INPUT};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
        }}
        QFrame#status_card:hover {{ border-color: {P.BORDER_FOCUS}; }}
        QFrame#status_card QLabel {{ background: transparent; }}
    """


def status_chip_stylesheet(kind: str) -> str:
    """Compact status chip text (critical/warning/info/ok/muted)."""
    color = _STATUS_COLORS.get(kind, P.TEXT_SECONDARY)
    return (
        f"QLabel {{ color: {color}; font-size: {P.FONT_SIZE_MD}; "
        "font-weight: bold; background: transparent; }"
    )


def status_column_title_stylesheet(kind: str) -> str:
    """Column heading in the status modal (critical/warning/info)."""
    color = _STATUS_COLORS.get(kind, P.TEXT_PRIMARY)
    return (
        f"QLabel {{ color: {color}; font-size: {P.FONT_SIZE_LG}; "
        "font-weight: bold; background: transparent; }"
    )


def status_modal_item_stylesheet(kind: str = "muted") -> str:
    """A single message/stat row inside the status modal."""
    color = _STATUS_COLORS.get(kind, P.TEXT_SECONDARY)
    return (
        f"QLabel {{ color: {color}; font-size: {P.FONT_SIZE_SM}; "
        "background: transparent; }"
    )


def status_modal_card_stylesheet(kind: str) -> str:
    """Status-modal column card with a colored accent stripe on the top edge.

    Mirrors ``section_card_stylesheet`` (the VAR1/VAR2 card look) but places
    the 3px stripe on the top instead of the left; the top corners are squared
    so the stripe ends flat instead of curling around the corner radius.  The
    stripe color follows the column identity (critical/warning/info).
    """
    accent = _STATUS_COLORS.get(kind, P.ACCENT)
    return f"""
        QFrame#status_modal_card {{
            background-color: {P.BG_ELEVATED};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
            border-top: 3px solid {accent};
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
        }}
    """


def status_modal_empty_stylesheet() -> str:
    """Muted, italic empty-state line inside a status-modal column."""
    return (
        f"QLabel {{ color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_SM}; "
        "font-style: italic; background: transparent; }"
    )


def status_modal_info_label_stylesheet() -> str:
    """Left-hand label of an Information row in the status modal."""
    return (
        f"QLabel {{ color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_SM}; "
        "background: transparent; }"
    )


def status_modal_info_value_stylesheet() -> str:
    """Right-hand bold value of an Information row in the status modal."""
    return (
        f"QLabel {{ color: {P.TEXT_PRIMARY}; font-size: {P.FONT_SIZE_SM}; "
        "font-weight: bold; background: transparent; }"
    )


# ── Graphs page ──────────────────────────────────────────────────────────


def graph_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def graph_scene_tabbar_stylesheet() -> str:
    """Top scene tabs (Scene 1, Scene 2, …) with closable tabs."""
    return f"""
        QTabBar {{
            background: transparent;
            font-size: {P.FONT_SIZE_SM};
        }}
        QTabBar::tab {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-bottom: none;
            border-top-left-radius: {P.RADIUS_SM};
            border-top-right-radius: {P.RADIUS_SM};
            padding: 5px 14px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {P.BG_ELEVATED};
        }}
        QTabBar::close-button {{
            subcontrol-position: right;
        }}
    """


def graph_add_scene_button_stylesheet() -> str:
    """The '+' button next to the scene tabs."""
    return f"""
        QToolButton {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            font-size: {P.FONT_SIZE_LG};
            font-weight: bold;
            padding: 0px 10px;
        }}
        QToolButton:hover {{
            background-color: {P.BG_ELEVATED};
            color: {P.TEXT_WHITE};
        }}
    """


def graph_sidebar_stylesheet() -> str:
    """The right sidebar: permanent Data / View / Analysis tabs."""
    return f"""
        QTabWidget::pane {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            top: -1px;
        }}
        QTabBar::tab {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-bottom: none;
            border-top-left-radius: {P.RADIUS_SM};
            border-top-right-radius: {P.RADIUS_SM};
            padding: 5px 16px;
            margin-right: 2px;
            font-size: {P.FONT_SIZE_SM};
        }}
        QTabBar::tab:selected {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_WHITE};
            font-weight: bold;
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {P.BG_ELEVATED};
        }}
    """


def _graph_thin_vscrollbar_qss() -> str:
    """Thin themed vertical scrollbar rules shared by the Graphs-page
    scroll surfaces (sidebar tabs, dataset tree, results lists)."""
    return f"""
        QScrollBar:vertical {{
            background: transparent;
            width: {P.SCROLLBAR_THIN}px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {P.BORDER};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {P.TEXT_DISABLED};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
    """


def graph_sidebar_scroll_stylesheet() -> str:
    """Sidebar tab scroll areas: transparent surface + thin gutter."""
    return f"""
        QScrollArea {{ background: transparent; border: none; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        {_graph_thin_vscrollbar_qss()}
    """


def graph_body_splitter_stylesheet() -> str:
    """Plot-area | sidebar splitter on the Graphs page."""
    return f"""
        QSplitter::handle:horizontal {{
            background-color: {P.BG_DEEP};
        }}
        QSplitter::handle:horizontal:hover {{
            background-color: {P.ACCENT_MUTED};
        }}
    """


def graph_tab_close_button_stylesheet() -> str:
    """Themed '✕' close button installed on each scene tab."""
    return f"""
        QToolButton {{
            background: transparent;
            color: {P.TEXT_MUTED};
            border: none;
            border-radius: {P.RADIUS_SM};
            font-size: {P.FONT_SIZE_XS};
            font-weight: bold;
        }}
        QToolButton:hover {{
            color: {P.STATUS_ERROR};
            background-color: {P.BG_ELEVATED};
        }}
    """


def graph_sidebar_toggle_stylesheet() -> str:
    """Slim edge button that collapses/expands the sidebar."""
    return f"""
        QToolButton {{
            background-color: {P.BG_PANEL};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            font-size: {P.FONT_SIZE_SM};
            font-weight: bold;
        }}
        QToolButton:hover {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
    """


def graph_dataset_tree_stylesheet() -> str:
    """Setups → executions tree with checkboxes on the Data tab."""
    return f"""
        QTreeWidget {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            outline: 0;
            font-size: {P.FONT_SIZE_SM};
            padding: 4px;
        }}
        QTreeWidget::item {{
            min-height: 20px;
            padding: 2px 4px;
            border: none;
            border-radius: {P.RADIUS_SM};
        }}
        QTreeWidget::item:hover {{
            background-color: {P.BG_ELEVATED};
        }}
        QTreeWidget::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        QTreeWidget::item:disabled {{
            color: {P.TEXT_DISABLED};
        }}
        {_graph_thin_vscrollbar_qss()}
    """


def graph_trace_row_stylesheet() -> str:
    """One per-trace styling row inside the View tab Traces section."""
    return f"""
        QFrame#trace_row {{
            background-color: {P.BG_INPUT};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
        }}
    """


def graph_color_swatch_stylesheet(color: str) -> str:
    """Clickable color swatch of a trace row (opens QColorDialog)."""
    return f"""
        QPushButton {{
            background-color: {color};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
        }}
        QPushButton:hover {{
            border: 1px solid {P.BORDER_FOCUS};
        }}
    """


def graph_results_list_stylesheet() -> str:
    """Fits / computed-traces lists on the Analysis tab."""
    return f"""
        QListWidget {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_SM};
            outline: 0;
            font-size: {P.FONT_SIZE_XS};
            font-family: {P.FONT_FAMILY_MONO};
        }}
        QListWidget::item {{
            padding: 3px 6px;
        }}
        QListWidget::item:selected {{
            background-color: {P.ACCENT_MUTED};
            color: {P.TEXT_WHITE};
        }}
        {_graph_thin_vscrollbar_qss()}
    """


def graph_analysis_message_stylesheet() -> str:
    """Amber explanatory banner (e.g. non-functional trace notice)."""
    return (
        f"QLabel {{ color: {P.STATUS_CAUTION}; "
        f"font-size: {P.FONT_SIZE_XS}; background: transparent; }}"
    )


def graph_cursor_readout_stylesheet() -> str:
    """Monospace cursor x/y (and Δ) readout label in the View tab."""
    return (
        f"QLabel {{ color: {P.STATUS_INFO}; font-size: {P.FONT_SIZE_XS}; "
        f"font-family: {P.FONT_FAMILY_MONO}; background: transparent; }}"
    )
