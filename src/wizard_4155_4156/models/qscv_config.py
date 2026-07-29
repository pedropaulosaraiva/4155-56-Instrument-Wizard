"""
models/qscv_config.py
---------------------
Domain model for the Quasi-static C-V (QSCV) measurement configuration.

Layer contract
--------------
- No Qt imports.
- All enum values are the SCPI-legal strings.
- QscvConstraints holds the cross-parameter validation rules; per-widget
  bounds are enforced by SciDoubleEdit in the view using the constants /
  helpers exported from this module.  Voltage-source and constant-source
  bounds are *reused* from models/sweep_config.py (the QSCV sweep source is
  always an SMU forcing voltage, identical hardware to a Sweep VAR1 unit).

4155C/4156C QSCV hardware limits (User's Guide Vol.2 ch.4 + builder)
--------------------------------------------------------------------
QSCV integration time (CINT) : 2 – 20000 PLC  ⇒ [2/f, 20000/f] s
Leak  integration time (IINT): 1 – 100   PLC  ⇒ [1/f, 100/f] s
  where f is the AC line frequency (50 or 60 Hz, a global setting).
Delay time                   : 0.0 – 65.535 s   (reused from sweep_config)
Hold time                    : 0.0 – 655.35 s   (reused from sweep_config)
VAR1 (voltage SMU) start/stop: ±100 V | ±40 V interlock open (reused),
                               |value| ≥ output-range resolution (0 exempt)
VAR1 step                    : ±200 V | ±80 V interlock open (reused), ≠ 0,
                               |step| ≥ 2 × output-range resolution
QSCV meas voltage (cstep)    : 0 < cstep ≤ 10 V  AND  cstep ≤ |step|  AND
                               cstep ≥ 2 × output-range resolution
VAR1 compliance (current)    : 1 pA – 0.1 A  (reused from sweep_config)
NO. OF STEP = ⌊|start-stop|/|step|⌋ − 1, must be 1 – 1001 (0 ⇒ auto-set to 1)
Measurement range            : 1 nA / 10 nA (4155C/MPSMU/HPSMU)
                               10 pA / 100 pA / 1 nA / 10 nA (4156C/HRSMU)
cap/leak name                : 1–6 chars, first char a letter

Output-range resolution
-----------------------
The "step ≥ 2× output-range resolution" and "cstep ≥ 2× output-range
resolution" rules use the Ch.7 output-range resolution table, which lives in
models/sweep_config.py (`output_range_resolution`) and is *reused* here — the
QSCV sweep source is an SMU forcing voltage, identical hardware to a Sweep
VAR1 unit.  The range is the lowest one covering max(|start|, |stop|).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Reused, unchanged hardware limits / helpers / enums from the Sweep model.
from wizard_4155_4156.models.sweep_config import (
    DELAY_MAX,
    DELAY_MIN,
    DISPLAY_VARS_MAX,
    HOLD_TIME_MAX,
    HOLD_TIME_MIN,
    SweepConstraints,
    SweepStop,
    VAR1Mode,
    current_compliance_bounds,
    output_range_resolution,
    validate_constant_sources,
    validate_display_vars,
)

__all__ = [
    "CSTEP_MAX",
    "NO_OF_STEP_MIN",
    "NO_OF_STEP_MAX",
    "QSCV_RANGES_4155",
    "QSCV_RANGES_4156",
    "cap_integration_bounds",
    "leak_integration_bounds",
    "ranges_for_model",
    "resolution_label_for",
    "valid_qscv_name",
    "QscvVar1Config",
    "QscvConfig",
    "QscvConstraints",
    "SweepStop",
    "VAR1Mode",
]

# ── QSCV-specific hardware-limit constants ──────────

# Integration time is specified in PLC (power-line cycles); the second-valued
# bounds depend on the configured line frequency.
CINT_MIN_PLC: int = 2
CINT_MAX_PLC: int = 20_000
IINT_MIN_PLC: int = 1
IINT_MAX_PLC: int = 100

# Capacitance-measurement voltage (cvoltage / cstep)
CSTEP_MAX: float = 10.0  # V

# NO. OF STEP cross-rule (start/stop voltages are not measured ⇒ −1 vs Sweep)
NO_OF_STEP_MIN: int = 1
NO_OF_STEP_MAX: int = 1001

# Measurement (current) ranges with per-range resolution.
# Tuple layout: (combo label, SCPI value [A], resolution label).
QSCV_RANGES_4156: Tuple[Tuple[str, float, str], ...] = (
    ("10 pA", 10e-12, "10 fA"),
    ("100 pA", 100e-12, "10 fA"),
    ("1 nA", 1e-9, "100 fA"),
    ("10 nA", 10e-9, "1 pA"),
)
# 4155C / MPSMU / HPSMU expose only the two larger ranges.
QSCV_RANGES_4155: Tuple[Tuple[str, float, str], ...] = (
    ("1 nA", 1e-9, "100 fA"),
    ("10 nA", 10e-9, "1 pA"),
)

_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{0,5}")


# ── Module-level helpers ────────────────────────────


# TODO: It's more safe to just output the maximun and minimun values
#  for each frequency as constants rather than calculating in executition
def cap_integration_bounds(
    line_frequency_hz: int,
) -> Tuple[float, float]:
    """QSCV (capacitance) integration-time bounds in seconds
    for a line freq."""
    f = line_frequency_hz if line_frequency_hz else 50
    return CINT_MIN_PLC / f, CINT_MAX_PLC / f


def leak_integration_bounds(line_frequency_hz: int) -> Tuple[float, float]:
    """Leakage-current integration-time bounds in seconds for a line freq."""
    f = line_frequency_hz if line_frequency_hz else 50
    return IINT_MIN_PLC / f, IINT_MAX_PLC / f


def ranges_for_model(
    instrument_model: str,
) -> Tuple[Tuple[str, float, str], ...]:
    """Allowed QSCV measurement ranges for the instrument model.

    Mirrors the RangeRow convention (``"56" in model`` ⇒ HRSMU/4156C).
    """
    return (
        QSCV_RANGES_4156
        if "56" in (instrument_model or "")
        else QSCV_RANGES_4155
    )


def resolution_label_for(instrument_model: str, range_value: float) -> str:
    """Resolution label for the selected range (empty string if unknown)."""
    for _label, value, resolution in ranges_for_model(instrument_model):
        if value == range_value:
            return resolution
    return ""


def valid_qscv_name(name: str) -> bool:
    """Match the builder rule: 1–6 chars, first a letter, alphanumeric."""
    return bool(_NAME_RE.fullmatch(name or ""))


def no_of_step(start: float, stop: float, step: float) -> Optional[int]:
    """Effective NO. OF STEP per the manual; None when step is zero.

    NO. OF STEP = ⌊|start − stop| / |step|⌋ − 1.  Per the manual a computed
    value of 0 is auto-set to 1 by the instrument; a span smaller than one
    step yields a negative (invalid) count that the caller rejects.
    """
    if step == 0:
        return None
    raw = math.floor(abs(stop - start) / abs(step))
    count = raw - 1
    return 1 if count == 0 else count


# ── Per-section dataclasses ─────────────────────────


@dataclass
class QscvVar1Config:
    """Voltage staircase sweep source (an SMU forcing V)."""

    mode: VAR1Mode = VAR1Mode.SINGLE
    start: float = 0.0
    stop: float = 1.0
    step: float = 0.1
    cstep: float = 0.1  # QSCV meas voltage (cvoltage)
    compliance: float = 0.01  # current compliance (A)


@dataclass
class QscvConfig:
    """Complete snapshot of the QSCV configuration page."""

    # A fresh page opens in Referenced Mode at 500 ms — a middle-of-the-grid
    # reference time that is legal at both 50 and 60 Hz and published for every
    # measurement range, so the capacitance ceiling is shown from the start.
    cap_integration_time: float = 0.5  # CINT (qscv time), s
    leak_integration_time: float = 0.5  # IINT (leak time), s
    delay: float = 0.0
    hold_time: float = 0.0
    measuring_unit: str = "DEFAULT"  # SMU1..SMU4 or DEFAULT
    meas_range: float = 1e-9  # capacitance current range (A)
    cap_name: str = "C"  # CNAME
    leak_name: str = "IL"  # LNAME
    leak_compensation: bool = False  # LCAN
    zero_cancel: bool = False  # ZCAN
    sweep_stop: SweepStop = SweepStop.OFF
    # Referenced Mode is a UI-only aid: it restricts the integration times to
    # the manufacturer's reference grid (and keeps cap/leak equal) so a maximum
    # measurable capacitance can be derived.  Never persisted to JSON — a fresh
    # page defaults it ON, and a loaded setup turns it on only when the stored
    # times happen to sit on the grid (see QscvConfigPresenter.__init__).
    referenced_mode: bool = True
    var1: QscvVar1Config = field(default_factory=QscvVar1Config)
    channel_standby: Dict[str, bool] = field(default_factory=dict)
    display_vars: List[str] = field(default_factory=list)
    constants: Dict[str, Dict[str, float]] = field(default_factory=dict)


def total_indexes(cfg: "QscvConfig") -> Optional[int]:
    """Total measurement indexes: NO. OF STEP × (2 if Double Sweep else 1).

    QSCV has no VAR2 (VAR2 steps ≡ 1).  Returns None when the sweep is invalid.
    """
    points = no_of_step(cfg.var1.start, cfg.var1.stop, cfg.var1.step)
    if points is None:
        return None
    double = 2 if cfg.var1.mode == VAR1Mode.DOUBLE else 1
    return points * double


# ── Constraint rule-set (cross-parameter) ───────────


class QscvConstraints:
    """Cross-parameter validation for QSCV (errors-only, mirrors Sweep)."""

    @staticmethod
    def no_of_step(start: float, stop: float, step: float) -> Optional[int]:
        return no_of_step(start, stop, step)

    @staticmethod
    def _validate_output_resolution(
        cfg: QscvConfig,
        instrument_model: str,
        prior_errors: List[str],
    ) -> List[str]:
        """
        Mirror of ``SweepConstraints._validate_output_resolution`` for the
        QSCV voltage staircase.  Every output value must be representable in
        the output range covering max(|start|, |stop|); Step and Capacitance
        Meas Voltage additionally need *twice* that resolution, since
        each capacitance point outputs a window around the DC bias.  Zero is
        always representable, so a zero Start/Stop is exempt.  Each check runs
        only when its field has no prior error: a bad Start/Stop makes the
        selected output range meaningless (so nothing is checked), and a bad
        Step or Capacitance Meas Voltage is reported once rather than
        twice.
        """
        if any(
            e.startswith(("VAR1 Start", "VAR1 Stop")) for e in prior_errors
        ):
            return []

        v1 = cfg.var1
        unit = SweepConstraints.source_unit(True)
        rng, res = output_range_resolution(
            True, False, instrument_model, max(abs(v1.start), abs(v1.stop))
        )
        errors: List[str] = []

        def below(label: str, magnitude: float, doubled: bool) -> str:
            limit = (
                f"twice the output resolution "
                f"(2 x {res:.3g} {unit} = {2 * res:.3g} {unit})"
                if doubled
                else f"the output resolution {res:.3g} {unit}"
            )
            return (
                f"{label}: {magnitude:.3g} {unit} is below {limit} "
                f"of the {rng:.3g} {unit} output range"
            )

        for label, value in (("VAR1 Start", v1.start), ("VAR1 Stop", v1.stop)):
            if 0 < abs(value) < res:
                errors.append(below(label, abs(value), False))
        if not any(e.startswith("VAR1 Step") for e in prior_errors):
            if abs(v1.step) < 2 * res:
                errors.append(below("VAR1 Step", abs(v1.step), True))
        cm_label = "Capacitance Meas Voltage"
        if not any(e.startswith(cm_label) for e in prior_errors):
            if abs(v1.cstep) < 2 * res:
                errors.append(below(cm_label, abs(v1.cstep), True))
        return errors

    @staticmethod
    def validate_config(
        cfg: QscvConfig,
        *,
        active_channels: Optional[List[dict]] = None,
        instrument_model: str = "4156C",
        line_frequency_hz: int = 50,
        enabled_smu_ids: Optional[List[str]] = None,
        interlock_open: bool = False,
    ) -> List[str]:
        """Return a flat list of blocking error strings (empty ⇒ valid)."""
        errors: List[str] = []
        SC = SweepConstraints

        # 1. Integration times (line-frequency dependent)
        cmin, cmax = cap_integration_bounds(line_frequency_hz)
        if not (cmin <= cfg.cap_integration_time <= cmax):
            errors.append(
                f"Capacitance Integration Time: invalid value "
                f"(range: {cmin:.4g} – {cmax:.4g} s "
                f"at {line_frequency_hz} Hz)"
            )
        lmin, lmax = leak_integration_bounds(line_frequency_hz)
        if not (lmin <= cfg.leak_integration_time <= lmax):
            errors.append(
                f"Leak Integration Time: invalid value "
                f"(range: {lmin:.4g} – {lmax:.4g} s at {line_frequency_hz} Hz)"
            )

        # 1b. Referenced Mode restricts the integration time to the reference
        # grid and keeps both times equal.  Imported inside the function:
        # models/qscv_reference.py depends on this module's integration bounds,
        # so a module-level import would be circular.
        if cfg.referenced_mode:
            from wizard_4155_4156.models.qscv_reference import (  # noqa: PLC0415
                format_integration_time,
                supported_integration_times,
            )

            allowed_times = supported_integration_times(
                cfg.meas_range, line_frequency_hz
            )
            if not any(
                math.isclose(cfg.cap_integration_time, t, rel_tol=1e-9)
                for t in allowed_times
            ):
                shown = (
                    ", ".join(
                        format_integration_time(t) for t in allowed_times
                    )
                    or "none for this range"
                )
                errors.append(
                    f"Capacitance Integration Time: Referenced Mode allows "
                    f"only the manufacturer reference times ({shown})"
                )
            elif not math.isclose(
                cfg.cap_integration_time,
                cfg.leak_integration_time,
                rel_tol=1e-9,
            ):
                errors.append(
                    "Referenced Mode: QSCV and Leak Integration Time must be "
                    "equal"
                )

        # 2. Timing
        if not (DELAY_MIN <= cfg.delay <= DELAY_MAX):
            errors.append(
                f"Delay: invalid value "
                f"(range: {DELAY_MIN:.3g} – "
                f"{DELAY_MAX:.3g} s)"
            )
        if not (HOLD_TIME_MIN <= cfg.hold_time <= HOLD_TIME_MAX):
            errors.append(
                f"Hold Time: invalid value "
                f"(range: {HOLD_TIME_MIN:.3g} – {HOLD_TIME_MAX:.3g} s)"
            )

        # 3. Names
        if not valid_qscv_name(cfg.cap_name):
            errors.append(
                "Capacitance Name: must be 1–6 "
                "characters and start with a letter"
            )
        if cfg.leak_compensation:
            if not valid_qscv_name(cfg.leak_name):
                errors.append(
                    "Leak compensation is ON: a valid Leakage Current Name "
                    "(1–6 chars, first a letter) is required"
                )
        elif cfg.leak_name.strip() and not valid_qscv_name(cfg.leak_name):
            errors.append(
                "Leakage Current Name: must be "
                "1–6 characters and start "
                "with a letter"
            )

        # 4. Measurement range (instrument-gated)
        allowed = ranges_for_model(instrument_model)
        if cfg.meas_range not in {value for _, value, _ in allowed}:
            labels = ", ".join(label for label, _, _ in allowed)
            errors.append(
                f"Measurement Range: invalid for {instrument_model} "
                f"(allowed: {labels})"
            )

        # 5. Measuring unit must be DEFAULT or an enabled SMU
        if cfg.measuring_unit != "DEFAULT":
            if cfg.measuring_unit not in set(enabled_smu_ids or []):
                errors.append(
                    f"Measurement Unit: "
                    f"{cfg.measuring_unit} "
                    f"is not an enabled SMU"
                )

        # 6. VAR1 (always an SMU forcing voltage)
        v1 = cfg.var1
        src_min, src_max = SC.source_range(True, False, interlock_open)
        if not (src_min <= v1.start <= src_max):
            errors.append(
                f"VAR1 Start: invalid value "
                f"(range: {src_min:.3g} – "
                f"{src_max:.3g} V)"
            )
        if not (src_min <= v1.stop <= src_max):
            errors.append(
                f"VAR1 Stop: invalid value "
                f"(range: {src_min:.3g} – "
                f"{src_max:.3g} V)"
            )
        stp_min, stp_max = SC.step_range(
            True, is_var2_or_offset=False, interlock_open=interlock_open
        )
        if v1.step == 0:
            errors.append("VAR1 Step: cannot be zero")
        elif not (stp_min <= v1.step <= stp_max):
            errors.append(
                f"VAR1 Step: invalid value "
                f"(range: {stp_min:.3g} – "
                f"{stp_max:.3g} V)"
            )
        elif v1.step > 0 and v1.stop <= v1.start:
            errors.append(
                "VAR1: Stop must be greater than Start when Step is positive."
            )
        elif v1.step < 0 and v1.stop >= v1.start:
            errors.append(
                "VAR1: Stop must be less than Start when Step is negative."
            )

        if not any(e.startswith(("VAR1 Start", "VAR1 Stop")) for e in errors):
            v1_mag = max(abs(v1.start), abs(v1.stop))
            comp_min, comp_max = current_compliance_bounds(
                instrument_model, v1_mag, interlock_open
            )
            if not (comp_min <= v1.compliance <= comp_max):
                errors.append(
                    f"VAR1 Compliance: invalid value "
                    f"(range: {comp_min:.3g} – {comp_max:.3g} A)"
                )

        # 7. QSCV meas voltage (cstep): 0 < cstep ≤ 10 V and cstep ≤ |step|.
        # cvoltage is a small perturbation window (output ± cvoltage/2) around
        # each DC bias step; it must fit within the step spacing.
        if not (0 < v1.cstep <= CSTEP_MAX):
            errors.append(
                f"Capacitance Meas Voltage: invalid "
                f"value (range: 0 < v ≤ "
                f"{CSTEP_MAX:g} V)"
            )
        elif v1.step != 0 and v1.cstep > abs(v1.step):
            errors.append(
                f"Capacitance Meas Voltage: must be ≤ |Step| "
                f"({abs(v1.step):.3g} V)"
            )

        # 8. NO. OF STEP (only when the basic VAR1 sweep params are sound)
        if not any(e.startswith("VAR1") for e in errors):
            count = QscvConstraints.no_of_step(v1.start, v1.stop, v1.step)
            if count is None or not (
                NO_OF_STEP_MIN <= count <= NO_OF_STEP_MAX
            ):
                shown = count if count is not None else 0
                errors.append(
                    f"VAR1: {shown} steps "
                    f"(NO. OF STEP must be {NO_OF_STEP_MIN}–{NO_OF_STEP_MAX})"
                )

        # 9. Output resolution — runs after the NO. OF STEP block (which gates
        # on "VAR1"), so a resolution error never suppresses it.
        errors.extend(
            QscvConstraints._validate_output_resolution(
                cfg, instrument_model, errors
            )
        )

        # 10. Display variables: ≥2 selected, ≥1 measurement variable (C/IL).
        measurement_vars: List[str] = []
        if cfg.cap_name.strip():
            measurement_vars.append(cfg.cap_name.strip())
        if cfg.leak_name.strip():
            measurement_vars.append(cfg.leak_name.strip())
        errors.extend(
            validate_display_vars(
                cfg.display_vars,
                measurement_vars,
                max_total=DISPLAY_VARS_MAX,
            )
        )

        # 11. Constant sources (shared validator)
        errors.extend(
            validate_constant_sources(
                cfg.constants, active_channels, interlock_open
            )
        )

        return errors
