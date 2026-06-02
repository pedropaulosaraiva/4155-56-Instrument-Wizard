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
