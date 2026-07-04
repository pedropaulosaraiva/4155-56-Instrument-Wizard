"""
models/config_loader.py
-----------------------
Reconstruct domain models from a canonical measurement-config dict.

These are the inverse of the sweep/sampling presenters' ``_build_json`` and of
``ChannelsConfig.to_measure_dict`` — used by the "Copy to measurement
configuration" action to repopulate a freshly generated config page from a
saved setup.

Layer contract: no Qt imports (pure model reconstruction).  Enum coercion is
defensive: any unexpected/legacy value falls back to a sane default rather than
raising, so a stored setup can never crash the copy.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Type

from wizard_4155_4156.models.channels import (
    DEFAULT_INSTRUMENT_MODEL,
    ChannelsConfig,
    InstrumentModel,
    MeasurementMode,
    SMUConfig,
    SMUMode,
    UnitFunction,
    VMUConfig,
    VMUMode,
    VSUConfig,
)
from wizard_4155_4156.models.qscv_config import QscvConfig
from wizard_4155_4156.models.sampling_config import (
    PeriodMode,
    SamplingConfig,
    SamplingMode,
    SConEvent,
)
from wizard_4155_4156.models.sweep_config import (
    IntegrationMode,
    SweepConfig,
    SweepSpacing,
    SweepStop,
    VAR1Mode,
)

# JSON ``function`` token (see _fn_to_json_key) → UnitFunction.
_JSON_FN_TO_UNIT = {
    "CONS": UnitFunction.CONST,
    "VAR1": UnitFunction.VAR1,
    "VAR2": UnitFunction.VAR2,
    "VARD": UnitFunction.VAR1_PRIME,
}

# JSON top-level ``mode`` → MeasurementMode.
_JSON_MODE_TO_MEAS = {
    "SWEEP": MeasurementMode.SWEEP,
    "SAMP": MeasurementMode.SAMPLING,
    "QSCV": MeasurementMode.QSCV,
}


def _enum(cls: Type, value: Any, default):
    try:
        return cls(value)
    except (ValueError, KeyError):
        return default


def _truthy(value: Any) -> bool:
    """Coerce a stored bool / SCPI on-off string to a Python bool."""
    if isinstance(value, str):
        return value.strip().upper() in ("ON", "TRUE", "1", "YES")
    return bool(value)


def _standby_from_channels(channels: Mapping[str, dict]) -> dict[str, bool]:
    return {
        unit_id: ch.get("standby") == "ON"
        for unit_id, ch in channels.items()
        if "standby" in ch
    }


# =============================================================================
# Channels
# =============================================================================


def channels_config_from_setup(
    config: Mapping[str, Any],
    *,
    instrument_model: str,
    interlock_open: bool = True,
    common_to_ground: bool = True,
) -> ChannelsConfig:
    """Rebuild a ChannelsConfig from a setup's config dict."""
    channels = config.get("channels", {})
    measurement_mode = _JSON_MODE_TO_MEAS.get(
        config.get("mode", "SWEEP"), MeasurementMode.SWEEP
    )

    smu: dict[int, SMUConfig] = {}
    for i in range(1, 5):
        ch = channels.get(f"SMU{i}", {"disable": 1})
        if "disable" in ch:
            smu[i] = SMUConfig(
                enabled=False, voltage_name=f"V{i}", current_name=f"I{i}"
            )
        else:
            smu[i] = SMUConfig(
                enabled=True,
                mode=_enum(SMUMode, ch.get("smu_mode"), SMUMode.V),
                function=_JSON_FN_TO_UNIT.get(
                    ch.get("function"), UnitFunction.CONST
                ),
                voltage_name=ch.get("v_name", f"V{i}"),
                current_name=ch.get("i_name", f"I{i}"),
            )

    vmu: dict[int, VMUConfig] = {}
    for i in range(1, 3):
        ch = channels.get(f"VMU{i}", {"disable": 1})
        if "disable" in ch:
            vmu[i] = VMUConfig(enabled=False, voltage_name=f"VMU{i}")
        else:
            vmu[i] = VMUConfig(
                enabled=True,
                mode=_enum(VMUMode, ch.get("vmu_mode"), VMUMode.V),
                voltage_name=ch.get("v_name", f"VMU{i}"),
            )

    vsu: dict[int, VSUConfig] = {}
    for i in range(1, 3):
        ch = channels.get(f"VSU{i}", {"disable": 1})
        if "disable" in ch:
            vsu[i] = VSUConfig(enabled=False, voltage_name=f"VSU{i}")
        else:
            vsu[i] = VSUConfig(
                enabled=True,
                function=_JSON_FN_TO_UNIT.get(
                    ch.get("function"), UnitFunction.CONST
                ),
                voltage_name=ch.get("v_name", f"VSU{i}"),
            )

    return ChannelsConfig(
        instrument_model=_enum(
            InstrumentModel, instrument_model, DEFAULT_INSTRUMENT_MODEL
        ),
        measurement_mode=measurement_mode,
        common_to_ground=common_to_ground,
        interlock_open=interlock_open,
        smu=smu,
        vmu=vmu,
        vsu=vsu,
    )


