"""
models/channels.py
------------------
Domain model for 4155/56 channel configuration.

Layer contract
--------------
- No Qt imports of any kind.
- Enum values are the literal SCPI strings (e.g. UnitFunction.VAR1_PRIME
  produces "VAR1'" which is sent verbatim to the instrument).
- ChannelsConstraints encodes every 4155/56 hardware rule as a pure static
  function.  The presenter calls these before mutating the config and before
  calling any display_* method on the view.

Hardware notes
--------------
All models  — 4 SMUs, 2 VSUs, 2 VMUs
C models only  — QSCV measurement mode available
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ── Enumerations ─────────────────────────────────────────────────────────────


class InstrumentModel(str, Enum):
    HP4155B = "4155B"
    HP4156B = "4156B"
    HP4155C = "4155C"
    HP4156C = "4156C"

    def supports_qscv(self) -> bool:
        """QSCV (C-V) mode is only available on C-suffix models."""
        return self in {InstrumentModel.HP4155C, InstrumentModel.HP4156C}


class MeasurementMode(str, Enum):
    SWEEP = "SWEEP"
    SAMPLING = "SAMPLING"
    QSCV = "QSCV"


class SMUMode(str, Enum):
    """
    Source function of an SMU channel (maps directly to SCPI MODE argument).
    """

    V = "V"
    I = "I"  # noqa: E741
    VPULSE = "VPULSE"
    IPULSE = "IPULSE"
    COMM = "COMM"  # SMU acts as a common return — function locked to CONST


class VMUMode(str, Enum):
    """Measurement mode of a VMU channel."""

    V = "V"
    DVOLT = "DVOLT"


class UnitFunction(str, Enum):
    """
    Source/sweep function of a unit channel.
    Values are the exact SCPI strings sent to :PAGE:CHAN:<unit>:FUNC.
    VAR1_PRIME (VAR1') is the derivative step — only meaningful for SMUs
    in Sweep mode.
    """

    CONST = "CONST"
    VAR1 = "VAR1"
    VAR2 = "VAR2"
    VAR1_PRIME = "VAR1'"  # apostrophe is part of the SCPI token


# ── Hardware constants ───────────────────────────────────────────────────────

SMU_COUNT: int = 4
VMU_COUNT: int = 2
VSU_COUNT: int = 2
MAX_NAME_LEN: int = 6  # 4155/56 variable-name character limit (hardware)
MAX_UNITS_PER_SWEEP_FUNCTION: int = 1  # only one unit may carry VAR1/VAR2/VARD


# ── Per-unit configuration ───────────────────────────────────────────────────


@dataclass
class SMUConfig:
    enabled: bool = True
    mode: SMUMode = SMUMode.V
    function: UnitFunction = UnitFunction.CONST
    voltage_name: str = "V"
    current_name: str = "I"


@dataclass
class VMUConfig:
    enabled: bool = True
    mode: VMUMode = VMUMode.V
    voltage_name: str = "VM"


@dataclass
class VSUConfig:
    """VSUs are voltage-only sources: no mode selector needed in the UI."""

    enabled: bool = True
    function: UnitFunction = UnitFunction.CONST
    voltage_name: str = "VS"


# ── Top-level session configuration ──────────────────────────────────────────


@dataclass
class ChannelsConfig:
    """
    Complete snapshot of the channels page configuration.
    All unit dicts are keyed by 1-based unit index
    (SMU1 → smu[1], VMU2 → vmu[2], …).
    """

    instrument_model: InstrumentModel = InstrumentModel.HP4155C
    measurement_mode: MeasurementMode = MeasurementMode.SWEEP
    gndu_to_common: bool = True
    inlink_enabled: bool = False

    smu: dict[int, SMUConfig] = field(
        default_factory=lambda: {
            i: SMUConfig(voltage_name=f"V{i}", current_name=f"I{i}")
            for i in range(1, SMU_COUNT + 1)
        }
    )
    vmu: dict[int, VMUConfig] = field(
        default_factory=lambda: {
            i: VMUConfig(voltage_name=f"VMU{i}")
            for i in range(1, VMU_COUNT + 1)
        }
    )
    vsu: dict[int, VSUConfig] = field(
        default_factory=lambda: {
            i: VSUConfig(voltage_name=f"VSU{i}")
            for i in range(1, VSU_COUNT + 1)
        }
    )

    def to_measure_dict(self) -> dict:
        """
        Serialize the active channel layout into the SCPI-oriented dict
        consumed by the measurement-config factory.

        Each unit is emitted under its 1-based key (``"SMU1"`` …). Disabled
        units — and VMUs in a mode where they cannot run — are emitted as
        ``{"disable": 1}``.
        """
        vmu_active = ChannelsConstraints.vmu_usable_in_mode(
            self.measurement_mode
        )
        channels: dict[str, dict] = {}

        for index, smu in self.smu.items():
            if smu.enabled:
                channels[f"SMU{index}"] = {
                    "v_name": smu.voltage_name,
                    "i_name": smu.current_name,
                    "function": UNIT_FUNCTION_SCPI_MAP[smu.function],
                    "smu_mode": SMU_MODE_SCPI_MAP[smu.mode],
                }
            else:
                channels[f"SMU{index}"] = {"disable": 1}

        for index, vmu in self.vmu.items():
            if vmu_active and vmu.enabled:
                channels[f"VMU{index}"] = {
                    "v_name": vmu.voltage_name,
                    "vmu_mode": VMU_MODE_SCPI_MAP[vmu.mode],
                }
            else:
                channels[f"VMU{index}"] = {"disable": 1}

        for index, vsu in self.vsu.items():
            if vsu.enabled:
                channels[f"VSU{index}"] = {
                    "v_name": vsu.voltage_name,
                    "function": UNIT_FUNCTION_SCPI_MAP[vsu.function],
                }
            else:
                channels[f"VSU{index}"] = {"disable": 1}

        return {
            "mode": MEASUREMENT_MODE_SCPI_MAP[self.measurement_mode],
            "channels": channels,
        }


# ── Constraint rule-set ──────────────────────────────────────────────────────


class ChannelsConstraints:
    """
    Static, pure-function rule-set encoding all 4155/56 channel constraints.

    Every method takes only model values (enums / dataclasses) and returns
    plain Python objects.  No Qt, no I/O, no side effects.

    The presenter is the sole consumer of this class.
    """

    @staticmethod
    def allowed_modes(model: InstrumentModel) -> list[MeasurementMode]:
        """QSCV is gated on C-suffix models."""
        modes: list[MeasurementMode] = [
            MeasurementMode.SWEEP,
            MeasurementMode.SAMPLING,
        ]
        if model.supports_qscv():
            modes.append(MeasurementMode.QSCV)
        return modes

    @staticmethod
    def vmu_usable_in_mode(mode: MeasurementMode) -> bool:
        """
        VMUs are monitor-only units, usable in Sweep and Sampling.
        Only in QSCV they are disabled in hardware and must be
        greyed-out in the UI.
        """
        return mode in {MeasurementMode.SWEEP, MeasurementMode.SAMPLING}

    @staticmethod
    def smu_functions(mode: MeasurementMode) -> list[UnitFunction]:
        if mode == MeasurementMode.SWEEP:
            return [
                UnitFunction.CONST,
                UnitFunction.VAR1,
                UnitFunction.VAR2,
                UnitFunction.VAR1_PRIME,
            ]
        if mode == MeasurementMode.SAMPLING:
            return [UnitFunction.CONST]
        if mode == MeasurementMode.QSCV:
            return [UnitFunction.CONST, UnitFunction.VAR1]
        return [UnitFunction.CONST]

    @staticmethod
    def vsu_functions(mode: MeasurementMode) -> list[UnitFunction]:
        """
        VSUs can sweep in Sweep mode.  In QSCV only SMUs may carry VAR1,
        so VSUs are constrained to CONST.  Same for Sampling.
        """
        if mode == MeasurementMode.SWEEP:
            return [
                UnitFunction.CONST,
                UnitFunction.VAR1,
                UnitFunction.VAR2,
                UnitFunction.VAR1_PRIME,
            ]
        return [UnitFunction.CONST]  # SAMPLING and QSCV

    @staticmethod
    def smu_function_locked(mode: SMUMode) -> bool:
        """
        COMM mode forces the SMU to act as a passive return path.
        The function is locked to CONST and the combo must be disabled.
        """
        return mode == SMUMode.COMM

    @staticmethod
    def clamp_function(
        current: UnitFunction,
        allowed: list[UnitFunction],
    ) -> UnitFunction:
        """
        Return current if still in the allowed set, else fall back to CONST.
        """
        return current if current in allowed else UnitFunction.CONST

    @staticmethod
    def clamp_mode(
        current: MeasurementMode,
        allowed: list[MeasurementMode],
    ) -> MeasurementMode:
        """Return current if still valid for the selected model, else SWEEP."""
        return current if current in allowed else MeasurementMode.SWEEP

    @staticmethod
    def _active_variable_names(cfg: ChannelsConfig) -> list[str]:
        """Voltage/current names of every unit contributing to the run."""
        names: list[str] = []
        for smu in cfg.smu.values():
            if smu.enabled:
                names.append(smu.voltage_name)
                names.append(smu.current_name)
        if ChannelsConstraints.vmu_usable_in_mode(cfg.measurement_mode):
            for vmu in cfg.vmu.values():
                if vmu.enabled:
                    names.append(vmu.voltage_name)
        for vsu in cfg.vsu.values():
            if vsu.enabled:
                names.append(vsu.voltage_name)
        return names

    @staticmethod
    def _any_unit_enabled(cfg: ChannelsConfig) -> bool:
        """True if at least one unit contributing to the run is enabled."""
        if any(smu.enabled for smu in cfg.smu.values()):
            return True
        if ChannelsConstraints.vmu_usable_in_mode(
            cfg.measurement_mode
        ) and any(vmu.enabled for vmu in cfg.vmu.values()):
            return True
        return any(vsu.enabled for vsu in cfg.vsu.values())

    @staticmethod
    def _count_function(cfg: ChannelsConfig, function: UnitFunction) -> int:
        """Count enabled SMUs and VSUs assigned to *function*."""
        sweep_units = [*cfg.smu.values(), *cfg.vsu.values()]
        return sum(
            1
            for unit in sweep_units
            if unit.enabled and unit.function == function
        )

    @staticmethod
    def _first_unit_with_function(
        cfg: ChannelsConfig, function: UnitFunction
    ) -> SMUConfig | VSUConfig | None:
        """First enabled SMU (then VSU) assigned to *function*, or None."""
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == function:
                return smu
        for vsu in cfg.vsu.values():
            if vsu.enabled and vsu.function == function:
                return vsu
        return None

    @staticmethod
    def _sweep_signal_type(unit: SMUConfig | VSUConfig) -> str:
        """'V', 'I' or 'COMM' — the signal type a sweep unit drives."""
        if isinstance(unit, VSUConfig):
            return "V"
        if unit.mode in {SMUMode.V, SMUMode.VPULSE}:
            return "V"
        if unit.mode in {SMUMode.I, SMUMode.IPULSE}:
            return "I"
        return "COMM"

    @staticmethod
    def validate_config(cfg: ChannelsConfig) -> list[str]:
        errors: list[str] = []

        # 1.1.1) Two units or more share the same voltage/current name
        norm_names = [
            name.strip().upper()
            for name in ChannelsConstraints._active_variable_names(cfg)
            if name.strip()
        ]
        if len(norm_names) != len(set(norm_names)):
            errors.append(
                "Two units or more have the same voltage/current variable name"
            )

        # 1.1.2) All units are disabled
        if not ChannelsConstraints._any_unit_enabled(cfg):
            errors.append("All units are disabled")

        # 1.1.3) Two units or more are selected as primary sweep
        var1_count = ChannelsConstraints._count_function(
            cfg, UnitFunction.VAR1
        )
        if var1_count > MAX_UNITS_PER_SWEEP_FUNCTION:
            errors.append("Two units or more are selected as primary sweep")

        # 1.1.4) Two units or more are selected as subordinate sweep
        var2_count = ChannelsConstraints._count_function(
            cfg, UnitFunction.VAR2
        )
        if var2_count > MAX_UNITS_PER_SWEEP_FUNCTION:
            errors.append(
                "Two units or more are selected as subordinate sweep"
            )

        # 1.1.5) Two units or more are selected as VARD
        vard_count = ChannelsConstraints._count_function(
            cfg, UnitFunction.VAR1_PRIME
        )
        if vard_count > MAX_UNITS_PER_SWEEP_FUNCTION:
            errors.append("Two units or more are selected as VARD")

        # 1.1.6) Sweep and QSCV modes require a primary sweep unit
        sweep_like = {MeasurementMode.SWEEP, MeasurementMode.QSCV}
        if cfg.measurement_mode in sweep_like and var1_count == 0:
            errors.append(
                "At least one unit must be selected as primary sweep for "
                "sweep and qscv modes"
            )

        # 1.1.7) Primary sweep and VARD must share the same V/I mode type
        var1_unit = ChannelsConstraints._first_unit_with_function(
            cfg, UnitFunction.VAR1
        )
        vard_unit = ChannelsConstraints._first_unit_with_function(
            cfg, UnitFunction.VAR1_PRIME
        )
        if var1_unit is not None and vard_unit is not None:
            var1_type = ChannelsConstraints._sweep_signal_type(var1_unit)
            vard_type = ChannelsConstraints._sweep_signal_type(vard_unit)
            if "COMM" in {var1_type, vard_type} or var1_type != vard_type:
                errors.append(
                    "Primary sweep and VARD must have the same V/I mode type"
                )

        return errors


# ── SCPI Mapping Dictionaries ───────────────────────────────────────────────

MEASUREMENT_MODE_SCPI_MAP = {
    MeasurementMode.SWEEP: "SWEEP",
    MeasurementMode.SAMPLING: "SAMP",
    MeasurementMode.QSCV: "QSCV",
}

SMU_MODE_SCPI_MAP = {
    SMUMode.V: "V",
    SMUMode.I: "I",
    SMUMode.VPULSE: "VPUL",
    SMUMode.IPULSE: "IPUL",
    SMUMode.COMM: "COMM",
}

VMU_MODE_SCPI_MAP = {
    VMUMode.V: "V",
    VMUMode.DVOLT: "DVOL",
}

UNIT_FUNCTION_SCPI_MAP = {
    UnitFunction.CONST: "CONS",
    UnitFunction.VAR1: "VAR1",
    UnitFunction.VAR2: "VAR2",
    UnitFunction.VAR1_PRIME: "VARD",
}
