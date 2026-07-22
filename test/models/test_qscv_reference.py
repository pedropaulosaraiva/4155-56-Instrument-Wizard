"""
Tests for models/qscv_reference.py — the manufacturer reference data for the
maximum measurable capacitance in QSCV (Referenced Mode).

The published fits all have slope −1.000, so C_max(V) = A / V with
A = 10**intercept; the intercepts are the values transcribed in
``coefficients_summary_corrected.txt``.
"""

import math

import pytest

from wizard_4155_4156.models.qscv_config import (
    QscvConfig,
    QscvConstraints,
)
from wizard_4155_4156.models.qscv_reference import (
    REFERENCE_INTEGRATION_TIMES,
    REFERENCE_INTERCEPTS,
    REFERENCE_SLOPE,
    format_capacitance,
    format_integration_time,
    max_capacitance,
    nearest_supported_time,
    supported_integration_times,
)

R_10PA = 10e-12
R_100PA = 100e-12
R_1NA = 1e-9
R_10NA = 10e-9

ALL_RANGES = (R_10PA, R_100PA, R_1NA, R_10NA)

# Reference-grid integration times (seconds).
T_2S = 2.0
T_1S = 1.0
T_500MS = 0.5
T_300MS = 0.3
T_100MS = 0.1
T_50MS = 0.05
T_30MS = 0.03


# ── Coefficient table ────────────────────────────────────────────────────────


def test_slope_is_minus_one():
    assert REFERENCE_SLOPE == -1.0


def test_ten_and_hundred_pa_share_the_same_curves():
    """Image 1 of the reference data covers both HRSMU low ranges."""
    for time in (2.0, 1.0, 0.5, 0.3):
        assert (
            REFERENCE_INTERCEPTS[(R_10PA, time)]
            == REFERENCE_INTERCEPTS[(R_100PA, time)]
        )


def test_low_ranges_stop_at_300ms():
    """The 10 pA / 100 pA curves are only published down to 300 ms."""
    for time in (0.1, 0.05, 0.03):
        assert (R_10PA, time) not in REFERENCE_INTERCEPTS
        assert (R_100PA, time) not in REFERENCE_INTERCEPTS


def test_na_ranges_cover_every_reference_time():
    for time in REFERENCE_INTEGRATION_TIMES:
        assert (R_1NA, time) in REFERENCE_INTERCEPTS
        assert (R_10NA, time) in REFERENCE_INTERCEPTS


def test_table_has_no_unexpected_keys():
    for range_value, time in REFERENCE_INTERCEPTS:
        assert range_value in ALL_RANGES
        assert time in REFERENCE_INTEGRATION_TIMES


def test_longer_integration_allows_higher_capacitance():
    """Monotonicity claimed by the reference data, per range."""
    for range_value in ALL_RANGES:
        times = [
            t
            for t in REFERENCE_INTEGRATION_TIMES
            if (range_value, t) in REFERENCE_INTERCEPTS
        ]
        values = [max_capacitance(range_value, t, 1.0) for t in times]
        assert values == sorted(values, reverse=True)


def test_higher_range_allows_higher_capacitance():
    for time in (2.0, 1.0, 0.5, 0.3):
        assert max_capacitance(R_10NA, time, 1.0) > max_capacitance(
            R_1NA, time, 1.0
        )
        assert max_capacitance(R_1NA, time, 1.0) > max_capacitance(
            R_10PA, time, 1.0
        )


# ── max_capacitance ──────────────────────────────────────────────────────────


def test_at_one_volt_result_is_the_linear_coefficient():
    """V = 1 ⇒ C_max = A = 10**intercept."""
    assert max_capacitance(R_1NA, 1.0, 1.0) == pytest.approx(10**-8.127)
    assert max_capacitance(R_10NA, 2.0, 1.0) == pytest.approx(10**-7.724)
    assert max_capacitance(R_10PA, 0.3, 1.0) == pytest.approx(10**-13.58)


def test_inverse_law_halving_voltage_doubles_capacitance():
    at_1v = max_capacitance(R_10NA, 2.0, 1.0)
    at_half = max_capacitance(R_10NA, 2.0, 0.5)
    assert at_half == pytest.approx(2 * at_1v)


def test_matches_the_general_log_form():
    """C_max = A/V is the slope=−1 case of log10(C) = n·log10(V) + b."""
    voltage = 3.7
    intercept = REFERENCE_INTERCEPTS[(R_1NA, 0.05)]
    expected = 10 ** (REFERENCE_SLOPE * math.log10(voltage) + intercept)
    assert max_capacitance(R_1NA, 0.05, voltage) == pytest.approx(expected)


@pytest.mark.parametrize("voltage", [0.0, -1.0, -0.05])
def test_non_positive_voltage_has_no_result(voltage):
    assert max_capacitance(R_1NA, 1.0, voltage) is None


def test_unmapped_pair_has_no_result():
    assert max_capacitance(R_10PA, 0.03, 1.0) is None  # not published
    assert max_capacitance(1e-6, 1.0, 1.0) is None  # not a QSCV range
    assert max_capacitance(R_1NA, 0.7, 1.0) is None  # off the time grid


def test_float_noise_still_matches_the_time_grid():
    noisy = 0.1 + 0.2 - 0.2  # 0.10000000000000003
    assert noisy != T_100MS
    assert max_capacitance(R_1NA, noisy, 1.0) == pytest.approx(10**-9.244)


# ── supported_integration_times / nearest_supported_time ─────────────────────


