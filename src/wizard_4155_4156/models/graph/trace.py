"""
models/graph/trace.py
---------------------
The Trace dataclass — one displayed curve in a plot cell.

Measured (DATA), computed (COMPUTED) and fitted (FIT) curves are all the
same type so every feature (styling, cursors, further math, fitting)
treats them uniformly.

Identity & persistence
----------------------
Trace ids are stable strings — ``"exec:<execution_id>"`` for measured
data, ``"calc:<n>"`` / ``"fit:<n>"`` for derived traces (counters live in
``PlotConfig``) — so persisted computed/fit *definitions* keep valid
references across sessions.  ``to_dict`` never serializes the point
arrays: DATA traces are rebuilt from the project database and derived
traces are recomputed from their ``definition`` on load.

No PySide6 / pyqtgraph imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: Logical line styles (the view maps them to Qt pen styles).
LINE_STYLES: tuple[str, ...] = ("solid", "dash", "dot", "none")

#: Logical marker shapes (the view maps them to pyqtgraph symbols).
MARKERS: tuple[str, ...] = ("none", "circle", "square", "triangle", "cross")


class TraceKind(StrEnum):
    """What produced a trace (never changes how it behaves)."""

    DATA = "data"
    COMPUTED = "computed"
    FIT = "fit"


@dataclass
class TraceStyle:
    """Per-trace visual configuration.

    ``width`` / ``marker_size`` / ``opacity`` already exist with defaults
    so future style controls need no model or persistence change.
    """

    color: str = "#ffffff"
    visible: bool = True
    line_style: str = "solid"
    marker: str = "none"
    width: float = 1.5
    marker_size: float = 6.0
    opacity: float = 1.0

    def to_dict(self) -> dict:
        return {
            "color": self.color,
            "visible": self.visible,
            "line_style": self.line_style,
            "marker": self.marker,
            "width": self.width,
            "marker_size": self.marker_size,
            "opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TraceStyle":
        default = cls()
        return cls(
            color=data.get("color", default.color),
            visible=bool(data.get("visible", default.visible)),
            line_style=data.get("line_style", default.line_style),
            marker=data.get("marker", default.marker),
            width=float(data.get("width", default.width)),
            marker_size=float(data.get("marker_size", default.marker_size)),
            opacity=float(data.get("opacity", default.opacity)),
        )


@dataclass
class Trace:
    """One curve: identity, data arrays, style and (optional) recipe.

    ``definition`` is the JSON-safe recipe of a COMPUTED/FIT trace
    (operation id + source trace ids, or fit model + degree + ROI range);
    it is what gets persisted so the arrays can be recomputed on load.
    """

    id: str
    name: str
    kind: TraceKind = TraceKind.DATA
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    style: TraceStyle = field(default_factory=TraceStyle)
    source_exec_id: int | None = None
    definition: dict | None = None

    def to_dict(self) -> dict:
        """Persistable form — point arrays are deliberately omitted."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "style": self.style.to_dict(),
            "source_exec_id": self.source_exec_id,
            "definition": self.definition,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Trace":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            kind=TraceKind(data.get("kind", TraceKind.DATA.value)),
            style=TraceStyle.from_dict(data.get("style", {})),
            source_exec_id=data.get("source_exec_id"),
            definition=data.get("definition"),
        )


def traces_to_dataset(traces: list[Trace]) -> dict[str, list[float]]:
    """
    Flatten traces into the app's canonical ``{column: [values]}`` shape
    (two columns per trace) so ``models/data_export`` can serialize them.

    Column names are disambiguated when trace display names collide.
    """
    dataset: dict[str, list[float]] = {}
    for trace in traces:
        base = trace.name
        suffix = 2
        while f"{base} [x]" in dataset:
            base = f"{trace.name} ({suffix})"
            suffix += 1
        dataset[f"{base} [x]"] = [float(v) for v in trace.x]
        dataset[f"{base} [y]"] = [float(v) for v in trace.y]
    return dataset
