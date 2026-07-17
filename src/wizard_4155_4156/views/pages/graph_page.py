"""
views/pages/graph_page.py
-------------------------
The Graphs page: scene tabs on top, one shared scene body below.

Layout (per design sketch)
--------------------------
┌────────────────────────────────────────────────────────────┐
│ [Scene 1][Scene 2] [+]        Grid: [1]×[1] [x] Maximize   │
├──────────────────────────────────────╫───┬────────────────┤
│                                      ║ ‹ │ Data|Plot|Tools│
│        GraphPlotArea (grid of        ║   │ |Analysis      │
│        1×1 … 3×3 plots)   (splitter ─╫─) │ (GraphSidebar) │
└──────────────────────────────────────╨───┴────────────────┘

There is ONE plot area + sidebar pair for all scenes — the presenter
owns every scene's state and re-renders the body when the tab changes.

Passive view: this class only aggregates its children's signals into a
single page-level surface (the presenter connects here and nowhere
else) and delegates ``display_*`` calls back down.  Zero business logic.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QSplitter,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.icons import AppIcon24, hover_tinted_icon
from wizard_4155_4156.styles.stylesheets import (
    form_label_stylesheet,
    global_option_checkbox_stylesheet,
    graph_add_scene_button_stylesheet,
    graph_body_splitter_stylesheet,
    graph_page_stylesheet,
    graph_scene_tabbar_stylesheet,
    graph_sidebar_toggle_stylesheet,
    graph_tab_close_button_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages import BasePage
from wizard_4155_4156.views.widgets.config_sections import spinbox
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
    trace_width_changed = Signal(str, float)
    plot_font_size_changed = Signal(str, int)  # (element key, size in pt)

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
        # Close buttons are themed QToolButtons installed per tab in
        # display_scenes() — never Qt's native (platform-styled) icon.
        self._tab_bar.setTabsClosable(False)
        self._tab_bar.setUsesScrollButtons(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_bar.tabBarDoubleClicked.connect(self._on_tab_renamed)
        h.addWidget(self._tab_bar)

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip(tr_ui(TXT.GRAPH_TT_ADD_SCENE))
        add_btn.setStyleSheet(graph_add_scene_button_stylesheet())
        add_btn.clicked.connect(self.scene_add_requested)
        h.addWidget(add_btn)
        h.addStretch(1)

        # Scene-scoped grid controls live up here with the scene tabs —
        # not in the sidebar, whose tabs configure the ACTIVE plot only.
        grid_lbl = QLabel(tr_ui(TXT.GRAPH_LBL_GRID))
        grid_lbl.setStyleSheet(form_label_stylesheet())
        h.addWidget(grid_lbl)
        self._rows_spin = spinbox(1, 3, 1)
        self._rows_spin.setToolTip(tr_ui(TXT.GRAPH_TT_GRID_ROWS))
        h.addWidget(self._rows_spin)
        times_lbl = QLabel("×")
        times_lbl.setStyleSheet(form_label_stylesheet())
        h.addWidget(times_lbl)
        self._cols_spin = spinbox(1, 3, 1)
        self._cols_spin.setToolTip(tr_ui(TXT.GRAPH_TT_GRID_COLS))
        h.addWidget(self._cols_spin)
        h.addSpacing(12)
        self._maximize_chk = QCheckBox(tr_ui(TXT.GRAPH_CHK_MAXIMIZE))
        self._maximize_chk.setStyleSheet(global_option_checkbox_stylesheet())
        h.addWidget(self._maximize_chk)

        self._rows_spin.valueChanged.connect(self._emit_grid)
        self._cols_spin.valueChanged.connect(self._emit_grid)
        self._maximize_chk.toggled.connect(self.maximize_toggled)
        return bar

    def _emit_grid(self) -> None:
        self.grid_layout_changed.emit(
            self._rows_spin.value(), self._cols_spin.value()
        )

    #: Width of the collapse strip inside the splitter's right pane
    #: (toggle button + layout spacing) — kept when the sidebar hides.
    _TOGGLE_STRIP_WIDTH = 18 + 6

    def _build_body(self) -> QWidget:
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setStyleSheet(graph_body_splitter_stylesheet())
        self._splitter.setHandleWidth(6)
        self._splitter.setChildrenCollapsible(False)

        self.plot_area = GraphPlotArea()
        self.plot_area.setMinimumWidth(P.GRAPH_PLOT_MIN_WIDTH)
        self._splitter.addWidget(self.plot_area)

        # The toggle strip travels with the sidebar in one right pane so
        # collapsing leaves only the strip visible.
        right = QWidget()
        h = QHBoxLayout(right)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

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
        self._splitter.addWidget(right)

        self._splitter.setStretchFactor(0, 1)  # window growth → plot
        self._splitter.setStretchFactor(1, 0)
        self._saved_sidebar_size = (
            P.GRAPH_SIDEBAR_WIDTH + self._TOGGLE_STRIP_WIDTH
        )
        self._splitter.setSizes([10_000, self._saved_sidebar_size])
        return self._splitter

    def _chain_signals(self) -> None:
        """Re-emit every child signal at page level (presenter contract)."""
        area = self.plot_area
        area.plot_activated.connect(self.plot_activated)
        area.roi_region_changed.connect(self.roi_region_changed)
        area.cursor_dragged.connect(self.cursor_dragged)

        data = self.sidebar.data_tab
        data.execution_check_changed.connect(self.execution_check_changed)

        plot = self.sidebar.plot_tab
        plot.x_variable_changed.connect(self.x_variable_changed)
        plot.y_variable_changed.connect(self.y_variable_changed)
        plot.axis_autoscale_changed.connect(self.axis_autoscale_changed)
        plot.axis_log_changed.connect(self.axis_log_changed)
        plot.axis_min_committed.connect(self.axis_min_committed)
        plot.axis_max_committed.connect(self.axis_max_committed)
        plot.axis_multiplier_changed.connect(self.axis_multiplier_changed)
        plot.plot_title_committed.connect(self.plot_title_committed)
        plot.axis_label_committed.connect(self.axis_label_committed)
        plot.trace_visibility_changed.connect(self.trace_visibility_changed)
        plot.trace_color_changed.connect(self.trace_color_changed)
        plot.trace_renamed.connect(self.trace_renamed)
        plot.trace_line_style_changed.connect(self.trace_line_style_changed)
        plot.trace_marker_changed.connect(self.trace_marker_changed)
        plot.trace_width_changed.connect(self.trace_width_changed)
        plot.plot_font_size_changed.connect(self.plot_font_size_changed)

        tools = self.sidebar.tools_tab
        tools.reset_view_requested.connect(self.reset_view_requested)
        tools.mouse_mode_changed.connect(self.mouse_mode_changed)
        tools.cursor_mode_changed.connect(self.cursor_mode_changed)
        tools.cursor_source_changed.connect(self.cursor_source_changed)
        tools.roi_enabled_changed.connect(self.roi_enabled_changed)
        tools.export_requested.connect(self.export_requested)

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
        # A single scene must stay open — no close button then.
        closable = len(names) > 1
        for index, name in enumerate(names):
            self._tab_bar.addTab(name)
            self._tab_bar.setTabToolTip(index, tr_ui(TXT.GRAPH_TT_RENAME_HINT))
            if closable:
                self._tab_bar.setTabButton(
                    index,
                    QTabBar.ButtonPosition.RightSide,
                    self._make_close_button(index),
                )
        self._tab_bar.setCurrentIndex(current)
        self._tab_bar.blockSignals(False)

    def _make_close_button(self, index: int) -> QWidget:
        """Themed close button replacing Qt's native close icon.  Tabs are
        fully rebuilt on every display_scenes, so the captured index is
        safe."""
        btn = QToolButton()
        # 10 px icon in the 16 px circle — even margins center it exactly
        # (an odd leftover shifts the glyph 1 px right/down).
        btn.setIcon(
            hover_tinted_icon(
                AppIcon24.X, P.TEXT_SECONDARY, P.TEXT_ON_ACCENT, 10
            )
        )
        btn.setIconSize(QSize(10, 10))
        btn.setFixedSize(16, 16)
        btn.setToolTip(tr_ui(TXT.GRAPH_CLOSE_SCENE_TITLE))
        btn.setStyleSheet(graph_tab_close_button_stylesheet())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(
            lambda _c=False, i=index: self.scene_close_requested.emit(i)
        )
        # QTabBar pins the side widget to the tab's outer right edge, which
        # leaves the circle hanging off the rounded tab — a right margin on
        # a transparent wrapper pulls it back inside.
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(0)
        lay.addWidget(btn)
        return wrapper

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
        return self.plot_area.export_plot_png(
            slot_index, path, self.sidebar.tools_tab.export_background()
        )

    def export_scene_png(self, path: str) -> bool:
        return self.plot_area.export_scene_png(
            path, self.sidebar.tools_tab.export_background()
        )

    # ── Data tab ─────────────────────────────────────────────────────────────

    def display_datasets(self, groups) -> None:
        self.sidebar.data_tab.display_datasets(groups)

    # ── Scene bar (grid controls) ────────────────────────────────────────────

    def display_grid(self, rows: int, cols: int, maximized: bool) -> None:
        for widget in (self._rows_spin, self._cols_spin, self._maximize_chk):
            widget.blockSignals(True)
        self._rows_spin.setValue(rows)
        self._cols_spin.setValue(cols)
        self._maximize_chk.setChecked(maximized)
        for widget in (self._rows_spin, self._cols_spin, self._maximize_chk):
            widget.blockSignals(False)

    # ── Plot tab ─────────────────────────────────────────────────────────────

    def display_variables(self, options, x_var, y_var) -> None:
        self.sidebar.plot_tab.display_variables(options, x_var, y_var)

    def display_axis(self, axis: str, cfg: dict) -> None:
        self.sidebar.plot_tab.display_axis(axis, cfg)

    def display_labels(self, title, x_label, y_label) -> None:
        self.sidebar.plot_tab.display_labels(title, x_label, y_label)

    def display_fonts(self, fonts: dict) -> None:
        self.sidebar.plot_tab.display_fonts(fonts)

    def display_traces(self, specs: list[dict]) -> None:
        self.sidebar.plot_tab.display_traces(specs)

    # ── Tools tab ────────────────────────────────────────────────────────────

    def display_tools(
        self, mouse_mode, cursor_mode, cursor_source_id, roi_enabled
    ) -> None:
        self.sidebar.tools_tab.display_tools(
            mouse_mode, cursor_mode, cursor_source_id, roi_enabled
        )

    def display_cursor_trace_options(self, options, current) -> None:
        self.sidebar.tools_tab.display_trace_options(options, current)

    def display_cursor_readout(self, text: str) -> None:
        self.sidebar.tools_tab.display_cursor_readout(text)

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

    def set_fit_roi_enabled(self, enabled: bool) -> None:
        self.sidebar.analysis_tab.set_fit_roi_enabled(enabled)

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
            tr_ui(TXT.GRAPH_RENAME_TITLE),
            tr_ui(TXT.GRAPH_RENAME_LABEL),
            text=self._tab_bar.tabText(index),
        )
        if ok and name.strip():
            self.scene_renamed.emit(index, name.strip())

    def _toggle_sidebar(self) -> None:
        visible = self.sidebar.isVisible()
        total = sum(self._splitter.sizes())
        if visible:
            # Hiding the sidebar removes its minimum width from the
            # splitter's solver, so only the toggle strip remains.
            self._saved_sidebar_size = self._splitter.sizes()[1]
            self.sidebar.setVisible(False)
            self._splitter.setSizes(
                [total - self._TOGGLE_STRIP_WIDTH, self._TOGGLE_STRIP_WIDTH]
            )
        else:
            self.sidebar.setVisible(True)
            self._splitter.setSizes(
                [total - self._saved_sidebar_size, self._saved_sidebar_size]
            )
        self._splitter.handle(1).setEnabled(not visible)
        self._toggle_btn.setText("‹" if visible else "›")
