"""
models/graph
------------
Pure-Python (Qt-free, pyqtgraph-free) domain layer of the Graphs page.

Modules
-------
config      — persistable state dataclasses (scene / plot / axis / style)
              plus multiplier and unit helpers.
trace       — the Trace dataclass shared by measured, computed and fitted
              curves.
functional  — turning raw point clouds into mathematical functions
              (duplicate-X averaging, non-functional detection, cursor
              snapping).
trace_math  — registry of derivative / unary / binary trace operations.
fitting     — registry of curve-fit models (linear, polynomial).

Everything here is unit-tested under ``test/models/graph``.
"""