# =============================================================================
# Sweep
# =============================================================================


def sweep_config_from_setup(config: Mapping[str, Any]) -> SweepConfig:
    """Rebuild a SweepConfig from a setup's config dict."""
    cfg = SweepConfig()
    _load_measurement_setup(cfg, config.get("measurement_setup", {}))

    ss = config.get("sweep_setup", {})
    cfg.delay = ss.get("delay", cfg.delay)
    cfg.hold_time = ss.get("hold_time", cfg.hold_time)
    cfg.sweep_stop = _enum(
        SweepStop, ss.get("sweep_stop"), SweepStop.COMPLIANCE
    )

    if "var1" in ss:
        v = ss["var1"]
        cfg.var1.mode = _enum(VAR1Mode, v.get("mode"), VAR1Mode.SINGLE)
        cfg.var1.spacing = _enum(
            SweepSpacing, v.get("spacing"), SweepSpacing.LINEAR
        )
        cfg.var1.start = v.get("start", cfg.var1.start)
        cfg.var1.stop = v.get("stop", cfg.var1.stop)
        cfg.var1.step = v.get("step", cfg.var1.step)
        _load_compliance(cfg.var1, v)
    if "var2" in ss:
        v = ss["var2"]
        cfg.var2.start = v.get("start", cfg.var2.start)
        cfg.var2.step = v.get("step", cfg.var2.step)
        cfg.var2.n_of_steps = v.get("n_of_steps", cfg.var2.n_of_steps)
        _load_compliance(cfg.var2, v)
    if "vard" in ss:
        v = ss["vard"]
        cfg.vard.offset = v.get("offset", cfg.vard.offset)
        cfg.vard.ratio = v.get("ratio", cfg.vard.ratio)
        _load_compliance(cfg.vard, v)

    cfg.constants = copy.deepcopy(ss.get("constants", {}))
    cfg.display_vars = list(config.get("display_vars", []))
    cfg.channel_standby = _standby_from_channels(config.get("channels", {}))
    return cfg


def _load_compliance(section, data: Mapping[str, Any]) -> None:
    if "compliance" in data:
        section.compliance = data["compliance"]
    if "pcompliance" in data:
        section.power_compliance = data["pcompliance"]
        section.power_compliance_enabled = True


# =============================================================================
# Sampling
# =============================================================================


