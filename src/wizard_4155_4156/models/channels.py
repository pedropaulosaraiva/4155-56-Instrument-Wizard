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
4155B / 4155C  — 4 SMUs, 2 VSUs, NO VMUs
4156B / 4156C  — 4 SMUs, 2 VSUs, 2 VMUs
C models only  — QSCV measurement mode available
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

# ── Enumerations ─────────────────────────────────────────────────────────────


class InstrumentModel(str, Enum):
    HP4155B = "4155B"
    HP4156B = "4156B"
    HP4155C = "4155C"
    HP4156C = "4156C"

    def has_vmu(self) -> bool:
        """4156 variants ship with Voltage Monitor Units; 4155 do not."""
        return self in {
            InstrumentModel.HP4156B,
            InstrumentModel.HP4156C,
            InstrumentModel.HP4155B,
            InstrumentModel.HP4155C,
        }

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

    smu: Dict[int, SMUConfig] = field(
        default_factory=lambda: {
            i: SMUConfig(voltage_name=f"V{i}", current_name=f"I{i}")
            for i in range(1, SMU_COUNT + 1)
        }
    )
    vmu: Dict[int, VMUConfig] = field(
        default_factory=lambda: {
            i: VMUConfig(voltage_name=f"VMU{i}")
            for i in range(1, VMU_COUNT + 1)
        }
    )
    vsu: Dict[int, VSUConfig] = field(
        default_factory=lambda: {
            i: VSUConfig(voltage_name=f"VSU{i}")
            for i in range(1, VSU_COUNT + 1)
        }
    )


# ── Constraint rule-set ──────────────────────────────────────────────────────


