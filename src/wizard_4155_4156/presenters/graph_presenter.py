"""
presenters/graph_presenter.py
-----------------------------
Presenter for the Graphs page.

Owns ALL page state — a list of ``SceneConfig`` (scenes → 3×3 plot
slots → traces) — and mediates it between:

* **GraphPageView** — passive widgets that emit user intent and render
  whatever ``display_*`` pushes at them;
* **the project database** — executions to plot (read-only) and the
  ``graph_scene`` table where every scene is persisted as JSON;
* **models/graph** — the pure math layer (functional normalization,
  trace operations, curve fitting).

Persistence is a debounced autosave: every mutation restarts a 600 ms
single-shot timer; ``flush_pending_save()`` (called by MainWindow before
a project switch) forces the write.  Derived traces persist only their
definitions and are recomputed on load.

No live-data path by design: the dataset selector offers DB executions
only, so this presenter never subscribes to ``data_ready``.  All DB
access happens on the GUI thread (mirrors TablePresenter).
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from wizard_4155_4156.db.assembler import execution_to_data_dict
from wizard_4155_4156.db.repository import (
    ExecutionRepository,
    GraphSceneRepository,
    SetupRepository,
)
from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.models.data_export import to_csv
from wizard_4155_4156.models.graph.config import (
    AxisConfig,
    Multiplier,
    PlotConfig,
    SceneConfig,
    axis_label,
    axis_scale,
    variables_compatible,
)
from wizard_4155_4156.models.graph.fitting import (
    FIT_MODELS,
    FitError,
    run_fit,
)
from wizard_4155_4156.models.graph.functional import (
    NonFunctionalTraceError,
    nearest_point,
)
from wizard_4155_4156.models.graph.trace import (
    Trace,
    TraceKind,
    TraceStyle,
    traces_to_dataset,
)
from wizard_4155_4156.models.graph.trace_math import (
    OPERATIONS,
    OpCategory,
    TraceMathError,
    apply_operation,
    operations_in,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.pages.graph_page import GraphPageView
from wizard_4155_4156.views.widgets.graph_plot_area import (
    PlotRenderSpec,
    TraceRenderSpec,
)

_AUTOSAVE_MS = 600

_CATEGORY_LABELS = {
    OpCategory.DERIVATIVE: TXT.GRAPH_CAT_DERIVATIVE,
    OpCategory.UNARY: TXT.GRAPH_CAT_UNARY,
    OpCategory.BINARY: TXT.GRAPH_CAT_BINARY,
}


def _fmt(value: float) -> str:
    return f"{value:.6g}"


class GraphPresenter(QObject):
    """Mediates GraphPageView ↔ project DB + the graph math models."""

    def __init__(
        self,
        view: GraphPageView,
        project_manager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._projects = project_manager

        self._scenes: list[SceneConfig] = [self._default_scene(1)]
        self._scene_index = 0

        # Runtime caches (never persisted).
        self._data_cache: dict[int, dict[str, list[float]]] = {}
        self._var_names: dict[int, list[str]] = {}
        self._exec_labels: dict[int, str] = {}
        self._cursor_points: dict[int, tuple[float, float]] = {}
        self._pending_renders: set[str] = set()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_AUTOSAVE_MS)
        self._save_timer.timeout.connect(self._save_now)

        self._push_registries()
        self._connect()

    # =========================================================================
    # Public API (called by MainWindow)
    # =========================================================================

    def set_database(self, _db=None) -> None:
        """Reload everything when a project is created/opened/closed."""
        self._save_timer.stop()
        self._data_cache.clear()
        self._var_names.clear()
        self._exec_labels.clear()
        self._cursor_points.clear()
        self._load_scenes()
        self._render_all()

    def flush_pending_save(self) -> None:
        """Write any pending scene changes immediately (project switch)."""
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._save_now()

    # =========================================================================
    # Wiring
    # =========================================================================

    def _push_registries(self) -> None:
        """Feed the Analysis tab from the model registries (extensible)."""
        self._view.set_fit_models(
            [
                (m.model_id, m.label, m.has_degree, m.min_degree, m.max_degree)
                for m in FIT_MODELS.values()
            ]
        )
        categories = [
            (cat.value, tr_ui(_CATEGORY_LABELS[cat])) for cat in OpCategory
        ]
        by_category = {
            cat.value: [(op.op_id, op.label) for op in operations_in(cat)]
            for cat in OpCategory
        }
        self._view.set_operations(
            categories, by_category, {OpCategory.BINARY.value}
        )

    def _connect(self) -> None:
        v = self._view
        v.page_activated.connect(self._on_page_activated)
        v.scene_add_requested.connect(self._on_scene_add)
        v.scene_close_requested.connect(self._on_scene_close)
        v.scene_changed.connect(self._on_scene_changed)
        v.scene_renamed.connect(self._on_scene_renamed)

        v.plot_activated.connect(self._on_plot_activated)
        v.roi_region_changed.connect(self._on_roi_region)
        v.cursor_dragged.connect(self._on_cursor_dragged)

        v.execution_check_changed.connect(self._on_execution_checked)
        v.grid_layout_changed.connect(self._on_grid_changed)
        v.maximize_toggled.connect(self._on_maximize)
        v.x_variable_changed.connect(lambda n: self._on_variable("x", n))
        v.y_variable_changed.connect(lambda n: self._on_variable("y", n))
        v.axis_autoscale_changed.connect(self._on_axis_autoscale)
        v.axis_log_changed.connect(self._on_axis_log)
        v.axis_min_committed.connect(
            lambda a, val: self._on_axis_bound(a, "min", val)
        )
        v.axis_max_committed.connect(
            lambda a, val: self._on_axis_bound(a, "max", val)
        )
        v.axis_multiplier_changed.connect(self._on_axis_multiplier)

        v.reset_view_requested.connect(self._on_reset_view)
        v.mouse_mode_changed.connect(self._on_mouse_mode)
        v.cursor_mode_changed.connect(self._on_cursor_mode)
        v.cursor_source_changed.connect(self._on_cursor_source)
        v.roi_enabled_changed.connect(self._on_roi_enabled)
        v.export_requested.connect(self._on_export)
        v.plot_title_committed.connect(self._on_plot_title)
        v.axis_label_committed.connect(self._on_axis_label)
        v.trace_visibility_changed.connect(
            lambda t, on: self._on_trace_style(t, "visible", on)
        )
        v.trace_color_changed.connect(
            lambda t, c: self._on_trace_style(t, "color", c)
        )
        v.trace_renamed.connect(self._on_trace_renamed)
        v.trace_line_style_changed.connect(
            lambda t, s: self._on_trace_style(t, "line_style", s)
        )
        v.trace_marker_changed.connect(
            lambda t, m: self._on_trace_style(t, "marker", m)
        )

        v.fit_requested.connect(self._on_fit_requested)
        v.fit_removed.connect(self._on_trace_removed)
        v.math_requested.connect(self._on_math_requested)
        v.computed_trace_removed.connect(self._on_trace_removed)

    # =========================================================================
    # Scene helpers
    # =========================================================================

    @staticmethod
    def _default_scene(number: int) -> SceneConfig:
        return SceneConfig(
            name=tr_ui(TXT.GRAPH_SCENE_DEFAULT).format(n=number)
        )

    @property
    def _scene(self) -> SceneConfig:
        return self._scenes[self._scene_index]

    @property
    def _plot(self) -> PlotConfig:
        return self._scene.active_plot

    def _axis(self, axis: str) -> AxisConfig:
        return self._plot.axis_x if axis == "x" else self._plot.axis_y

    # =========================================================================
    # Persistence
    # =========================================================================

    def _load_scenes(self) -> None:
        self._scenes = [self._default_scene(1)]
        self._scene_index = 0
        db = self._projects.current_db
        if db is None:
            return
        with db.session() as s:
            rows = GraphSceneRepository.list_rows(s)
        if not rows:
            return
        self._scenes = [SceneConfig.from_dict(row.scene_data) for row in rows]
        valid_ids = self._all_execution_ids()
        for scene in self._scenes:
            for plot in scene.plots:
                self._restore_plot(plot, valid_ids)

    def _restore_plot(self, plot: PlotConfig, valid_ids: set[int]) -> None:
        """Prune stale executions and recompute derived traces."""
        plot.selected_exec_ids = [
            i for i in plot.selected_exec_ids if i in valid_ids
        ]
        for exec_id in plot.selected_exec_ids:
            self._ensure_data(exec_id)

        restored: list[Trace] = []
        for trace in plot.traces:
            if self._materialize_trace(trace, restored, plot):
                restored.append(trace)
        plot.traces = restored

    def _materialize_trace(
        self, trace: Trace, done: list[Trace], plot: PlotConfig
    ) -> bool:
        """Fill a persisted trace's arrays; False → drop it."""
        if trace.kind is TraceKind.DATA:
            data = (
                self._data_cache.get(trace.source_exec_id)
                if trace.source_exec_id is not None
                else None
            )
            if data is None or not plot.x_var or not plot.y_var:
                return False
            trace.x = list(data.get(plot.x_var, []))
            trace.y = list(data.get(plot.y_var, []))
            return bool(trace.x)

        by_id = {t.id: t for t in done}
        definition = trace.definition or {}
        try:
            if trace.kind is TraceKind.COMPUTED:
                sources = [by_id[src] for src in definition.get("sources", [])]
                trace.x, trace.y = apply_operation(
                    definition.get("op_id", ""),
                    [(t.x, t.y) for t in sources],
                )
            else:  # FIT
                source = by_id[definition.get("source", "")]
                x_range = definition.get("x_range")
                outcome = run_fit(
                    definition.get("model_id", ""),
                    int(definition.get("degree", 1)),
                    source.x,
                    source.y,
                    tuple(x_range) if x_range else None,
                )
                trace.x, trace.y = outcome.x, outcome.y
        except (
            KeyError,
            NonFunctionalTraceError,
            TraceMathError,
            FitError,
        ):
            return False
        return True

    def _schedule_save(self) -> None:
        if self._projects.current_db is not None:
            self._save_timer.start()

    def _save_now(self) -> None:
        db = self._projects.current_db
        if db is None:
            return
        payload = [(scene.name, scene.to_dict()) for scene in self._scenes]
        with db.session() as s:
            GraphSceneRepository.replace_all(s, payload)

    # =========================================================================
    # Data access helpers
    # =========================================================================

    def _all_execution_ids(self) -> set[int]:
        db = self._projects.current_db
        if db is None:
            return set()
        ids: set[int] = set()
        with db.session() as s:
            for setup in SetupRepository.list_rows(s):
                for row in ExecutionRepository.list_rows(s, setup.id):
                    ids.add(row.id)
        return ids

    def _ensure_data(self, exec_id: int) -> Optional[dict]:
        """Load (once) and cache an execution's data + variable names."""
        if exec_id in self._data_cache:
            return self._data_cache[exec_id]
        db = self._projects.current_db
        if db is None:
            return None
        with db.session() as s:
            execution = ExecutionRepository.get(s, exec_id)
            if execution is None:
                return None
            data = execution_to_data_dict(execution)
        self._data_cache[exec_id] = data
        self._var_names[exec_id] = list(data.keys())
        return data

    def _variables_of(self, exec_id: int) -> list[str]:
        if exec_id not in self._var_names:
            db = self._projects.current_db
            if db is None:
                return []
            with db.session() as s:
                self._var_names[exec_id] = (
                    ExecutionRepository.list_variable_names(s, exec_id)
                )
        return self._var_names[exec_id]

    def _plot_signature(self, plot: PlotConfig) -> Optional[set[str]]:
        """Variable-name set the plot's executions must all share."""
        if not plot.selected_exec_ids:
            return None
        return set(self._variables_of(plot.selected_exec_ids[0]))

    # =========================================================================
    # View-signal handlers — scenes
    # =========================================================================

    def _on_page_activated(self) -> None:
        self._render_all()

    def _on_scene_add(self) -> None:
        self._scenes.append(self._default_scene(len(self._scenes) + 1))
        self._scene_index = len(self._scenes) - 1
        self._schedule_save()
        self._render_all()

    def _on_scene_close(self, index: int) -> None:
        if len(self._scenes) <= 1 or not (0 <= index < len(self._scenes)):
            return
        answer = QMessageBox.question(
            self._view,
            tr_ui(TXT.GRAPH_CLOSE_SCENE_TITLE),
            tr_ui(TXT.GRAPH_CLOSE_SCENE_MSG),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._scenes.pop(index)
        self._scene_index = min(self._scene_index, len(self._scenes) - 1)
        self._schedule_save()
        self._render_all()

    def _on_scene_changed(self, index: int) -> None:
        if 0 <= index < len(self._scenes) and index != self._scene_index:
            self._scene_index = index
            self._cursor_points.clear()
            self._render_body()

    def _on_scene_renamed(self, index: int, name: str) -> None:
        if 0 <= index < len(self._scenes):
            self._scenes[index].name = name
            self._schedule_save()
            self._render_scenes()

    # =========================================================================
    # View-signal handlers — layout / activation
    # =========================================================================

    def _on_plot_activated(self, slot: int) -> None:
        if slot != self._scene.active_index:
            self._scene.active_index = slot
            self._cursor_points.clear()
            self._schedule_save()
            self._render_body()

    def _on_grid_changed(self, rows: int, cols: int) -> None:
        scene = self._scene
        scene.rows, scene.cols = rows, cols
        if scene.active_index not in scene.visible_indices():
            scene.active_index = scene.visible_indices()[0]
        self._schedule_save()
        self._render_body()

    def _on_maximize(self, maximized: bool) -> None:
        self._scene.maximized = maximized
        self._schedule_save()
        self._render_plot_area()

    # =========================================================================
    # View-signal handlers — data / axes
    # =========================================================================

    def _on_execution_checked(self, exec_id: int, checked: bool) -> None:
        plot = self._plot
        if checked and exec_id not in plot.selected_exec_ids:
            if self._ensure_data(exec_id) is None:
                return
            plot.selected_exec_ids.append(exec_id)
            self._apply_default_variables(plot)
        elif not checked and exec_id in plot.selected_exec_ids:
            plot.selected_exec_ids.remove(exec_id)
        self._rebuild_data_traces(plot)
        self._schedule_save()
        self._render_body()

    def _apply_default_variables(self, plot: PlotConfig) -> None:
        """First execution defines default X/Y (first two variables)."""
        variables = self._variables_of(plot.selected_exec_ids[0])
        if not variables:
            return
        if plot.x_var not in variables:
            plot.x_var = variables[0]
        if plot.y_var not in variables:
            plot.y_var = variables[1] if len(variables) > 1 else variables[0]

    def _on_variable(self, axis: str, name: str) -> None:
        plot = self._plot
        if axis == "x":
            plot.x_var = name
        else:
            plot.y_var = name
        self._rebuild_data_traces(plot)
        self._schedule_save()
        self._render_body()

    def _on_axis_autoscale(self, axis: str, on: bool) -> None:
        cfg = self._axis(axis)
        cfg.auto_scale = on
        if not on and (cfg.min_val is None or cfg.max_val is None):
            self._seed_manual_range(axis, cfg)
        self._schedule_save()
        self._render_data_tab()
        self._render_plot_area()

    def _seed_manual_range(self, axis: str, cfg: AxisConfig) -> None:
        """Autoscale switched off with empty bounds → seed from data."""
        values: list[float] = []
        for trace in self._plot.traces:
            values.extend(trace.x if axis == "x" else trace.y)
        finite = [v for v in values if math.isfinite(v)]
        if cfg.log:
            finite = [v for v in finite if v > 0]
        if finite:
            cfg.min_val, cfg.max_val = min(finite), max(finite)
        else:
            cfg.min_val, cfg.max_val = 0.0, 1.0

    def _on_axis_log(self, axis: str, on: bool) -> None:
        cfg = self._axis(axis)
        cfg.log = on
        if on:
            # AxisItem.setScale conflicts with log ticks → force ×1.
            cfg.multiplier = Multiplier.NONE
        self._schedule_save()
        self._render_data_tab()
        self._render_plot_area()

    def _on_axis_bound(self, axis: str, bound: str, value: float) -> None:
        cfg = self._axis(axis)
        if bound == "min":
            cfg.min_val = value
        else:
            cfg.max_val = value
        self._schedule_save()
        self._render_plot_area()

    def _on_axis_multiplier(self, axis: str, label: str) -> None:
        cfg = self._axis(axis)
        try:
            cfg.multiplier = Multiplier(label)
        except ValueError:
            return
        self._schedule_save()
        self._render_plot_area()

    # =========================================================================
    # View-signal handlers — tools / traces
    # =========================================================================

    def _on_reset_view(self) -> None:
        self._view.reset_plot_view(self._scene.active_index)

    def _on_mouse_mode(self, mode: str) -> None:
        self._plot.mouse_mode = mode
        self._schedule_save()
        self._render_plot_area()

    def _on_cursor_mode(self, mode: str) -> None:
        plot = self._plot
        plot.cursor_mode = mode
        if plot.cursor_source_id is None and plot.traces:
            plot.cursor_source_id = plot.traces[0].id
        self._cursor_points.clear()
        self._schedule_save()
        self._render_plot_area()
        self._view.display_cursor_readout("")

    def _on_cursor_source(self, trace_id: str) -> None:
        self._plot.cursor_source_id = trace_id
        self._cursor_points.clear()
        self._schedule_save()
        self._view.display_cursor_readout("")

    def _on_roi_enabled(self, on: bool) -> None:
        plot = self._plot
        plot.roi_enabled = on
        if on and plot.roi is None:
            plot.roi = self._default_roi(plot)
        self._schedule_save()
        self._render_plot_area()

    @staticmethod
    def _default_roi(plot: PlotConfig) -> tuple[float, float]:
        """Middle half of the first trace's finite x span."""
        for trace in plot.traces:
            finite = [v for v in trace.x if math.isfinite(v)]
            if finite:
                lo, hi = min(finite), max(finite)
                span = hi - lo
                return lo + 0.25 * span, hi - 0.25 * span
        return 0.0, 1.0

    def _on_roi_region(self, lo: float, hi: float) -> None:
        # No re-render — the item is already where the user dragged it.
        self._plot.roi = (lo, hi)
        self._schedule_save()

    def _on_plot_title(self, title: str) -> None:
        self._plot.title = title
        self._schedule_save()
        self._render_plot_area()

    def _on_axis_label(self, axis: str, text: str) -> None:
        self._axis(axis).label = text
        self._schedule_save()
        self._render_plot_area()

    def _on_trace_style(self, trace_id: str, prop: str, value) -> None:
        trace = self._plot.trace_by_id(trace_id)
        if trace is None:
            return
        setattr(trace.style, prop, value)
        self._schedule_save()
        self._render_plot_area()
        if prop == "color":
            self._render_view_tab()

    def _on_trace_renamed(self, trace_id: str, name: str) -> None:
        trace = self._plot.trace_by_id(trace_id)
        if trace is None or not name.strip():
            return
        trace.name = name.strip()
        self._schedule_save()
        self._render_plot_area()
        self._render_view_tab()
        self._render_analysis_tab()

    def _on_trace_removed(self, trace_id: str) -> None:
        plot = self._plot
        plot.traces = [t for t in plot.traces if t.id != trace_id]
        if plot.cursor_source_id == trace_id:
            plot.cursor_source_id = None
        self._schedule_save()
        self._render_body()

    # =========================================================================
    # View-signal handlers — analysis
    # =========================================================================

    def _on_fit_requested(
        self, trace_id: str, model_id: str, degree: int, over_roi: bool
    ) -> None:
        plot = self._plot
        source = plot.trace_by_id(trace_id)
        if source is None:
            return
        x_range = None
        if over_roi:
            if not plot.roi_enabled or plot.roi is None:
                self._view.display_analysis_message(
                    tr_ui(TXT.GRAPH_FIT_NEED_ROI)
                )
                return
            x_range = plot.roi
        try:
            outcome = run_fit(model_id, degree, source.x, source.y, x_range)
        except NonFunctionalTraceError:
            self._view.display_analysis_message(
                tr_ui(TXT.GRAPH_NON_FUNCTIONAL_MSG)
            )
            return
        except FitError as exc:
            self._view.display_analysis_message(str(exc))
            return

        trace = Trace(
            id=f"fit:{plot.next_fit_id}",
            name=f"fit{plot.next_fit_id} [{source.name}]",
            kind=TraceKind.FIT,
            x=outcome.x,
            y=outcome.y,
            style=TraceStyle(color=self._next_color(plot), line_style="dash"),
            definition={
                "model_id": model_id,
                "degree": outcome.degree,
                "source": source.id,
                "x_range": list(x_range) if x_range else None,
                "equation": outcome.equation_text,
                "r_squared": outcome.r_squared,
            },
        )
        plot.next_fit_id += 1
        plot.traces.append(trace)
        self._view.display_analysis_message("")
        self._schedule_save()
        self._render_body()

    def _on_math_requested(self, op_id: str, src_a: str, src_b: str) -> None:
        plot = self._plot
        spec = OPERATIONS.get(op_id)
        source_a = plot.trace_by_id(src_a)
        source_b = plot.trace_by_id(src_b) if src_b else None
        if spec is None or source_a is None:
            return
        sources = [source_a] + ([source_b] if source_b else [])
        if len(sources) != spec.arity:
            return
        try:
            x, y = apply_operation(op_id, [(t.x, t.y) for t in sources])
        except NonFunctionalTraceError:
            self._view.display_analysis_message(
                tr_ui(TXT.GRAPH_NON_FUNCTIONAL_MSG)
            )
            return
        except TraceMathError as exc:
            self._view.display_analysis_message(str(exc))
            return

        name = spec.name_template.format(
            a=source_a.name, b=source_b.name if source_b else ""
        )
        trace = Trace(
            id=f"calc:{plot.next_calc_id}",
            name=name,
            kind=TraceKind.COMPUTED,
            x=x,
            y=y,
            style=TraceStyle(color=self._next_color(plot)),
            definition={
                "op_id": op_id,
                "sources": [t.id for t in sources],
            },
        )
        plot.next_calc_id += 1
        plot.traces.append(trace)
        self._view.display_analysis_message("")
        self._schedule_save()
        self._render_body()

    # =========================================================================
    # View-signal handlers — cursors / export
    # =========================================================================

    def _on_cursor_dragged(self, cursor_index: int, x: float) -> None:
        plot = self._plot
        source = (
            plot.trace_by_id(plot.cursor_source_id)
            if plot.cursor_source_id
            else None
        )
        if source is None and plot.traces:
            source = plot.traces[0]
        if source is None:
            return
        try:
            _idx, sx, sy = nearest_point(source.x, source.y, x)
        except ValueError:
            return
        self._cursor_points[cursor_index] = (sx, sy)
        text = tr_ui(TXT.GRAPH_CURSOR_READOUT).format(x=_fmt(sx), y=_fmt(sy))
        self._view.display_cursor(cursor_index, sx, sy, text)
        self._view.display_cursor_readout(self._readout_text())

    def _readout_text(self) -> str:
        parts = [
            f"c{idx + 1}: "
            + tr_ui(TXT.GRAPH_CURSOR_READOUT).format(x=_fmt(x), y=_fmt(y))
            for idx, (x, y) in sorted(self._cursor_points.items())
        ]
        both = (
            self._cursor_points.get(0),
            self._cursor_points.get(1),
        )
        if all(p is not None for p in both):
            (x0, y0), (x1, y1) = both
            dx, dy = x1 - x0, y1 - y0
            slope = dy / dx if dx else float("nan")
            parts.append(
                tr_ui(TXT.GRAPH_CURSOR_DELTA).format(
                    dx=_fmt(dx), dy=_fmt(dy), slope=_fmt(slope)
                )
            )
        return "\n".join(parts)

    def _on_export(self, kind: str) -> None:
        plot = self._plot
        traces = [t for t in plot.traces if t.x]
        if not traces:
            self._view.display_analysis_message(
                tr_ui(TXT.GRAPH_EXPORT_NO_PLOT)
            )
            return
        if kind == "png":
            self._export_png()
        else:
            self._export_csv(traces)

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self._view,
            tr_ui(TXT.GRAPH_EXPORT_PNG_TITLE),
            "plot.png",
            "PNG (*.png)",
        )
        if path:
            self._view.export_plot_png(self._scene.active_index, path)

    def _export_csv(self, traces: list[Trace]) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self._view,
            tr_ui(TXT.GRAPH_EXPORT_CSV_TITLE),
            "plot.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(to_csv(traces_to_dataset(traces)))
        except OSError as exc:
            self._view.display_analysis_message(
                tr_ui(TXT.GRAPH_EXPORT_ERROR).format(error=exc)
            )

    # =========================================================================
    # Trace lifecycle
    # =========================================================================

    def _rebuild_data_traces(self, plot: PlotConfig) -> None:
        """Re-derive DATA traces from selection + x/y vars (styles kept)."""
        previous = {t.id: t for t in plot.traces if t.kind is TraceKind.DATA}
        derived = [t for t in plot.traces if t.kind is not TraceKind.DATA]
        data_traces: list[Trace] = []
        for exec_id in plot.selected_exec_ids:
            data = self._data_cache.get(exec_id)
            if data is None or not plot.x_var or not plot.y_var:
                continue
            trace_id = f"exec:{exec_id}"
            old = previous.get(trace_id)
            trace = Trace(
                id=trace_id,
                name=(
                    old.name
                    if old is not None
                    else self._default_trace_name(plot, exec_id)
                ),
                kind=TraceKind.DATA,
                x=list(data.get(plot.x_var, [])),
                y=list(data.get(plot.y_var, [])),
                style=old.style if old is not None else TraceStyle(),
                source_exec_id=exec_id,
            )
            if old is None:
                trace.style.color = self._next_color(
                    plot, extra=len(data_traces)
                )
            data_traces.append(trace)
        plot.traces = data_traces + derived

    def _default_trace_name(self, plot: PlotConfig, exec_id: int) -> str:
        label = self._exec_labels.get(exec_id, f"#{exec_id}")
        return f"{plot.y_var} · {label}"

    def _next_color(self, plot: PlotConfig, extra: int = 0) -> str:
        colors = P.GRAPH_TRACE_COLORS
        return colors[(len(plot.traces) + extra) % len(colors)]

    # =========================================================================
    # Rendering (model → display_*)
    #
    # CRITICAL — all rendering is DEFERRED to the next event-loop turn.
    # Handlers run inside the emitting widget's own Qt signal (a tree
    # item's ``itemChanged``, a combo's ``currentTextChanged``, a
    # pyqtgraph ``sigMouseClicked``…).  Painting synchronously would
    # rebuild those very widgets (``tree.clear()``, ``combo.clear()``,
    # ``GraphicsLayoutWidget.clear()``), destroying the C++ object whose
    # signal is still on the stack — a native crash with no traceback.
    # ``_request_render`` coalesces parts and flushes them once the
    # signal stack has unwound.
    # =========================================================================

    _RENDER_ORDER = ("scenes", "data", "view", "analysis", "plots")

    def _request_render(self, *parts: str) -> None:
        if not self._pending_renders:
            # ``self`` as context: the pending flush dies with the
            # presenter instead of firing into destroyed widgets.
            QTimer.singleShot(0, self, self._flush_renders)
        self._pending_renders.update(parts)

    def _flush_renders(self) -> None:
        parts, self._pending_renders = self._pending_renders, set()
        paints = {
            "scenes": self._paint_scenes,
            "data": self._paint_data_tab,
            "view": self._paint_view_tab,
            "analysis": self._paint_analysis_tab,
            "plots": self._paint_plot_area,
        }
        for part in self._RENDER_ORDER:
            if part in parts:
                paints[part]()

    def _render_all(self) -> None:
        self._request_render(*self._RENDER_ORDER)

    def _render_body(self) -> None:
        self._request_render("data", "view", "analysis", "plots")

    def _render_scenes(self) -> None:
        self._request_render("scenes")

    def _render_data_tab(self) -> None:
        self._request_render("data")

    def _render_view_tab(self) -> None:
        self._request_render("view")

    def _render_analysis_tab(self) -> None:
        self._request_render("analysis")

    def _render_plot_area(self) -> None:
        self._request_render("plots")

    def _paint_scenes(self) -> None:
        self._view.display_scenes(
            [scene.name for scene in self._scenes], self._scene_index
        )

    # ── Data tab ─────────────────────────────────────────────────────────────

    def _paint_data_tab(self) -> None:
        plot = self._plot
        self._view.display_datasets(self._dataset_groups(plot))
        signature = self._plot_signature(plot)
        self._view.display_variables(
            sorted(signature) if signature else [],
            plot.x_var,
            plot.y_var,
        )
        for axis in ("x", "y"):
            cfg = self._axis(axis)
            self._view.display_axis(
                axis,
                {
                    "variable": plot.x_var if axis == "x" else plot.y_var,
                    "auto_scale": cfg.auto_scale,
                    "log": cfg.log,
                    "min_val": cfg.min_val,
                    "max_val": cfg.max_val,
                    "multiplier": cfg.multiplier.value,
                },
            )
        scene = self._scene
        self._view.display_grid(scene.rows, scene.cols, scene.maximized)

    def _dataset_groups(self, plot: PlotConfig) -> list:
        db = self._projects.current_db
        if db is None:
            return []
        signature = self._plot_signature(plot)
        groups = []
        with db.session() as s:
            for setup in SetupRepository.list_rows(s):
                executions = []
                for row in ExecutionRepository.list_rows(s, setup.id):
                    self._exec_labels[row.id] = row.name
                    checked = row.id in plot.selected_exec_ids
                    enabled = checked or signature is None
                    if not enabled:
                        enabled = variables_compatible(
                            signature, self._variables_of(row.id)
                        )
                    executions.append((row.id, row.name, checked, enabled))
                if executions:
                    groups.append(
                        (
                            f"{setup.name} · {setup.type_label}",
                            executions,
                        )
                    )
        return groups

    # ── View tab ─────────────────────────────────────────────────────────────

    def _paint_view_tab(self) -> None:
        plot = self._plot
        self._view.display_tools(
            plot.mouse_mode,
            plot.cursor_mode,
            plot.cursor_source_id,
            plot.roi_enabled,
        )
        self._view.display_labels(
            plot.title, plot.axis_x.label, plot.axis_y.label
        )
        options = [(t.id, t.name) for t in plot.traces]
        self._view.display_cursor_trace_options(options, plot.cursor_source_id)
        self._view.display_traces(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "color": t.style.color,
                    "visible": t.style.visible,
                    "line_style": t.style.line_style,
                    "marker": t.style.marker,
                }
                for t in plot.traces
            ]
        )

    # ── Analysis tab ─────────────────────────────────────────────────────────

    def _paint_analysis_tab(self) -> None:
        plot = self._plot
        options = [(t.id, t.name) for t in plot.traces]
        self._view.display_analysis_trace_options(options)
        self._view.display_fits(
            [
                (t.id, self._fit_entry_text(t))
                for t in plot.traces
                if t.kind is TraceKind.FIT
            ]
        )
        self._view.display_computed(
            [
                (t.id, t.name)
                for t in plot.traces
                if t.kind is TraceKind.COMPUTED
            ]
        )
        has_traces = bool(plot.traces)
        self._view.set_analysis_enabled(has_traces)
        if not has_traces:
            self._view.display_analysis_message(
                tr_ui(TXT.GRAPH_ANALYSIS_EMPTY)
            )
        else:
            self._view.display_analysis_message("")

    @staticmethod
    def _fit_entry_text(trace: Trace) -> str:
        definition = trace.definition or {}
        equation = definition.get("equation", "")
        r_squared = definition.get("r_squared")
        suffix = f"  (R²={r_squared:.5g})" if r_squared is not None else ""
        return f"{trace.name}: {equation}{suffix}"

    # ── Plot area ────────────────────────────────────────────────────────────

    def _paint_plot_area(self) -> None:
        scene = self._scene
        specs = [
            self._plot_spec(slot, scene.plots[slot], scene)
            for slot in scene.visible_indices()
        ]
        self._view.display_scene(
            specs,
            scene.rows,
            scene.cols,
            scene.active_index,
            scene.maximized,
        )

    def _plot_spec(
        self, slot: int, plot: PlotConfig, scene: SceneConfig
    ) -> PlotRenderSpec:
        active = slot == scene.active_index
        return PlotRenderSpec(
            index=slot,
            title=plot.title,
            x_label=self._axis_label_text(plot.x_var, plot.axis_x),
            y_label=self._axis_label_text(plot.y_var, plot.axis_y),
            x_log=plot.axis_x.log,
            y_log=plot.axis_y.log,
            x_scale=self._axis_scale_value(plot.axis_x),
            y_scale=self._axis_scale_value(plot.axis_y),
            x_range=self._axis_range(plot.axis_x),
            y_range=self._axis_range(plot.axis_y),
            mouse_mode=plot.mouse_mode,
            active=active,
            traces=[
                TraceRenderSpec(
                    trace_id=t.id,
                    name=t.name,
                    x=t.x,
                    y=t.y,
                    color=t.style.color,
                    visible=t.style.visible,
                    line_style=t.style.line_style,
                    marker=t.style.marker,
                    width=t.style.width,
                    marker_size=t.style.marker_size,
                    opacity=t.style.opacity,
                )
                for t in plot.traces
            ],
            roi=(plot.roi if active and plot.roi_enabled else None),
            cursors=self._cursor_positions(plot) if active else [],
        )

    @staticmethod
    def _axis_label_text(var: str | None, cfg: AxisConfig) -> str:
        if cfg.label:
            return cfg.label
        if not var:
            return ""
        return axis_label(var, cfg.multiplier)

    @staticmethod
    def _axis_scale_value(cfg: AxisConfig) -> float:
        # Log ticks are already decades — never rescale them.
        if cfg.log:
            return 1.0
        return axis_scale(cfg.multiplier)

    @staticmethod
    def _axis_range(cfg: AxisConfig) -> tuple[float, float] | None:
        if cfg.auto_scale or cfg.min_val is None or cfg.max_val is None:
            return None
        return (cfg.min_val, cfg.max_val)

    def _cursor_positions(self, plot: PlotConfig) -> list[float]:
        count = {"off": 0, "single": 1, "dual": 2}.get(plot.cursor_mode, 0)
        if count == 0:
            return []
        lo, hi = self._default_roi(plot)  # finite x span anchors
        span = hi - lo
        defaults = [lo + span * 0.5, lo + span * 0.9]
        return [
            self._cursor_points.get(i, (defaults[i], 0.0))[0]
            for i in range(count)
        ]
