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


def unit_group_header_stylesheet() -> str:
    return (
        f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_XS}; "
        f"font-weight: bold; letter-spacing: 2px; background: transparent;"
    )


def unit_group_separator_stylesheet() -> str:
    return f"background-color: {P.BORDER}; max-height: 1px;"


def unit_card_enabled_stylesheet(hover: bool = False) -> str:
    border_color = P.ACCENT if hover else P.BORDER
    return f"""
        QFrame#unit_card {{
            background-color: {P.BG_PANEL};
            border: 1px solid {border_color};
            border-radius: {P.RADIUS_LG};
        }}
    """


def unit_card_disabled_stylesheet(hover: bool = False) -> str:
    border_color = P.ACCENT if hover else P.BG_ELEVATED
    return f"""
        QFrame#unit_card {{
            background-color: {P.BG_DEEP};
            border: 1px solid {border_color};
            border-radius: {P.RADIUS_LG};
        }}
    """


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


# ── Sweep Config Page ────────────────────────────────────────────────────────


def sweep_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def sweep_section_card_stylesheet() -> str:
    return f"""
        QFrame#section_card {{
            background-color: {P.BG_PANEL};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_LG};
        }}
    """


def channel_row_badge_stylesheet(color: str) -> str:
    return (
        f"color: {color}; font-size: {P.FONT_SIZE_XS}; font-weight: bold; "
        f"background: transparent; padding: 2px 8px; "
        f"border: 1px solid {color}; border-radius: {P.RADIUS_SM};"
    )


def input_error_stylesheet() -> str:
    """Applied to a _SciDoubleEdit or QSpinBox when its value is out of range."""
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


def sweep_form_label_stylesheet() -> str:
    return f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_SM}; background: transparent;"


def sweep_unit_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_DISABLED}; font-size: {P.FONT_SIZE_SM}; "
        f"font-family: {P.FONT_FAMILY_MONO}; background: transparent; min-width: 26px;"
    )


def segmented_btn_checked_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: {P.ACCENT};
            color: {P.TEXT_WHITE};
            border: 1px solid {P.ACCENT};
            padding: 5px 16px;
            font-size: {P.FONT_SIZE_SM};
            font-weight: bold;
            border-radius: 0;
        }}
    """


def segmented_btn_unchecked_stylesheet() -> str:
    return f"""
        QPushButton {{
            background-color: {P.BG_DEEP};
            color: {P.TEXT_SECONDARY};
            border: 1px solid {P.BORDER};
            padding: 5px 16px;
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
        QSpinBox:disabled {{ color: {P.TEXT_DISABLED}; border-color: {P.BG_ELEVATED}; }}
    """


# ── Measurements & Run Page ──────────────────────────────────────────────


def measurements_page_stylesheet() -> str:
    return f"background-color: {P.BG_DEEP};"


def meas_source_label_stylesheet() -> str:
    return (
        f"color: {P.TEXT_SECONDARY}; font-size: {P.FONT_SIZE_MD}; "
        f"font-weight: bold; background: transparent;"
    )


def meas_summary_box_stylesheet() -> str:
    return f"""
        QLabel {{
            background-color: {P.BG_INPUT};
            color: {P.TEXT_PRIMARY};
            border: 1px solid {P.BORDER};
            border-radius: {P.RADIUS_MD};
            padding: 10px 14px;
            font-size: {P.FONT_SIZE_SM};
            font-family: {P.FONT_FAMILY_MONO};
        }}
    """


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
