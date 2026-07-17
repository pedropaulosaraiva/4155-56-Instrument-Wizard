"""
models/graph/config.py
----------------------
Persistable state of the Graphs page: scenes → plots → axes/traces.

Every dataclass here serializes to plain JSON via ``to_dict``/
``from_dict`` — one scene becomes one ``graph_scene`` row (mirroring how
``measurement_setup.setup_data`` stores the config dict verbatim).
Derived traces persist only their *definitions* and are recomputed on
load; point arrays are never stored.

Engineering multipliers
-----------------------
pyqtgraph's automatic SI prefixing is banned (it silently rescales the
displayed values).  The multiplier is always explicit: ``axis_scale``
returns the factor handed to ``AxisItem.setScale`` so only the *tick
text* changes — the underlying data is never touched.

No PySide6 / pyqtgraph imports.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from wizard_4155_4156.models.graph.trace import Trace

#: JSON schema version stored with every persisted scene.
SCENE_SCHEMA_VERSION = 1

#: The plot grid is conceptually always 3×3; ``rows``/``cols`` select the
#: visible sub-grid so per-cell configs survive grid resizes.
GRID_MAX = 3
PLOT_SLOTS = GRID_MAX * GRID_MAX

#: Fraction of the data span added on each side by the auto range.
_RANGE_PADDING = 0.05


# =============================================================================
# Engineering multipliers
# =============================================================================


class Multiplier(StrEnum):
    """User-selectable engineering multiplier (value = UI label)."""

    PICO = "p"
    NANO = "n"
    MICRO = "µ"
    MILLI = "m"
    NONE = "1"
    KILO = "k"
    MEGA = "M"
    GIGA = "G"


#: Display order for the multiplier selector.
MULTIPLIERS: tuple[Multiplier, ...] = (
    Multiplier.PICO,
    Multiplier.NANO,
    Multiplier.MICRO,
    Multiplier.MILLI,
    Multiplier.NONE,
    Multiplier.KILO,
    Multiplier.MEGA,
    Multiplier.GIGA,
)

MULTIPLIER_FACTORS: dict[Multiplier, float] = {
    Multiplier.PICO: 1e-12,
    Multiplier.NANO: 1e-9,
    Multiplier.MICRO: 1e-6,
    Multiplier.MILLI: 1e-3,
    Multiplier.NONE: 1.0,
    Multiplier.KILO: 1e3,
    Multiplier.MEGA: 1e6,
    Multiplier.GIGA: 1e9,
}


def axis_scale(multiplier: Multiplier) -> float:
    """The value for ``AxisItem.setScale`` — tick text = value × scale."""
    return 1.0 / MULTIPLIER_FACTORS[multiplier]


def infer_unit(var_name: str) -> str:
    """Physical unit from the variable-name convention.

    ``V*``/``VMU*``/``VSU*`` → volts, ``I*`` → amperes, ``@TIME`` →
    seconds, ``@INDEX`` → dimensionless.
    """
    if var_name == "@TIME":
        return "s"
    if var_name.startswith("V"):
        return "V"
    if var_name.startswith("I"):
        return "A"
    return ""


def axis_label(var_name: str, multiplier: Multiplier) -> str:
    """Axis label with the multiplier baked in, e.g. ``I1 (mA)``."""
    unit = infer_unit(var_name)
    prefix = "" if multiplier is Multiplier.NONE else multiplier.value
    if not unit and not prefix:
        return var_name
    if not unit:
        return f"{var_name} (×{prefix})"
    return f"{var_name} ({prefix}{unit})"


# =============================================================================
# Dataset compatibility & ranges
# =============================================================================


def variables_compatible(a: Iterable[str], b: Iterable[str]) -> bool:
    """Executions may share a plot iff their variable-name sets match."""
    return set(a) == set(b)


def compute_axis_range(
    values: Sequence[float], log: bool
) -> tuple[float, float]:
    """Padded display range for *values* (log-safe when *log* is set)."""
    finite = [
        v for v in values if isinstance(v, (int, float)) and math.isfinite(v)
    ]
    if log:
        finite = [v for v in finite if v > 0.0]
    if not finite:
        return (0.1, 1.0) if log else (0.0, 1.0)

    lo, hi = min(finite), max(finite)
    if log:
        log_lo, log_hi = math.log10(lo), math.log10(hi)
        pad = (log_hi - log_lo) * _RANGE_PADDING or 0.5
        return 10 ** (log_lo - pad), 10 ** (log_hi + pad)

    pad = (hi - lo) * _RANGE_PADDING
    if pad == 0.0:
        pad = abs(hi) * _RANGE_PADDING or 0.5
    return lo - pad, hi + pad


# =============================================================================
# Axis / plot / scene state
# =============================================================================


@dataclass
class AxisConfig:
    """Per-axis display configuration of one plot."""

    label: str = ""  # custom label; empty → derived from the variable
    auto_scale: bool = True
    log: bool = False
    min_val: float | None = None
    max_val: float | None = None
    multiplier: Multiplier = Multiplier.NONE

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "auto_scale": self.auto_scale,
            "log": self.log,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "multiplier": self.multiplier.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AxisConfig":
        default = cls()
        return cls(
            label=data.get("label", default.label),
            auto_scale=bool(data.get("auto_scale", default.auto_scale)),
            log=bool(data.get("log", default.log)),
            min_val=data.get("min_val"),
            max_val=data.get("max_val"),
            multiplier=Multiplier(
                data.get("multiplier", default.multiplier.value)
            ),
        )


@dataclass
class PlotConfig:
    """One grid cell: datasets, axes, traces and interaction state."""

    title: str = ""
    x_var: str | None = None
    y_var: str | None = None
    axis_x: AxisConfig = field(default_factory=AxisConfig)
    axis_y: AxisConfig = field(default_factory=AxisConfig)
    selected_exec_ids: list[int] = field(default_factory=list)
    traces: list[Trace] = field(default_factory=list)
    mouse_mode: str = "pan"  # "pan" | "zoom"
    cursor_mode: str = "off"  # "off" | "single" | "dual"
    cursor_source_id: str | None = None
    roi_enabled: bool = False
    roi: tuple[float, float] | None = None
    next_calc_id: int = 1
    next_fit_id: int = 1
    # Font sizes in points; defaults match pyqtgraph's built-in rendering.
    font_title: int = 11
    font_axis_x: int = 10
    font_axis_y: int = 10
    font_ticks: int = 9
    font_legend: int = 9

    def trace_by_id(self, trace_id: str) -> Trace | None:
        for trace in self.traces:
            if trace.id == trace_id:
                return trace
        return None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "x_var": self.x_var,
            "y_var": self.y_var,
            "axis_x": self.axis_x.to_dict(),
            "axis_y": self.axis_y.to_dict(),
            "selected_exec_ids": list(self.selected_exec_ids),
            "traces": [t.to_dict() for t in self.traces],
            "mouse_mode": self.mouse_mode,
            "cursor_mode": self.cursor_mode,
            "cursor_source_id": self.cursor_source_id,
            "roi_enabled": self.roi_enabled,
            "roi": list(self.roi) if self.roi else None,
            "next_calc_id": self.next_calc_id,
            "next_fit_id": self.next_fit_id,
            "font_title": self.font_title,
            "font_axis_x": self.font_axis_x,
            "font_axis_y": self.font_axis_y,
            "font_ticks": self.font_ticks,
            "font_legend": self.font_legend,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlotConfig":
        default = cls()
        roi = data.get("roi")
        return cls(
            title=data.get("title", ""),
            x_var=data.get("x_var"),
            y_var=data.get("y_var"),
            axis_x=AxisConfig.from_dict(data.get("axis_x", {})),
            axis_y=AxisConfig.from_dict(data.get("axis_y", {})),
            selected_exec_ids=[
                int(i) for i in data.get("selected_exec_ids", [])
            ],
            traces=[Trace.from_dict(t) for t in data.get("traces", [])],
            mouse_mode=data.get("mouse_mode", default.mouse_mode),
            cursor_mode=data.get("cursor_mode", default.cursor_mode),
            cursor_source_id=data.get("cursor_source_id"),
            roi_enabled=bool(data.get("roi_enabled", False)),
            roi=(float(roi[0]), float(roi[1])) if roi else None,
            next_calc_id=int(data.get("next_calc_id", 1)),
            next_fit_id=int(data.get("next_fit_id", 1)),
            font_title=int(data.get("font_title", default.font_title)),
            font_axis_x=int(data.get("font_axis_x", default.font_axis_x)),
            font_axis_y=int(data.get("font_axis_y", default.font_axis_y)),
            font_ticks=int(data.get("font_ticks", default.font_ticks)),
            font_legend=int(data.get("font_legend", default.font_legend)),
        )


@dataclass
class SceneConfig:
    """One scene tab: a visible sub-grid over 9 persistent plot slots."""

    name: str = "Scene 1"
    rows: int = 1
    cols: int = 1
    plots: list[PlotConfig] = field(
        default_factory=lambda: [PlotConfig() for _ in range(PLOT_SLOTS)]
    )
    active_index: int = 0
    maximized: bool = False

    def visible_indices(self) -> list[int]:
        """Slot indices shown by the current grid (row-major)."""
        return [
            row * GRID_MAX + col
            for row in range(self.rows)
            for col in range(self.cols)
        ]

    @property
    def active_plot(self) -> PlotConfig:
        return self.plots[self.active_index]

    def to_dict(self) -> dict:
        return {
            "version": SCENE_SCHEMA_VERSION,
            "name": self.name,
            "rows": self.rows,
            "cols": self.cols,
            "plots": [p.to_dict() for p in self.plots],
            "active_index": self.active_index,
            "maximized": self.maximized,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SceneConfig":
        plots = [PlotConfig.from_dict(p) for p in data.get("plots", [])]
        while len(plots) < PLOT_SLOTS:
            plots.append(PlotConfig())
        rows = min(max(int(data.get("rows", 1)), 1), GRID_MAX)
        cols = min(max(int(data.get("cols", 1)), 1), GRID_MAX)
        active = int(data.get("active_index", 0))
        if active < 0 or active >= PLOT_SLOTS:
            active = 0
        return cls(
            name=str(data.get("name", "Scene 1")),
            rows=rows,
            cols=cols,
            plots=plots[:PLOT_SLOTS],
            active_index=active,
            maximized=bool(data.get("maximized", False)),
        )
