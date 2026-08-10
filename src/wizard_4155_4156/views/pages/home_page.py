"""
views/pages/home_page.py
------------------------
Home page view.  Contains only UI construction and signal declarations.
All business logic is handled by HomePresenter.

The view exposes:
    Signals  → user intents that the presenter subscribes to
    Methods  → display_* slots the presenter calls to update state
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.models.project import ProjectData, format_relative_time
from wizard_4155_4156.styles.icons import (
    AppIcon,
    AppIcon24,
    app_icon,
    hover_tinted_icon,
    logo_pixmap,
    tinted_pixmap,
)
from wizard_4155_4156.styles.stylesheets import (
    clear_history_button_stylesheet,
    empty_projects_label_stylesheet,
    icon_chip_stylesheet,
    primary_action_button_stylesheet,
    project_row_stylesheet,
    quick_actions_panel_stylesheet,
    recent_panel_count_stylesheet,
    recent_panel_header_stylesheet,
    resource_button_stylesheet,
    row_date_stylesheet,
    row_name_stylesheet,
    row_path_stylesheet,
    row_remove_button_stylesheet,
    section_title_stylesheet,
    splitter_stylesheet,
    subsection_title_stylesheet,
    version_label_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage

# =============================================================================
# PROJECT ROW
# =============================================================================


class ProjectRow(QFrame):
    """
    Single entry in the recent-projects list.

    Full-width row of fixed height: leading icon chip, two stacked text lines
    (project name over its folder), a relative date, and a remove (✕) button
    that appears on hover.  Nothing here has a fixed width — the row stretches
    to the panel and both text lines elide, so the list is unaffected by the
    display resolution.
    """

    clicked = Signal(ProjectData)
    remove_requested = Signal(ProjectData)

    def __init__(
        self, project: ProjectData, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._hovered = False
        self._full_name = project.name
        self._full_path = str(Path(project.path).parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(P.PROJECT_ROW_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.setToolTip(
            f"{project.path}\n"
            f"{project.last_modified.strftime('%d/%m/%Y  %H:%M')}"
        )
        self._setup_ui()
        self._update_row_style()

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 12, 10)
        row.setSpacing(14)

        # Leading chip — same accent-tinted affordance as the Start buttons.
        chip = QFrame()
        chip.setFixedSize(P.PROJECT_ROW_ICON, P.PROJECT_ROW_ICON)
        chip.setStyleSheet(icon_chip_stylesheet(P.ACCENT))
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel()
        icon.setPixmap(tinted_pixmap(AppIcon24.BAR_CHART, P.ACCENT, 20))
        icon.setStyleSheet("background: transparent;")
        chip_layout.addWidget(icon)
        row.addWidget(chip)

        # Name over folder path.  Both labels use an Ignored horizontal policy
        # so a long project name can never widen the row — they take whatever
        # width is left and elide inside it.
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._lbl_name = QLabel(self._full_name)
        self._lbl_name.setStyleSheet(row_name_stylesheet())
        self._lbl_name.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        text_col.addWidget(self._lbl_name)

        self._lbl_path = QLabel(self._full_path)
        self._lbl_path.setStyleSheet(row_path_stylesheet())
        self._lbl_path.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        text_col.addWidget(self._lbl_path)

        row.addLayout(text_col, stretch=1)

        self._lbl_date = QLabel(
            format_relative_time(self._project.last_modified)
        )
        self._lbl_date.setStyleSheet(row_date_stylesheet())
        self._lbl_date.setFixedWidth(P.PROJECT_ROW_DATE_WIDTH)
        self._lbl_date.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        row.addWidget(self._lbl_date)

        # Remove button inside a fixed-width holder: the slot is reserved even
        # while the button is hidden, so revealing it on hover shifts nothing.
        holder = QWidget()
        holder.setFixedWidth(24)
        holder.setStyleSheet("background: transparent;")
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_remove = QToolButton()
        self._btn_remove.setIcon(
            hover_tinted_icon(
                AppIcon24.X, P.TEXT_SECONDARY, P.TEXT_ON_ACCENT, 12
            )
        )
        self._btn_remove.setIconSize(QSize(12, 12))
        self._btn_remove.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_remove.setStyleSheet(row_remove_button_stylesheet())
        self._btn_remove.setFixedSize(20, 20)
        self._btn_remove.setToolTip("Remove from recent projects")
        self._btn_remove.setVisible(False)
        self._btn_remove.clicked.connect(
            lambda: self.remove_requested.emit(self._project)
        )
        holder_layout.addWidget(self._btn_remove)
        row.addWidget(holder)

    def _update_row_style(self) -> None:
        self.setStyleSheet(project_row_stylesheet(self._hovered))

    def _apply_elide(self) -> None:
        """Re-fit both text lines to the width the layout granted them."""
        self._lbl_name.setText(
            QFontMetrics(self._lbl_name.font()).elidedText(
                self._full_name,
                Qt.TextElideMode.ElideRight,
                self._lbl_name.width(),
            )
        )
        self._lbl_path.setText(
            QFontMetrics(self._lbl_path.font()).elidedText(
                self._full_path,
                Qt.TextElideMode.ElideMiddle,
                self._lbl_path.width(),
            )
        )

    # ── Qt overrides ─────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_elide()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._update_row_style()
        self._btn_remove.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._update_row_style()
        self._btn_remove.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._btn_remove.underMouse()
        ):
            self.clicked.emit(self._project)
        super().mousePressEvent(event)


# =============================================================================
# QUICK ACTIONS PANEL  (left sidebar inside home page)
# =============================================================================


class QuickActionsPanel(QFrame):
    """Start sidebar: New / Open buttons + resource links."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    settings_requested = Signal()
    documentation_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(P.HOME_SIDEBAR_WIDTH)
        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self) -> None:
        # Content lives in a scroll area so that on short windows the panel
        # grows a scrollbar instead of clipping its fixed-height buttons.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(P.HOME_SIDEBAR_SPACING)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        start_title = QLabel("Start")
        start_title.setStyleSheet(section_title_stylesheet())
        layout.addWidget(start_title)

        self.btn_new = self._make_primary_btn(
            AppIcon.NEW_PROJECT,
            P.ACCENT_HOVER,
            "New Project",
            "Create a new measurement configuration",
        )
        self.btn_new.clicked.connect(self.new_project_requested.emit)
        layout.addWidget(self.btn_new)

        self.btn_open = self._make_primary_btn(
            AppIcon.OPEN_PROJECT,
            P.STATUS_CAUTION,
            "Open Project",
            "Browse for existing project files",
        )
        self.btn_open.clicked.connect(self.open_project_requested.emit)
        layout.addWidget(self.btn_open)

        layout.addWidget(self._make_separator())

        res_title = QLabel("Resources")
        res_title.setStyleSheet(subsection_title_stylesheet())
        layout.addWidget(res_title)

        self.btn_docs = self._make_resource_btn(
            AppIcon24.BOOK, "Documentation"
        )
        self.btn_docs.clicked.connect(self.documentation_requested.emit)
        self.btn_settings = self._make_resource_btn(
            AppIcon24.SETTINGS, "Settings"
        )
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        self.btn_help = self._make_resource_btn(
            AppIcon24.HELP_CIRCLE, "Help & Support"
        )

        for btn in (self.btn_docs, self.btn_settings, self.btn_help):
            layout.addWidget(btn)

        layout.addStretch()

        # Brand footer — the institutional logo and the version line sit below
        # the stretch, so they pin to the bottom of the column.  The pixmap is
        # untinted (the light-theme variant is multi-color) and the label needs
        # an explicit transparent background: the panel stylesheet paints a
        # universal `*` background rule that would otherwise fill behind it.
        layout.addWidget(self._make_separator())

        logo = QLabel()
        logo.setPixmap(
            logo_pixmap(
                AppIcon.GREYC_LOGO, P.HOME_LOGO_WIDTH, P.HOME_LOGO_HEIGHT
            )
        )
        logo.setStyleSheet("background: transparent;")
        logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(logo)

        version = QLabel("v0.5.0 — Wizard 4155/4156")
        version.setStyleSheet(version_label_stylesheet())
        version.setAlignment(Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(version)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    @staticmethod
    def _make_separator() -> QFrame:
        """Hairline rule dividing the column into sections."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(
            f"color: {P.BORDER}; max-height: 1px; background: {P.BORDER};"
        )
        return separator

    @staticmethod
    def _make_primary_btn(
        icon: str, accent: str, title: str, desc: str
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(90)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(btn)
        row.setSpacing(14)
        row.setContentsMargins(16, 10, 16, 10)

        # Leading icon sits in a rounded, low-alpha tinted chip and is itself
        # tinted to the same accent — reads as an affordance, not a lone glyph.
        chip = QFrame()
        chip.setFixedSize(40, 40)
        chip.setStyleSheet(icon_chip_stylesheet(accent))
        chip_layout = QVBoxLayout(chip)
        chip_layout.setContentsMargins(0, 0, 0, 0)
        chip_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(tinted_pixmap(icon, accent, 22))
        icon_lbl.setStyleSheet("background: transparent;")
        chip_layout.addWidget(icon_lbl)
        row.addWidget(chip)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {P.TEXT_WHITE}; font-weight: bold; "
            f"font-size: {P.FONT_SIZE_LG}; background: transparent;"
        )
        col.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            f"color: {P.TEXT_MUTED}; font-size: {P.FONT_SIZE_SM}; "
            "background: transparent;"
        )
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)

        row.addLayout(col, stretch=1)
        btn.setStyleSheet(primary_action_button_stylesheet())
        return btn

    @staticmethod
    def _make_resource_btn(icon_path: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setIcon(app_icon(icon_path))
        btn.setIconSize(QSize(16, 16))
        btn.setStyleSheet(resource_button_stylesheet())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _apply_styles(self) -> None:
        self.setStyleSheet(quick_actions_panel_stylesheet())


# =============================================================================
# RECENT PROJECTS PANEL  (right grid inside home page)
# =============================================================================


class RecentProjectsPanel(QFrame):
    """Scrollable vertical list of ProjectRow widgets."""

    project_selected = Signal(ProjectData)
    project_removed = Signal(str)  # emits path
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ProjectRow] = []
        self._setup_ui()

    # ── Public display API (called by presenter) ─────────────────────────────

    def display_projects(self, projects: List[ProjectData]) -> None:
        """Re-render the list from a fresh project list."""
        self._clear_list()

        self._lbl_count.setText(f"({len(projects)})")

        if not projects:
            empty = QLabel(
                "No recent projects.\n"
                "Create a new project or open an existing one first."
            )
            empty.setStyleSheet(empty_projects_label_stylesheet())
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list.addWidget(empty)
        else:
            for project in projects:
                row = ProjectRow(project)
                row.clicked.connect(self.project_selected.emit)
                row.remove_requested.connect(
                    lambda p: self.project_removed.emit(p.path)
                )
                self._rows.append(row)
                self._list.addWidget(row)

        # Trailing stretch keeps rows packed to the top of the scroll area.
        self._list.addStretch()

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header row
        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)

        self._lbl_header = QLabel("Recent Projects")
        self._lbl_header.setStyleSheet(recent_panel_header_stylesheet())
        header_row.addWidget(self._lbl_header)

        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet(recent_panel_count_stylesheet())
        header_row.addWidget(self._lbl_count)
        header_row.addStretch()

        self._btn_clear = QPushButton("Clear History")
        self._btn_clear.setStyleSheet(clear_history_button_stylesheet())
        self._btn_clear.clicked.connect(self._on_clear_clicked)
        header_row.addWidget(self._btn_clear)

        layout.addWidget(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._container)
        self._list.setSpacing(8)
        self._list.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def _clear_list(self) -> None:
        # takeAt also yields the trailing stretch, whose widget() is None.
        while self._list.count():
            item = self._list.takeAt(0)
            widget = item.widget()  # type: ignore
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

    def _on_clear_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Remove all projects from recent history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_requested.emit()


# =============================================================================
# HOME PAGE  (composed view)
# =============================================================================


class HomePageView(BasePage):
    """
    Composed home page: QuickActionsPanel (left) + RecentProjectsPanel (right).
    The ConnectionTopBar is owned by MainWindow and sits above the page stack.

    Signals exposed to presenter
    ----------------------------
    new_project_requested   — user clicked "New Project"
    open_project_requested  — user clicked "Open Project"
    project_opened          — user clicked a recent ProjectRow (emits path)
    project_remove_requested— user clicked ✕ on a row (emits path)
    clear_history_requested — user confirmed "Clear History"
    """

    new_project_requested = Signal()
    open_project_requested = Signal()
    project_opened = Signal(str)  # path
    project_remove_requested = Signal(str)  # path
    clear_history_requested = Signal()
    settings_requested = Signal()
    documentation_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._connect_internal()

    # ── Display API (called by presenter) ────────────────────────────────────

    def display_recent_projects(self, projects: List[ProjectData]) -> None:
        self._recent_panel.display_projects(projects)

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._quick_actions = QuickActionsPanel()
        splitter.addWidget(self._quick_actions)

        self._recent_panel = RecentProjectsPanel()
        self._recent_panel.setMinimumWidth(P.RECENT_PANEL_MIN_WIDTH)
        splitter.addWidget(self._recent_panel)

        # All spare width goes to the list; the sidebar keeps its 260 px.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(1, False)
        splitter.setSizes([P.HOME_SIDEBAR_WIDTH, 1020])
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(splitter_stylesheet())

        layout.addWidget(splitter)

    def _connect_internal(self) -> None:
        """Forward inner-widget signals to this view's own signals."""
        self._quick_actions.new_project_requested.connect(
            self.new_project_requested
        )
        self._quick_actions.open_project_requested.connect(
            self.open_project_requested
        )
        self._recent_panel.project_selected.connect(
            lambda p: self.project_opened.emit(p.path)
        )
        self._recent_panel.project_removed.connect(
            self.project_remove_requested
        )
        self._recent_panel.clear_requested.connect(
            self.clear_history_requested
        )
        self._quick_actions.settings_requested.connect(self.settings_requested)
        self._quick_actions.documentation_requested.connect(
            self.documentation_requested
        )
