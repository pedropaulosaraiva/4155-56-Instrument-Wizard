"""
db/assembler.py
---------------
Bridge between the runtime data and the ORM.

Setup side (trivial): a measurement setup's canonical config dict is stored
verbatim in the ``setup_data`` JSON column, so there is nothing to translate —
``config_dict_to_setup`` just constructs the row and ``setup_to_config_dict``
just returns the stored dict.

Execution side (normalized): the ``{var_name: array}`` fetch result is decomposed
into ``ExecutionVariable`` → ``DataPoint`` rows (non-finite readings stored as
NULL, since SQLite can't store NaN/inf), and rebuilt on read.

No PySide6 imports.
"""
from __future__ import annotations

import copy
import math
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from wizard_4155_4156.db.schema import (
    DataPoint,
    ExecutionVariable,
    MeasurementExecution,
    MeasurementSetup,
)


# =============================================================================
# Setup  <->  config dict  (JSON column — no translation)
# =============================================================================


def config_dict_to_setup(
    config: Mapping[str, Any],
    *,
    name: str,
    instrument_model: str,
    description: Optional[str] = None,
    author: Optional[str] = None,
    organization: Optional[str] = None,
    interlock_open: bool = True,
    common_to_ground: bool = True,
) -> MeasurementSetup:
    """Build an (un-persisted) setup row storing the config dict as JSON."""
    return MeasurementSetup(
        name=name,
        description=description,
        author=author,
        organization=organization,
        instrument_model=instrument_model,
        setup_type=config.get("mode", "SWEEP"),
        interlock_open=interlock_open,
        common_to_ground=common_to_ground,
        setup_data=copy.deepcopy(dict(config)),
    )


def setup_to_config_dict(setup: MeasurementSetup) -> dict:
    """Return the stored config dict (deep-copied so callers can't mutate it)."""
    return copy.deepcopy(setup.setup_data or {})


# =============================================================================
# Execution data (normalized)
# =============================================================================


def fetch_result_to_execution(
    results: Mapping[str, Iterable[Any]],
    *,
    setup: MeasurementSetup,
    name: str,
    instrument_model: str,
    description: Optional[str] = None,
    is_synthetic: bool = False,
) -> MeasurementExecution:
    """
    Convert a ``{var_name: array}`` fetch result (as emitted by
    ``DataFetchTask``) into a normalized execution graph, link it to ``setup``,
    and stamp the setup's ``last_execution_date``.
    """
    execution = MeasurementExecution(
        name=name,
        description=description,
        instrument_model=instrument_model,
        is_synthetic=is_synthetic,
    )
    for position, (var_name, values) in enumerate(results.items()):
        variable = ExecutionVariable(var_name=var_name, position=position)
        variable.data_points = [
            DataPoint(point_index=i, value=_finite_or_none(value))
            for i, value in enumerate(values)
        ]
        execution.variables.append(variable)

    execution.setup = setup
    setup.last_execution_date = datetime.now()
    return execution


def execution_to_data_dict(
    execution: MeasurementExecution,
) -> dict[str, list[float]]:
    """
    Reconstruct a ``{var_name: [values]}`` dict for table/graph display.

    NULL points (non-finite readings stored as NULL) come back as ``nan`` so
    every value is a float and downstream numeric formatting keeps working.
    """
    out: dict[str, list[float]] = {}
    for var in sorted(execution.variables, key=lambda v: v.position):
        out[var.var_name] = [
            dp.value if dp.value is not None else float("nan")
            for dp in sorted(var.data_points, key=lambda d: d.point_index)
        ]
    return out


def _finite_or_none(value: Any) -> Optional[float]:
    """Coerce to float; non-finite (NaN/inf) becomes NULL (SQLite-safe)."""
    v = float(value)
    return v if math.isfinite(v) else None
