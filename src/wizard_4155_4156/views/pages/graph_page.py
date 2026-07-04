"""
views/pages/graph_page.py
-------------------------
The Graphs page: scene tabs on top, one shared scene body below.

Layout (per design sketch)
--------------------------
┌────────────────────────────────────────────────────────────┐
│ [Scene 1][Scene 2][Scene 3]                  [+]           │
├──────────────────────────────────────┬───┬────────────────┤
│                                      │ ‹ │  Data|View|Anal│
│        GraphPlotArea (grid of        │   │  (GraphSidebar)│
│        1×1 … 3×3 plots)              │   │                │
└──────────────────────────────────────┴───┴────────────────┘

There is ONE plot area + sidebar pair for all scenes — the presenter
owns every scene's state and re-renders the body when the tab changes.

Passive view: this class only aggregates its children's signals into a
single page-level surface (the presenter connects here and nowhere
else) and delegates ``display_*`` calls back down.  Zero business logic.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.stylesheets import (
    graph_add_scene_button_stylesheet,
    graph_page_stylesheet,
    graph_scene_tabbar_stylesheet,
    graph_sidebar_toggle_stylesheet,
)
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.graph_plot_area import GraphPlotArea
from wizard_4155_4156.views.widgets.graph_sidebar import GraphSidebar


class GraphPageView(BasePage):
    """Scene tabs + plot grid + collapsible configuration sidebar."""

    # ── Page lifecycle / scenes ──────────────────────────────────────────────
    page_activated = Signal()
    scene_add_requested = Signal()
    scene_close_requested = Signal(int)
    scene_changed = Signal(int)
    scene_renamed = Signal(int, str)

    # ── Plot area ────────────────────────────────────────────────────────────
    plot_activated = Signal(int)
    roi_region_changed = Signal(int, float, float)  # (slot, lo, hi)
    cursor_dragged = Signal(int, int, float)  # (slot, cursor, x)

    # ── Data tab ─────────────────────────────────────────────────────────────
    execution_check_changed = Signal(int, bool)
    grid_layout_changed = Signal(int, int)
    maximize_toggled = Signal(bool)
    x_variable_changed = Signal(str)
    y_variable_changed = Signal(str)
    axis_autoscale_changed = Signal(str, bool)
    axis_log_changed = Signal(str, bool)
    axis_min_committed = Signal(str, float)
    axis_max_committed = Signal(str, float)
    axis_multiplier_changed = Signal(str, str)

    # ── View tab ─────────────────────────────────────────────────────────────
    reset_view_requested = Signal()
    mouse_mode_changed = Signal(str)
    cursor_mode_changed = Signal(str)
    cursor_source_changed = Signal(str)
    roi_enabled_changed = Signal(bool)
    export_requested = Signal(str)
    plot_title_committed = Signal(str)
    axis_label_committed = Signal(str, str)
    trace_visibility_changed = Signal(str, bool)
    trace_color_changed = Signal(str, str)
    trace_renamed = Signal(str, str)
    trace_line_style_changed = Signal(str, str)
    trace_marker_changed = Signal(str, str)

    # ── Analysis tab ─────────────────────────────────────────────────────────
    fit_requested = Signal(str, str, int, bool)
    fit_removed = Signal(str)
    math_requested = Signal(str, str, str)
    computed_trace_removed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(graph_page_stylesheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(6)
        root.addWidget(self._build_scene_bar())
        root.addWidget(self._build_body(), stretch=1)
        self._chain_signals()

    def on_activate(self) -> None:
        self.page_activated.emit()

    # =========================================================================
    # Build helpers
    # =========================================================================

    def _build_scene_bar(self) -> QWidget:
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self._tab_bar = QTabBar()
        self._tab_bar.setStyleSheet(graph_scene_tabbar_stylesheet())
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabCloseRequested.connect(self.scene_close_requested)
        self._tab_bar.tabBarDoubleClicked.connect(self._on_tab_renamed)
        h.addWidget(self._tab_bar)

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip(tr_ui(TXT.GRAPH_TT_ADD_SCENE))
        add_btn.setStyleSheet(graph_add_scene_button_stylesheet())
        add_btn.clicked.connect(self.scene_add_requested)
        h.addWidget(add_btn)
        h.addStretch(1)
        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        self.plot_area = GraphPlotArea()
        h.addWidget(self.plot_area, stretch=1)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("›")
        self._toggle_btn.setToolTip(tr_ui(TXT.GRAPH_TT_TOGGLE_SIDEBAR))
        self._toggle_btn.setStyleSheet(graph_sidebar_toggle_stylesheet())
        self._toggle_btn.setFixedWidth(18)
        self._toggle_btn.setMinimumHeight(60)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        h.addWidget(self._toggle_btn)

        self.sidebar = GraphSidebar()
        h.addWidget(self.sidebar)
        return body

    def _chain_signals(self) -> None:
        """Re-emit every child signal at page level (presenter contract)."""
        area = self.plot_area
        area.plot_activated.connect(self.plot_activated)
        area.roi_region_changed.connect(self.roi_region_changed)
        area.cursor_dragged.connect(self.cursor_dragged)

        data = self.sidebar.data_tab
        data.execution_check_changed.connect(self.execution_check_changed)
        data.grid_layout_changed.connect(self.grid_layout_changed)
        data.maximize_toggled.connect(self.maximize_toggled)
        data.x_variable_changed.connect(self.x_variable_changed)
        data.y_variable_changed.connect(self.y_variable_changed)
        data.axis_autoscale_changed.connect(self.axis_autoscale_changed)
        data.axis_log_changed.connect(self.axis_log_changed)
        data.axis_min_committed.connect(self.axis_min_committed)
        data.axis_max_committed.connect(self.axis_max_committed)
        data.axis_multiplier_changed.connect(self.axis_multiplier_changed)

        view = self.sidebar.view_tab
        view.reset_view_requested.connect(self.reset_view_requested)
        view.mouse_mode_changed.connect(self.mouse_mode_changed)
        view.cursor_mode_changed.connect(self.cursor_mode_changed)
        view.cursor_source_changed.connect(self.cursor_source_changed)
        view.roi_enabled_changed.connect(self.roi_enabled_changed)
        view.export_requested.connect(self.export_requested)
        view.plot_title_committed.connect(self.plot_title_committed)
        view.axis_label_committed.connect(self.axis_label_committed)
        view.trace_visibility_changed.connect(self.trace_visibility_changed)
        view.trace_color_changed.connect(self.trace_color_changed)
        view.trace_renamed.connect(self.trace_renamed)
        view.trace_line_style_changed.connect(self.trace_line_style_changed)
        view.trace_marker_changed.connect(self.trace_marker_changed)

        analysis = self.sidebar.analysis_tab
        analysis.fit_requested.connect(self.fit_requested)
        analysis.fit_removed.connect(self.fit_removed)
        analysis.math_requested.connect(self.math_requested)
        analysis.computed_trace_removed.connect(self.computed_trace_removed)

    # =========================================================================
    # Public display API (thin delegation — presenter calls only these)
    # =========================================================================

    # ── Scenes ───────────────────────────────────────────────────────────────

    def display_scenes(self, names: list[str], current: int) -> None:
        self._tab_bar.blockSignals(True)
        while self._tab_bar.count():
            self._tab_bar.removeTab(0)
        for name in names:
            self._tab_bar.addTab(name)
        self._tab_bar.setCurrentIndex(current)
        # A single scene must stay open — hide its close button.
        closable = len(names) > 1
        self._tab_bar.setTabsClosable(closable)
        self._tab_bar.blockSignals(False)

    # ── Plot area ────────────────────────────────────────────────────────────

    def display_scene(
        self,
        specs,
        rows: int,
        cols: int,
        active: int,
        maximized: bool,
        scene_token: int,
    ) -> None:
        self.plot_area.display_scene(
            specs, rows, cols, active, maximized, scene_token
        )

    def display_cursor(
        self, slot: int, cursor_index: int, x: float, y: float, text: str
    ) -> None:
        self.plot_area.display_cursor(slot, cursor_index, x, y, text)

    def reset_plot_view(self, slot_index: int) -> None:
        self.plot_area.reset_view(slot_index)

    def export_plot_png(self, slot_index: int, path: str) -> bool:
        return self.plot_area.export_plot_png(slot_index, path)

    # ── Data tab ─────────────────────────────────────────────────────────────

    def display_datasets(self, groups) -> None:
        self.sidebar.data_tab.display_datasets(groups)

    def display_variables(self, options, x_var, y_var) -> None:
        self.sidebar.data_tab.display_variables(options, x_var, y_var)

    def display_axis(self, axis: str, cfg: dict) -> None:
        self.sidebar.data_tab.display_axis(axis, cfg)

    def display_grid(self, rows: int, cols: int, maximized: bool) -> None:
        self.sidebar.data_tab.display_grid(rows, cols, maximized)

    # ── View tab ─────────────────────────────────────────────────────────────

    def display_tools(
        self, mouse_mode, cursor_mode, cursor_source_id, roi_enabled
    ) -> None:
        self.sidebar.view_tab.display_tools(
            mouse_mode, cursor_mode, cursor_source_id, roi_enabled
        )

    def display_labels(self, title, x_label, y_label) -> None:
        self.sidebar.view_tab.display_labels(title, x_label, y_label)

    def display_traces(self, specs: list[dict]) -> None:
        self.sidebar.view_tab.display_traces(specs)

    def display_cursor_trace_options(self, options, current) -> None:
        self.sidebar.view_tab.display_trace_options(options, current)

    def display_cursor_readout(self, text: str) -> None:
        self.sidebar.view_tab.display_cursor_readout(text)

    # ── Analysis tab ─────────────────────────────────────────────────────────

    def set_fit_models(self, models) -> None:
        self.sidebar.analysis_tab.set_fit_models(models)

    def set_operations(
        self, categories, by_category, binary_categories
    ) -> None:
        self.sidebar.analysis_tab.set_operations(
            categories, by_category, binary_categories
        )

    def display_analysis_trace_options(self, options) -> None:
        self.sidebar.analysis_tab.display_trace_options(options)

    def display_fits(self, entries) -> None:
        self.sidebar.analysis_tab.display_fits(entries)

    def display_computed(self, entries) -> None:
        self.sidebar.analysis_tab.display_computed(entries)

    def display_analysis_message(self, text: str) -> None:
        self.sidebar.analysis_tab.display_analysis_message(text)

    def set_analysis_enabled(self, enabled: bool) -> None:
        self.sidebar.analysis_tab.set_analysis_enabled(enabled)

    # =========================================================================
    # Internals
    # =========================================================================

    def _on_tab_changed(self, index: int) -> None:
        if index >= 0:
            self.scene_changed.emit(index)

    def _on_tab_renamed(self, index: int) -> None:
        if index < 0:
            return
        name, ok = QInputDialog.getText(
            self,
            tr_ui(TXT.GRAPH_SCENE_DEFAULT).format(n=index + 1),
            "",
            text=self._tab_bar.tabText(index),
        )
        if ok and name.strip():
            self.scene_renamed.emit(index, name.strip())

    def _toggle_sidebar(self) -> None:
        visible = self.sidebar.isVisible()
        self.sidebar.setVisible(not visible)
        self._toggle_btn.setText("‹" if visible else "›")