def sampling_config_from_setup(config: Mapping[str, Any]) -> SamplingConfig:
    """Rebuild a SamplingConfig from a setup's config dict."""
    cfg = SamplingConfig()
    _load_measurement_setup(cfg, config.get("measurement_setup", {}))

    sp = config.get("sampling_setup", {})
    cfg.mode = _enum(SamplingMode, sp.get("mode"), SamplingMode.LINEAR)
    cfg.initial_interval = sp.get("initial_interval", cfg.initial_interval)
    cfg.points = sp.get("points", cfg.points)
    cfg.hold_time = sp.get("hold_time", cfg.hold_time)
    cfg.filter_on = sp.get("filter", "ON") == "ON"

    if sp.get("period_auto") == "ON":
        cfg.period_mode = PeriodMode.AUTO
    elif sp.get("period") == "INFINITY":
        cfg.period_mode = PeriodMode.NO_LIMIT
    elif "period" in sp:
        cfg.period_mode = PeriodMode.NUMERIC
        try:
            cfg.period = float(sp["period"])
        except (TypeError, ValueError):
            pass
    # else (log modes carry no period key): keep the default AUTO.

    sc = sp.get("scon", {"state": "OFF"})
    if sc.get("state") == "ON":
        cfg.stop_condition.enabled = True
        cfg.stop_condition.name = sc.get("name", "")
        cfg.stop_condition.threshold = sc.get("threshold", 0.0)
        cfg.stop_condition.event = _enum(
            SConEvent, sc.get("event"), SConEvent.HIGH
        )
        cfg.stop_condition.event_count = sc.get("event_count", 1)
        cfg.stop_condition.enable_delay = sc.get("enable_delay", 0.0)

    cfg.constants = copy.deepcopy(sp.get("constants", {}))
    cfg.display_vars = list(config.get("display_vars", []))
    cfg.channel_standby = _standby_from_channels(config.get("channels", {}))
    return cfg


def _load_measurement_setup(cfg, ms: Mapping[str, Any]) -> None:
    """Populate the shared ``measurement_setup`` block.

    Applies to a sweep/sampling cfg.
    """
    m = cfg.measurement_setup
    m.integration_mode = _enum(
        IntegrationMode, ms.get("integration_mode"), IntegrationMode.MED
    )
    m.short_time = ms.get("short_time", m.short_time)
    m.long_time_cycles = ms.get("long_time_cycles", m.long_time_cycles)
    m.wait_multiplier = ms.get("wait_time", m.wait_multiplier)
    m.ranges = copy.deepcopy(ms.get("ranges", {}))


# =============================================================================
# QSCV
# =============================================================================


def qscv_config_from_setup(config: Mapping[str, Any]) -> QscvConfig:
    """Rebuild a QscvConfig from a setup's config dict."""
    cfg = QscvConfig()
    qs = config.get("qscv_setup", {})

    cfg.cap_integration_time = qs.get(
        "cap_integration_time", cfg.cap_integration_time
    )
    cfg.leak_integration_time = qs.get(
        "leak_integration_time", cfg.leak_integration_time
    )
    cfg.delay = qs.get("delay", cfg.delay)
    cfg.hold_time = qs.get("hold_time", cfg.hold_time)
    cfg.cap_name = qs.get("cap_name", cfg.cap_name)
    cfg.leak_name = qs.get("leak_name", cfg.leak_name)
    cfg.meas_range = qs.get("range", cfg.meas_range)
    cfg.sweep_stop = _enum(
        SweepStop, qs.get("sweep_stop"), SweepStop.COMPLIANCE
    )
    cfg.measuring_unit = qs.get("unit", cfg.measuring_unit)
    cfg.leak_compensation = _truthy(
        qs.get("leak_cancel", cfg.leak_compensation)
    )
    cfg.zero_cancel = _truthy(qs.get("zero_cancel", cfg.zero_cancel))

    v = qs.get("var1", {})
    cfg.var1.mode = _enum(VAR1Mode, v.get("mode"), VAR1Mode.SINGLE)
    cfg.var1.start = v.get("start", cfg.var1.start)
    cfg.var1.stop = v.get("stop", cfg.var1.stop)
    cfg.var1.step = v.get("step", cfg.var1.step)
    cfg.var1.cstep = v.get("cstep", cfg.var1.cstep)
    cfg.var1.compliance = v.get("compliance", cfg.var1.compliance)

    cfg.constants = copy.deepcopy(qs.get("constants", {}))
    cfg.display_vars = list(config.get("display_vars", []))
    cfg.channel_standby = _standby_from_channels(config.get("channels", {}))
    return cfg