class ChannelsConstraints:
    """
    Static, pure-function rule-set encoding all 4155/56 channel constraints.

    Every method takes only model values (enums / dataclasses) and returns
    plain Python objects.  No Qt, no I/O, no side effects.

    The presenter is the sole consumer of this class.
    """

    @staticmethod
    def allowed_modes(model: InstrumentModel) -> List[MeasurementMode]:
        """QSCV is gated on C-suffix models."""
        modes: List[MeasurementMode] = [
            MeasurementMode.SWEEP,
            MeasurementMode.SAMPLING,
        ]
        if model.supports_qscv():
            modes.append(MeasurementMode.QSCV)
        return modes

    @staticmethod
    def vmu_panel_visible(model: InstrumentModel) -> bool:
        """4155 models have no VMU hardware — the entire panel is hidden."""
        return model.has_vmu()

    @staticmethod
    def vmu_usable_in_mode(mode: MeasurementMode) -> bool:
        """
        VMUs are monitor-only units, usable in Sweep and Sampling.
        Only in QSCV they are disabled in hardware and must be
        greyed-out in the UI.
        """
        return mode in {MeasurementMode.SWEEP, MeasurementMode.SAMPLING}

    @staticmethod
    def smu_functions(mode: MeasurementMode) -> List[UnitFunction]:
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
    def vsu_functions(mode: MeasurementMode) -> List[UnitFunction]:
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
        allowed: List[UnitFunction],
    ) -> UnitFunction:
        """
        Return current if still in the allowed set, else fall back to CONST.
        """
        return current if current in allowed else UnitFunction.CONST

    @staticmethod
    def clamp_mode(
        current: MeasurementMode,
        allowed: List[MeasurementMode],
    ) -> MeasurementMode:
        """Return current if still valid for the selected model, else SWEEP."""
        return current if current in allowed else MeasurementMode.SWEEP

    @staticmethod
    def validate_config(cfg: ChannelsConfig) -> List[str]:
        errors = []

        # 1.1.1) Two units or more have the same voltage/current variable name
        names = []
        for smu in cfg.smu.values():
            if smu.enabled:
                if smu.voltage_name:
                    names.append(smu.voltage_name)
                if smu.current_name:
                    names.append(smu.current_name)
        if (
            cfg.instrument_model.has_vmu()
            and ChannelsConstraints.vmu_usable_in_mode(cfg.measurement_mode)
        ):
            for vmu in cfg.vmu.values():
                if vmu.enabled:
                    if vmu.voltage_name:
                        names.append(vmu.voltage_name)
        for vsu in cfg.vsu.values():
            if vsu.enabled:
                if vsu.voltage_name:
                    names.append(vsu.voltage_name)

        norm_names = [n.strip().upper() for n in names if n.strip()]
        if len(norm_names) != len(set(norm_names)):
            errors.append(
                "Two units or more have the same voltage/current variable name"
            )

        # 1.1.2) All units are disabled
        any_enabled = False
        for smu in cfg.smu.values():
            if smu.enabled:
                any_enabled = True
        if (
            cfg.instrument_model.has_vmu()
            and ChannelsConstraints.vmu_usable_in_mode(cfg.measurement_mode)
        ):
            for vmu in cfg.vmu.values():
                if vmu.enabled:
                    any_enabled = True
        for vsu in cfg.vsu.values():
            if vsu.enabled:
                any_enabled = True
        if not any_enabled:
            errors.append("All units are disabled")

        # 1.1.3) Two units or more are selected as primary sweep
        var1_count = 0
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == UnitFunction.VAR1:
                var1_count += 1
        for vsu in cfg.vsu.values():
            if vsu.enabled and vsu.function == UnitFunction.VAR1:
                var1_count += 1
        if var1_count >= 2:
            errors.append("Two units or more are selected as primary sweep")

        # 1.1.4) Two units or more are selected as subordinate sweep
        var2_count = 0
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == UnitFunction.VAR2:
                var2_count += 1
        for vsu in cfg.vsu.values():
            if vsu.enabled and vsu.function == UnitFunction.VAR2:
                var2_count += 1
        if var2_count >= 2:
            errors.append(
                "Two units or more are selected as subordinate sweep"
            )

        # 1.1.5) Two units or more are selected as VARD
        var1prime_count = 0
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == UnitFunction.VAR1_PRIME:
                var1prime_count += 1
        for vsu in cfg.vsu.values():
            if vsu.enabled and vsu.function == UnitFunction.VAR1_PRIME:
                var1prime_count += 1
        if var1prime_count >= 2:
            errors.append("Two units or more are selected as VARD")

        # 1.1.6) At least one unit must be selected as primary sweep for sweep and qscv modes
        if cfg.measurement_mode in {
            MeasurementMode.SWEEP,
            MeasurementMode.QSCV,
        }:
            var1_count = 0
            for smu in cfg.smu.values():
                if smu.enabled and smu.function == UnitFunction.VAR1:
                    var1_count += 1
            for vsu in cfg.vsu.values():
                if vsu.enabled and vsu.function == UnitFunction.VAR1:
                    var1_count += 1
            if var1_count == 0:
                errors.append(
                    "At least one unit must be selected as primary sweep for sweep and qscv modes"
                )

        # 1.1.7) Primary sweep and VARD must have the same V/I mode type
        var1_unit = None
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == UnitFunction.VAR1:
                var1_unit = smu
                break
        if var1_unit is None:
            for vsu in cfg.vsu.values():
                if vsu.enabled and vsu.function == UnitFunction.VAR1:
                    var1_unit = vsu
                    break

        vard_unit = None
        for smu in cfg.smu.values():
            if smu.enabled and smu.function == UnitFunction.VAR1_PRIME:
                vard_unit = smu
                break
        if vard_unit is None:
            for vsu in cfg.vsu.values():
                if vsu.enabled and vsu.function == UnitFunction.VAR1_PRIME:
                    vard_unit = vsu
                    break

        if var1_unit is not None and vard_unit is not None:
            if isinstance(var1_unit, VSUConfig):
                var1_type = "V"
            else:
                if var1_unit.mode in {SMUMode.V, SMUMode.VPULSE}:
                    var1_type = "V"
                elif var1_unit.mode in {SMUMode.I, SMUMode.IPULSE}:
                    var1_type = "I"
                else:
                    var1_type = "COMM"

            if isinstance(vard_unit, VSUConfig):
                vard_type = "V"
            else:
                if vard_unit.mode in {SMUMode.V, SMUMode.VPULSE}:
                    vard_type = "V"
                elif vard_unit.mode in {SMUMode.I, SMUMode.IPULSE}:
                    vard_type = "I"
                else:
                    vard_type = "COMM"

            if (
                var1_type == "COMM"
                or vard_type == "COMM"
                or var1_type != vard_type
            ):
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
