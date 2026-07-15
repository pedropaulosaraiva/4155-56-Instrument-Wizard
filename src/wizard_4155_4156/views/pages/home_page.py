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
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.models.project import ProjectData
from wizard_4155_4156.styles.icons import (
    AppIcon,
    AppIcon24,
    app_icon,
    hover_tinted_icon,
    tinted_pixmap,
)
from wizard_4155_4156.styles.stylesheets import (
    card_date_stylesheet,
    card_name_stylesheet,
    card_path_stylesheet,
    card_remove_button_stylesheet,
    card_thumbnail_stylesheet,
    clear_history_button_stylesheet,
    empty_projects_label_stylesheet,
    icon_chip_stylesheet,
    primary_action_button_stylesheet,
    project_card_stylesheet,
    quick_actions_panel_stylesheet,
    recent_panel_count_stylesheet,
    recent_panel_header_stylesheet,
    resource_button_stylesheet,
    section_title_stylesheet,
    splitter_stylesheet,
    subsection_title_stylesheet,
    version_label_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage

# =============================================================================
# PROJECT CARD
# =============================================================================


class ProjectCard(QFrame):
    """
    Single entry in the recent-projects grid.
    Hover reveals a remove (✕) button positioned absolutely in the
    top-right corner.
    """

    clicked = Signal(ProjectData)
    remove_requested = Signal(ProjectData)

    def __init__(
        self, project: ProjectData, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(P.CARD_WIDTH, P.CARD_HEIGHT)
        self._setup_ui()
        self._update_card_style()

    # ── Private ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Thumbnail
        thumb = QFrame()
        thumb.setFixedSize(200, 110)
        thumb.setStyleSheet(card_thumbnail_stylesheet())
        thumb_layout = QVBoxLayout(thumb)
        thumb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel()
        # 24px themed SVG scaled up — the 32px monochrome set is reserved
        # for the nav bar and the New/Open Project buttons.
        icon.setPixmap(app_icon(AppIcon24.BAR_CHART).pixmap(QSize(32, 32)))
        icon.setStyleSheet("background: transparent;")
        thumb_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(thumb, alignment=Qt.AlignmentFlag.AlignCenter)

        # Text info
        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_name = QLabel(self._project.name)
        self._lbl_name.setStyleSheet(card_name_stylesheet())
        self._lbl_name.setWordWrap(True)
        self._lbl_name.setMaximumWidth(200)
        info_layout.addWidget(self._lbl_name)

        self._lbl_path = QLabel(str(Path(self._project.path).parent))
        self._lbl_path.setStyleSheet(card_path_stylesheet())
        self._lbl_path.setWordWrap(True)
        self._lbl_path.setMaximumWidth(200)
        info_layout.addWidget(self._lbl_path)

        self._lbl_date = QLabel(
            self._project.last_modified.strftime("%d/%m/%Y  %H:%M")
        )
        self._lbl_date.setStyleSheet(card_date_stylesheet())
        info_layout.addWidget(self._lbl_date)

        layout.addWidget(info)

        # Remove button — absolutely positioned, hidden by default
        self._btn_remove = QToolButton(self)
        self._btn_remove.setIcon(
            hover_tinted_icon(
                AppIcon24.X, P.TEXT_SECONDARY, P.TEXT_ON_ACCENT, 12
            )
        )
        self._btn_remove.setIconSize(QSize(12, 12))
        self._btn_remove.setCursor(Qt.CursorShape.ArrowCursor)
        self._btn_remove.setStyleSheet(card_remove_button_stylesheet())
        self._btn_remove.setFixedSize(20, 20)
        self._btn_remove.move(192, 8)
        self._btn_remove.setVisible(False)
        self._btn_remove.clicked.connect(
            lambda: self.remove_requested.emit(self._project)
        )

    def _update_card_style(self) -> None:
        self.setStyleSheet(project_card_stylesheet(self._hovered))

    # ── Qt overrides ─────────────────────────────────────────────────────────

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._update_card_style()
        self._btn_remove.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self._update_card_style()
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
        self.setFixedWidth(260)
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
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(24)
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

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(
            f"color: {P.BORDER}; max-height: 1px; background: {P.BORDER};"
        )
        layout.addWidget(separator)

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

        version = QLabel("v0.2.0 — Wizard 4155/4156")
        version.setStyleSheet(version_label_stylesheet())
        version.setAlignment(Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(version)

        scroll.setWidget(container)
        outer.addWidget(scroll)

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
    """Scrollable grid of ProjectCard widgets."""

    project_selected = Signal(ProjectData)
    project_removed = Signal(str)  # emits path
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[ProjectCard] = []
        self._setup_ui()

    # ── Public display API (called by presenter) ─────────────────────────────

    def display_projects(self, projects: List[ProjectData]) -> None:
        """Re-render the grid from a fresh project list."""
        self._clear_grid()

        self._lbl_count.setText(f"({len(projects)})")

        if not projects:
            empty = QLabel(
                "No recent projects.\n"
                "Create a new project or open an existing one first."
            )
            empty.setStyleSheet(empty_projects_label_stylesheet())
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0, 1, P.CARD_COLUMNS)
            return

        for i, project in enumerate(projects):
            card = ProjectCard(project)
            card.clicked.connect(self.project_selected.emit)
            card.remove_requested.connect(
                lambda p: self.project_removed.emit(p.path)
            )
            self._cards.append(card)
            row, col = divmod(i, P.CARD_COLUMNS)
            self._grid.addWidget(card, row, col)

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
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(16)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():  # type: ignore
                item.widget().deleteLater()  # type: ignore
        self._cards.clear()

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
    project_opened          — user clicked a recent ProjectCard (emits path)
    project_remove_requested— user clicked ✕ on a card (emits path)
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
        splitter.addWidget(self._recent_panel)

        splitter.setSizes([260, 1020])
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
