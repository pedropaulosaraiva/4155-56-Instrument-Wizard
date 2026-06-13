"""
db/assembler.py
---------------
Bridge between the canonical measurement-config dict (produced by the
sweep/sampling presenters' ``get_json()``) and the normalized ORM graph.

The dict shape is defined 1:1 by
``presenters/sweep_config_presenter.py::_build_json`` and
``presenters/sampling_config_presenter.py::_build_json``.  The round-trip
invariant ``setup_to_config_dict(config_dict_to_setup(cfg, ...)) == cfg`` holds
for any valid sweep or sampling config dict, and is guarded by
``test/db/smoke_test_persistence.py``.

Fidelity rules (NULL column <=> omitted JSON key):
  * range ``value`` omitted for ``AUTO``;
  * sweep VAR ``compliance``/``pcompliance`` omitted when VSU-driven / off;
  * sampling period tri-state (AUTO / NO_LIMIT / NUMERIC) plus ``"NA"`` for log
    modes that carry no period key;
  * ``scon`` row present == enabled (``state == "ON"``);
  * disabled channels serialize as ``{"disable": 1}``.

``instrument_model``, ``interlock_open`` and ``common_to_ground`` are NOT part
of the config dict — they are supplied separately and are not round-tripped.

No PySide6 imports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from wizard_4155_4156.db.schema import (
    Channel,
    ConstantSource,
    DataPoint,
    DisplayVar,
    ExecutionVariable,
    MeasurementExecution,
    MeasurementSetup,
    MeasurementTiming,
    QscvSetup,
    RangeSetting,
    SamplingSetup,
    StopCondition,
    SweepSetup,
    SweepVar1,
    SweepVar2,
    SweepVard,
)


# =============================================================================
# dict  ->  ORM
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
    """Build a full (un-persisted) ORM setup graph from a canonical config dict."""
    mode = config["mode"]
    if mode == "SWEEP":
        setup: MeasurementSetup = SweepSetup()
        _apply_sweep(setup, config["sweep_setup"])
        constants = config["sweep_setup"].get("constants", {})
    elif mode == "SAMP":
        setup = SamplingSetup()
        _apply_sampling(setup, config["sampling_setup"])
        constants = config["sampling_setup"].get("constants", {})
    elif mode == "QSCV":
        setup = QscvSetup()
        constants = {}
    else:
        raise ValueError(f"Unsupported measurement mode: {mode!r}")

    setup.name = name
    setup.description = description
    setup.author = author
    setup.organization = organization
    setup.instrument_model = instrument_model
    setup.interlock_open = interlock_open
    setup.common_to_ground = common_to_ground

    setup.channels = _channels_to_rows(config["channels"])
    setup.timing = _timing_to_row(config["measurement_setup"])
    setup.ranges = _ranges_to_rows(
        config["measurement_setup"].get("ranges", {})
    )
    setup.constants = _constants_to_rows(constants)
    setup.display_vars = _display_vars_to_rows(config.get("display_vars", []))
    return setup


def _channels_to_rows(channels: Mapping[str, dict]) -> list[Channel]:
    rows: list[Channel] = []
    for unit_id, ch in channels.items():
        kind = unit_id[:3]  # SMU / VMU / VSU
        index = int(unit_id[3:])
        if "disable" in ch:
            rows.append(
                Channel(unit_kind=kind, unit_index=index, disabled=True)
            )
        elif kind == "SMU":
            rows.append(
                Channel(
                    unit_kind=kind,
                    unit_index=index,
                    disabled=False,
                    v_name=ch["v_name"],
                    i_name=ch["i_name"],
                    function=ch["function"],
                    smu_mode=ch["smu_mode"],
                    standby=(ch["standby"] == "ON"),
                )
            )
        elif kind == "VMU":
            rows.append(
                Channel(
                    unit_kind=kind,
                    unit_index=index,
                    disabled=False,
                    v_name=ch["v_name"],
                    vmu_mode=ch["vmu_mode"],
                )
            )
        elif kind == "VSU":
            rows.append(
                Channel(
                    unit_kind=kind,
                    unit_index=index,
                    disabled=False,
                    v_name=ch["v_name"],
                    function=ch["function"],
                )
            )
    return rows


def _timing_to_row(ms: Mapping[str, Any]) -> MeasurementTiming:
    return MeasurementTiming(
        integration_mode=ms["integration_mode"],
        short_time=ms["short_time"],
        long_time_cycles=ms["long_time_cycles"],
        wait_time=ms["wait_time"],
    )


def _ranges_to_rows(ranges: Mapping[str, dict]) -> list[RangeSetting]:
    return [
        RangeSetting(unit_id=uid, mode=r["mode"], value=r.get("value"))
        for uid, r in ranges.items()
    ]


def _constants_to_rows(constants: Mapping[str, dict]) -> list[ConstantSource]:
    return [
        ConstantSource(
            unit_id=uid,
            source=c.get("source"),
            compliance=c.get("compliance"),
        )
        for uid, c in constants.items()
    ]


def _display_vars_to_rows(names: Iterable[str]) -> list[DisplayVar]:
    return [
        DisplayVar(position=i, var_name=v) for i, v in enumerate(names)
    ]


def _apply_sweep(setup: SweepSetup, sweep: Mapping[str, Any]) -> None:
    setup.delay = sweep["delay"]
    setup.hold_time = sweep["hold_time"]
    setup.sweep_stop = sweep["sweep_stop"]
    if "var1" in sweep:
        v = sweep["var1"]
        setup.var1 = SweepVar1(
            mode=v["mode"],
            spacing=v["spacing"],
            start=v["start"],
            stop=v["stop"],
            step=v["step"],
            compliance=v.get("compliance"),
            pcompliance=v.get("pcompliance"),
        )
    if "var2" in sweep:
        v = sweep["var2"]
        setup.var2 = SweepVar2(
            start=v["start"],
            step=v["step"],
            points=v["points"],
            compliance=v.get("compliance"),
            pcompliance=v.get("pcompliance"),
        )
    if "vard" in sweep:
        v = sweep["vard"]
        setup.vard = SweepVard(
            offset=v["offset"],
            ratio=v["ratio"],
            compliance=v.get("compliance"),
            pcompliance=v.get("pcompliance"),
        )


def _apply_sampling(setup: SamplingSetup, samp: Mapping[str, Any]) -> None:
    setup.mode = samp["mode"]
    setup.initial_interval = samp["initial_interval"]
    setup.points = samp["points"]
    setup.hold_time = samp["hold_time"]
    setup.filter_on = samp["filter"] == "ON"

    # Period tri-state (+ "NA" for log modes that carry no period key).
    if "period" not in samp and "period_auto" not in samp:
        setup.period_mode = "NA"
        setup.period_value = None
    elif samp.get("period_auto") == "ON":
        setup.period_mode = "AUTO"
        setup.period_value = None
    elif samp.get("period") == "INFINITY":
        setup.period_mode = "NO_LIMIT"
        setup.period_value = None
    else:
        setup.period_mode = "NUMERIC"
        setup.period_value = float(samp["period"])

    sc = samp.get("scon", {"state": "OFF"})
    if sc.get("state") == "ON":
        setup.stop_condition = StopCondition(
            name=sc["name"],
            threshold=sc["threshold"],
            event=sc["event"],
            event_count=sc["event_count"],
            enable_delay=sc["enable_delay"],
        )


# =============================================================================
# ORM  ->  dict
# =============================================================================


def setup_to_config_dict(setup: MeasurementSetup) -> dict:
    """Reconstruct the exact canonical config dict from an ORM setup graph."""
    if isinstance(setup, SweepSetup):
        mode = "SWEEP"
    elif isinstance(setup, SamplingSetup):
        mode = "SAMP"
    elif isinstance(setup, QscvSetup):
        mode = "QSCV"
    else:
        mode = setup.setup_type

    out: dict[str, Any] = {
        "mode": mode,
        "channels": _channels_to_dict(setup.channels),
        "measurement_setup": _timing_to_dict(setup.timing, setup.ranges),
        "display_vars": [
            dv.var_name
            for dv in sorted(setup.display_vars, key=lambda d: d.position)
        ],
    }
    if mode == "SWEEP":
        out["sweep_setup"] = _sweep_to_dict(setup)
    elif mode == "SAMP":
        out["sampling_setup"] = _sampling_to_dict(setup)
    return out


def _channels_to_dict(channels: Iterable[Channel]) -> dict:
    out: dict[str, Any] = {}
    for ch in channels:
        unit_id = f"{ch.unit_kind}{ch.unit_index}"
        if ch.disabled:
            out[unit_id] = {"disable": 1}
        elif ch.unit_kind == "SMU":
            out[unit_id] = {
                "v_name": ch.v_name,
                "i_name": ch.i_name,
                "function": ch.function,
                "smu_mode": ch.smu_mode,
                "standby": "ON" if ch.standby else "OFF",
            }
        elif ch.unit_kind == "VMU":
            out[unit_id] = {"v_name": ch.v_name, "vmu_mode": ch.vmu_mode}
        elif ch.unit_kind == "VSU":
            out[unit_id] = {"v_name": ch.v_name, "function": ch.function}
    return out


def _timing_to_dict(
    timing: MeasurementTiming, ranges: Iterable[RangeSetting]
) -> dict:
    return {
        "integration_mode": timing.integration_mode,
        "short_time": timing.short_time,
        "long_time_cycles": timing.long_time_cycles,
        "wait_time": timing.wait_time,
        "ranges": _ranges_to_dict(ranges),
    }


def _ranges_to_dict(ranges: Iterable[RangeSetting]) -> dict:
    out: dict[str, Any] = {}
    for r in ranges:
        entry: dict[str, Any] = {"mode": r.mode}
        if r.value is not None:
            entry["value"] = r.value
        out[r.unit_id] = entry
    return out


def _constants_to_dict(constants: Iterable[ConstantSource]) -> dict:
    out: dict[str, Any] = {}
    for c in constants:
        entry: dict[str, Any] = {}
        if c.source is not None:
            entry["source"] = c.source
        if c.compliance is not None:
            entry["compliance"] = c.compliance
        out[c.unit_id] = entry
    return out


def _sweep_to_dict(setup: SweepSetup) -> dict:
    out: dict[str, Any] = {
        "delay": setup.delay,
        "hold_time": setup.hold_time,
        "sweep_stop": setup.sweep_stop,
    }
    if setup.var1 is not None:
        v = setup.var1
        d: dict[str, Any] = {
            "mode": v.mode,
            "spacing": v.spacing,
            "start": v.start,
            "stop": v.stop,
            "step": v.step,
        }
        if v.compliance is not None:
            d["compliance"] = v.compliance
        if v.pcompliance is not None:
            d["pcompliance"] = v.pcompliance
        out["var1"] = d
    if setup.var2 is not None:
        v = setup.var2
        d = {"start": v.start, "step": v.step, "points": v.points}
        if v.compliance is not None:
            d["compliance"] = v.compliance
        if v.pcompliance is not None:
            d["pcompliance"] = v.pcompliance
        out["var2"] = d
    if setup.vard is not None:
        v = setup.vard
        d = {"offset": v.offset, "ratio": v.ratio}
        if v.compliance is not None:
            d["compliance"] = v.compliance
        if v.pcompliance is not None:
            d["pcompliance"] = v.pcompliance
        out["vard"] = d

    constants = _constants_to_dict(setup.constants)
    if constants:
        out["constants"] = constants
    return out


def _sampling_to_dict(setup: SamplingSetup) -> dict:
    out: dict[str, Any] = {
        "mode": setup.mode,
        "hold_time": setup.hold_time,
        "initial_interval": setup.initial_interval,
        "points": setup.points,
        "filter": "ON" if setup.filter_on else "OFF",
    }
    pm = setup.period_mode
    if pm == "AUTO":
        out["period_auto"] = "ON"
    elif pm == "NO_LIMIT":
        out["period"] = "INFINITY"
        out["period_auto"] = "OFF"
    elif pm == "NUMERIC":
        out["period"] = setup.period_value
        out["period_auto"] = "OFF"
    # "NA" (log modes) -> no period key.

    sc = setup.stop_condition
    if sc is not None:
        out["scon"] = {
            "state": "ON",
            "name": sc.name,
            "threshold": sc.threshold,
            "event": sc.event,
            "event_count": sc.event_count,
            "enable_delay": sc.enable_delay,
        }
    else:
        out["scon"] = {"state": "OFF"}

    constants = _constants_to_dict(setup.constants)
    if constants:
        out["constants"] = constants
    return out


# =============================================================================
# Execution data
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
            DataPoint(point_index=i, value=float(value))
            for i, value in enumerate(values)
        ]
        execution.variables.append(variable)

    execution.setup = setup
    setup.last_execution_date = datetime.now()
    return execution


def execution_to_data_dict(
    execution: MeasurementExecution,
) -> dict[str, list[float]]:
    """Reconstruct a ``{var_name: [values]}`` dict for table/graph display."""
    out: dict[str, list[float]] = {}
    for var in sorted(execution.variables, key=lambda v: v.position):
        out[var.var_name] = [
            dp.value
            for dp in sorted(var.data_points, key=lambda d: d.point_index)
        ]
    return out