def test_50hz_excludes_30ms():
    """CINT minimum is 2 PLC = 40 ms at 50 Hz, so 30 ms is unreachable."""
    times = supported_integration_times(R_1NA, 50)
    assert T_30MS not in times
    assert times == [T_2S, T_1S, T_500MS, T_300MS, T_100MS, T_50MS]


def test_60hz_excludes_both_2s_and_30ms():
    """IINT maximum is 100 PLC = 1.667 s at 60 Hz; CINT minimum is 33.3 ms."""
    times = supported_integration_times(R_1NA, 60)
    assert T_2S not in times
    assert T_30MS not in times
    assert times == [T_1S, T_500MS, T_300MS, T_100MS, T_50MS]


def test_low_range_offers_only_long_times():
    assert supported_integration_times(R_10PA, 50) == [
        T_2S,
        T_1S,
        T_500MS,
        T_300MS,
    ]
    assert supported_integration_times(R_100PA, 60) == [
        T_1S,
        T_500MS,
        T_300MS,
    ]


def test_unknown_range_offers_nothing():
    assert supported_integration_times(1e-6, 50) == []


def test_times_are_ordered_longest_first():
    for range_value in ALL_RANGES:
        times = supported_integration_times(range_value, 50)
        assert times == sorted(times, reverse=True)


def test_nearest_supported_time_snaps_on_a_log_scale():
    # 0.4 s sits between 300 ms and 500 ms; log-distance picks 500 ms.
    assert nearest_supported_time(0.4, R_1NA, 50) == T_500MS
    # An exact grid value is kept.
    assert nearest_supported_time(0.1, R_1NA, 50) == T_100MS
    # Below the grid ⇒ the shortest available time.
    assert nearest_supported_time(0.001, R_1NA, 50) == T_50MS
    # Above the grid ⇒ the longest available time.
    assert nearest_supported_time(500.0, R_1NA, 50) == T_2S


def test_nearest_supported_time_respects_the_range():
    """300 ms is the floor on the 10 pA range even when 50 ms is asked for."""
    assert nearest_supported_time(0.05, R_10PA, 50) == T_300MS


def test_nearest_supported_time_without_options():
    assert nearest_supported_time(1.0, 1e-6, 50) is None


def test_nearest_supported_time_with_non_positive_input():
    assert nearest_supported_time(0.0, R_1NA, 50) == T_2S


# ── Formatting ───────────────────────────────────────────────────────────────


def test_format_capacitance():
    assert format_capacitance(7.46e-9) == "7.46 nF"
    assert format_capacitance(1.23e-12) == "1.23 pF"
    assert format_capacitance(5e-15) == "5 fF"
    assert format_capacitance(2.5e-6) == "2.5 µF"


def test_format_capacitance_without_a_value():
    assert format_capacitance(None) == "—"
    assert format_capacitance(0.0) == "—"
    assert format_capacitance(float("nan")) == "—"


def test_format_integration_time():
    assert format_integration_time(2.0) == "2 s"
    assert format_integration_time(1.0) == "1 s"
    assert format_integration_time(0.5) == "500 ms"
    assert format_integration_time(0.03) == "30 ms"


# ── Referenced-Mode validation (models/qscv_config.py) ───────────────────────


def make_referenced_config(**overrides):
    cfg = QscvConfig()
    cfg.referenced_mode = True
    cfg.cap_integration_time = 0.1
    cfg.leak_integration_time = 0.1
    cfg.meas_range = R_1NA
    cfg.cap_name = "C"
    cfg.leak_name = "IL"
    cfg.display_vars = ["C", "IL"]
    cfg.var1.start = 0.0
    cfg.var1.stop = 1.0
    cfg.var1.step = 0.1
    cfg.var1.cstep = 0.05
    cfg.var1.compliance = 0.01
    for key, val in overrides.items():
        setattr(cfg, key, val)
    return cfg


def validate(cfg):
    return QscvConstraints.validate_config(
        cfg,
        active_channels=[],
        instrument_model="4156C",
        line_frequency_hz=50,
        enabled_smu_ids=["SMU2"],
    )


def test_referenced_mode_accepts_a_grid_time():
    errors = validate(make_referenced_config())
    assert not any("Referenced Mode" in e for e in errors)
    assert not any(e.startswith("QSCV Integration Time") for e in errors)


def test_referenced_mode_rejects_an_off_grid_time():
    cfg = make_referenced_config(
        cap_integration_time=0.7, leak_integration_time=0.7
    )
    errors = validate(cfg)
    assert any("manufacturer reference times" in e for e in errors)


def test_referenced_mode_rejects_a_time_the_range_does_not_publish():
    cfg = make_referenced_config(
        meas_range=R_10PA,
        cap_integration_time=0.05,
        leak_integration_time=0.05,
    )
    errors = validate(cfg)
    assert any("manufacturer reference times" in e for e in errors)


def test_referenced_mode_requires_equal_integration_times():
    cfg = make_referenced_config(leak_integration_time=0.5)
    errors = validate(cfg)
    assert any(
        "QSCV and Leak Integration Time must be equal" in e for e in errors
    )


def test_off_grid_time_is_fine_when_referenced_mode_is_off():
    cfg = make_referenced_config(
        referenced_mode=False,
        cap_integration_time=0.7,
        leak_integration_time=0.25,
    )
    errors = validate(cfg)
    assert not any("Referenced Mode" in e for e in errors)
    assert not any("manufacturer reference times" in e for e in errors)
