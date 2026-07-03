"""
Tests for models/integration_time.py — effective A/D integration time and the
per-sample time interval (Tables 7-22/7-23/7-24 of the 4155C/4156C manual,
HRSMU and MPSMU only).
"""

import pytest

from wizard_4155_4156.models.integration_time import (
    SHORT_TABLE_MIN,
    effective_integration_time,
    estimated_measurement_time_range,
    estimated_sample_time_range,
    possible_current_ranges,
    voltage_ranges_spanned,
)
from wizard_4155_4156.models.sweep_config import (
    RANGE_VALUES_HRSMU_CURRENT,
    RANGE_VALUES_MPSMU_CURRENT,
    IntegrationMode,
    MeasurementSetup,
)

_HRSMU_RANGES = [val for _label, val in RANGE_VALUES_HRSMU_CURRENT]
_MPSMU_RANGES = [val for _label, val in RANGE_VALUES_MPSMU_CURRENT]

ST = 1e-3  # SHORT aperture inside the Table 7-24 window (0.96–1.92 ms)
PLC50 = 0.02  # 1 PLC at 50 Hz


def eff(mode, *, measures_current, short_time=ST, long_cycles=50, freq=50,
        current_range=None, voltage_range=None, is_4156=False):
    return effective_integration_time(
        integration_mode=mode,
        short_time=short_time,
        long_cycles=long_cycles,
        line_frequency_hz=freq,
        measures_current=measures_current,
        current_range=current_range,
        voltage_range=voltage_range,
        is_4156=is_4156,
    )


# ── Voltage measurements (no range dependence) ───────────────────────────────


def test_voltage_short_is_raw_aperture():
    assert eff(
        IntegrationMode.SHORT, measures_current=False, short_time=1.2e-3
    ) == pytest.approx(1.2e-3)


def test_voltage_medium_is_two_plc():
    assert eff(
        IntegrationMode.MED, measures_current=False, freq=50
    ) == pytest.approx(0.04)
    assert eff(
        IntegrationMode.MED, measures_current=False, freq=60
    ) == pytest.approx(2.0 / 60)


def test_voltage_long_is_twice_the_setting():
    assert eff(
        IntegrationMode.LONG, measures_current=False, long_cycles=50, freq=50
    ) == pytest.approx(2.0)
    assert eff(
        IntegrationMode.LONG, measures_current=False, long_cycles=10, freq=60
    ) == pytest.approx(2 * 10 / 60)


# ── Current, SHORT mode (Table 7-24, aperture in window) ─────────────────────


@pytest.mark.parametrize(
    ("current_range", "voltage_range", "expected"),
    [
        (10e-12, 2.0, 10 * PLC50),   # 10 pA → 10 PLC
        (100e-12, 2.0, 2 * PLC50),   # 100 pA → 2 PLC
        (1e-9, 2.0, 1 * PLC50),      # 1 nA → 1 PLC
        (10e-9, 2.0, 4 * ST),        # 10 nA → ×4
        (100e-9, 20.0, 2 * ST),      # 100 nA @≤20 V → ×2
        (100e-9, 40.0, 4 * ST),      # 100 nA @40/100 V → ×4
        (1e-6, 100.0, 1 * ST),       # 1 µA → ×1
        (10e-6, 2.0, 1 * ST),        # 10 µA @2 V → ×1
        (10e-6, 20.0, 2 * ST),       # 10 µA @≥20 V → ×2
        (100e-6, 100.0, 1 * ST),     # 100 µA → ×1
        (100e-3, 100.0, 1 * ST),     # 100 mA → ×1
    ],
)
def test_short_current_hrsmu(current_range, voltage_range, expected):
    assert eff(
        IntegrationMode.SHORT, measures_current=True, short_time=ST,
        current_range=current_range, voltage_range=voltage_range,
        is_4156=True,
    ) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("current_range", "voltage_range", "expected"),
    [
        (1e-9, 40.0, 1 * ST),    # 1 nA @≤40 V → ×1
        (1e-9, 100.0, 2 * ST),   # 1 nA @100 V → ×2
        (10e-9, 2.0, 1 * ST),    # 10 nA → ×1
        (100e-9, 20.0, 1 * ST),  # 100 nA @≤20 V → ×1
        (100e-9, 40.0, 2 * ST),  # 100 nA @40 V → ×2
        (100e-9, 100.0, 4 * ST),  # 100 nA @100 V → ×4
        (1e-6, 100.0, 1 * ST),   # 1 µA → ×1
        (10e-6, 20.0, 1 * ST),   # 10 µA @≤20 V → ×1
        (10e-6, 40.0, 2 * ST),   # 10 µA @40 V → ×2
        (10e-6, 100.0, 3 * ST),  # 10 µA @100 V → ×3
        (100e-3, 100.0, 1 * ST),  # 100 mA → ×1
    ],
)
def test_short_current_mpsmu(current_range, voltage_range, expected):
    assert eff(
        IntegrationMode.SHORT, measures_current=True, short_time=ST,
        current_range=current_range, voltage_range=voltage_range,
        is_4156=False,
    ) == pytest.approx(expected)


def test_short_current_below_table_uses_raw_aperture():
    # Below 0.96 ms the per-range factors do not apply — raw aperture only.
    assert SHORT_TABLE_MIN == pytest.approx(0.96e-3)
    for r in (10e-12, 1e-6, 100e-3):
        assert eff(
            IntegrationMode.SHORT, measures_current=True, short_time=5e-4,
            current_range=r, voltage_range=100.0, is_4156=True,
        ) == pytest.approx(5e-4)


# ── Current, MEDIUM mode (Table 7-23; ×2 ADC-Zero only ≥ 10 nA) ──────────────


@pytest.mark.parametrize(
    ("is_4156", "current_range", "expected"),
    [
        (True, 10e-12, 50 * PLC50),      # < 10 nA → no ADC-Zero doubling
        (True, 100e-12, 10 * PLC50),     # < 10 nA → no doubling
        (True, 1e-9, 5 * PLC50),         # < 10 nA → no doubling
        (True, 10e-9, 1 * 2 * PLC50),    # ≥ 10 nA → ×2
        (True, 100e-3, 1 * 2 * PLC50),   # ≥ 10 nA → ×2
        (False, 1e-9, 3 * PLC50),        # MPSMU < 10 nA → no doubling
        (False, 10e-9, 1 * 2 * PLC50),   # ≥ 10 nA → ×2
        (False, 100e-3, 1 * 2 * PLC50),  # ≥ 10 nA → ×2
    ],
)
def test_medium_current(is_4156, current_range, expected):
    assert eff(
        IntegrationMode.MED, measures_current=True,
        current_range=current_range, is_4156=is_4156, freq=50,
    ) == pytest.approx(expected)


# ── Current, LONG mode (Table 7-22, cap 100 PLC; ×2 ADC-Zero only ≥ 10 nA) ───


@pytest.mark.parametrize(
    ("is_4156", "current_range", "long_cycles", "expected"),
    [
        (True, 10e-12, 5, 100 * PLC50),    # always 100 PLC, no doubling
        (True, 100e-12, 5, 50 * PLC50),    # min(5×10, 100) = 50, no doubling
        (True, 100e-12, 20, 100 * PLC50),  # min(20×10, 100) = 100, no doubling
        (True, 1e-9, 5, 25 * PLC50),       # min(5×5, 100) = 25, no doubling
        (True, 10e-9, 50, 50 * 2 * PLC50),  # ≥ 10 nA → setting value ×2
        (False, 1e-9, 30, 30 * PLC50),     # MPSMU < 10 nA → no doubling
        (False, 100e-3, 30, 30 * 2 * PLC50),  # ≥ 10 nA → ×2
    ],
)
def test_long_current(is_4156, current_range, long_cycles, expected):
    assert eff(
        IntegrationMode.LONG, measures_current=True,
        current_range=current_range, long_cycles=long_cycles,
        is_4156=is_4156, freq=50,
    ) == pytest.approx(expected)


@pytest.mark.parametrize("mode", [IntegrationMode.MED, IntegrationMode.LONG])
def test_adc_zero_boundary_at_10na(mode):
    # ADC-Zero doubles the current integration time only on the 10 nA range or
    # greater: 1 nA is NOT doubled, 10 nA IS (HRSMU, base 1 PLC ≥ 10 nA).
    def t(current_range):
        return eff(
            mode, measures_current=True, current_range=current_range,
            long_cycles=1, is_4156=True, freq=50,
        )

    # HRSMU: 1 nA base = 5 PLC (MED) / min(1×5,100)=5 PLC (LONG); no doubling.
    assert t(1e-9) == pytest.approx(5 * PLC50)
    # 10 nA base = 1 PLC, doubled by ADC-Zero.
    assert t(10e-9) == pytest.approx(1 * 2 * PLC50)


# ── possible_current_ranges ──────────────────────────────────────────────────


def test_possible_ranges_auto_full_set():
    assert possible_current_ranges({"mode": "AUTO"}, True) == _HRSMU_RANGES
    assert possible_current_ranges({"mode": "AUTO"}, False) == _MPSMU_RANGES


def test_possible_ranges_lim_subset():
    limit = 1e-9
    ranges = possible_current_ranges({"mode": "LIM", "value": limit}, True)
    assert ranges == [r for r in _HRSMU_RANGES if r >= limit]
    assert min(ranges) == pytest.approx(limit)  # 10 pA / 100 pA excluded


def test_possible_ranges_fix_single():
    value = 1e-6
    assert possible_current_ranges({"mode": "FIX", "value": value}, True) == [
        value
    ]


def test_possible_ranges_missing_value_falls_back_to_auto():
    assert possible_current_ranges({"mode": "FIX"}, True) == _HRSMU_RANGES


# ── estimated_sample_time_range ──────────────────────────────────────────────


def _ms(mode=IntegrationMode.MED, short_time=ST, long_cycles=50, ranges=None):
    return MeasurementSetup(
        integration_mode=mode,
        short_time=short_time,
        long_time_cycles=long_cycles,
        ranges=ranges or {},
    )


def _smu(idx=1, mode="V"):
    return {
        "id": f"SMU{idx}",
        "unit_type": "SMU",
        "mode": mode,
        "v_name": f"V{idx}",
        "i_name": f"I{idx}",
    }


def _vmu(idx=1, mode="V"):
    return {
        "id": f"VMU{idx}",
        "unit_type": "VMU",
        "mode": mode,
        "v_name": f"VMU{idx}",
        "i_name": "",
    }


def test_auto_current_yields_interval():
    ms = _ms(ranges={"SMU1": {"mode": "AUTO"}})
    lo, hi = estimated_sample_time_range(
        ms, [_smu(mode="V")], ["I1"], {"SMU1": {"source": 0.0}}, "4155C", 50
    )
    assert lo == pytest.approx(0.04)  # ≥ 10 nA ranges: 1 PLC × 2
    assert hi == pytest.approx(0.06)  # MPSMU 1 nA: 3 PLC (no ADC-Zero < 10 nA)
    assert hi > lo


def test_fixed_current_collapses_to_single_value():
    ms = _ms(ranges={"SMU1": {"mode": "FIX", "value": 10e-3}})
    lo, hi = estimated_sample_time_range(
        ms, [_smu(mode="V")], ["I1"], {"SMU1": {"source": 0.0}}, "4155C", 50
    )
    assert lo == hi == pytest.approx(0.04)


def test_voltage_measurement_has_no_range_spread():
    # SMU in I mode measures voltage → single value even with AUTO range.
    ms = _ms(ranges={"SMU1": {"mode": "AUTO"}})
    lo, hi = estimated_sample_time_range(
        ms, [_smu(mode="I")], ["V1"], {"SMU1": {"source": 0.0}}, "4156C", 50
    )
    assert lo == hi == pytest.approx(0.04)  # MED voltage = 2·plc


def test_dvol_vmu_counts_twice():
    ms = _ms()
    lo, hi = estimated_sample_time_range(
        ms, [_vmu(mode="DVOLT")], ["VMU1"], {}, "4156C", 50
    )
    assert lo == hi == pytest.approx(0.08)  # (2·plc) × 2 (dvol)


def test_output_voltage_range_from_source_magnitude():
    # HRSMU 100 nA fixed range. Source 10 V → 20 V range (×2);
    # source 30 V → 40 V range (×4).
    ms = _ms(
        mode=IntegrationMode.SHORT,
        short_time=ST,
        ranges={"SMU1": {"mode": "FIX", "value": 100e-9}},
    )
    lo20, hi20 = estimated_sample_time_range(
        ms, [_smu(mode="V")], ["I1"], {"SMU1": {"source": 10.0}}, "4156C", 50
    )
    lo40, hi40 = estimated_sample_time_range(
        ms, [_smu(mode="V")], ["I1"], {"SMU1": {"source": 30.0}}, "4156C", 50
    )
    assert lo20 == hi20 == pytest.approx(2 * ST)
    assert lo40 == hi40 == pytest.approx(4 * ST)


def test_comm_smu_measures_current_at_smallest_voltage_range():
    # COMM has no constant entry → 0 V → 2 V range; HRSMU 100 nA @2 V → ×2.
    ms = _ms(
        mode=IntegrationMode.SHORT,
        short_time=ST,
        ranges={"SMU1": {"mode": "FIX", "value": 100e-9}},
    )
    lo, hi = estimated_sample_time_range(
        ms, [_smu(mode="COMM")], ["I1"], {}, "4156C", 50
    )
    assert lo == hi == pytest.approx(2 * ST)


def test_unselected_variable_is_ignored():
    ms = _ms(ranges={"SMU1": {"mode": "AUTO"}})
    result = estimated_sample_time_range(
        ms, [_smu(mode="V")], ["@TIME"], {"SMU1": {"source": 0.0}}, "4155C", 50
    )
    assert result == (0.0, 0.0)


# ── voltage_ranges_spanned ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("min_mag", "max_mag", "expected"),
    [
        (0.0, 1.0, [2.0]),  # inside the 2 V range
        (0.0, 5.0, [2.0, 20.0]),  # spans up to 20 V
        (0.0, 30.0, [2.0, 20.0, 40.0]),  # up to 40 V
        (0.0, 100.0, [2.0, 20.0, 40.0, 100.0]),  # full set
        (3.0, 3.0, [20.0]),  # single point in the 20 V range
        (150.0, 200.0, [100.0]),  # above all ranges → clamp to 100 V
    ],
)
def test_voltage_ranges_spanned(min_mag, max_mag, expected):
    assert voltage_ranges_spanned(min_mag, max_mag) == expected


# ── estimated_measurement_time_range (voltage-range set) ─────────────────────


def test_measurement_range_spans_multiple_voltage_ranges():
    # HRSMU 100 nA SHORT: ×2 at 20 V, ×4 at 40 V. A sweep touching both ranges
    # widens the interval; a single voltage range collapses it.
    ms = _ms(
        mode=IntegrationMode.SHORT,
        short_time=ST,
        ranges={"SMU1": {"mode": "FIX", "value": 100e-9}},
    )
    channels = [_smu(mode="V")]
    lo2, hi2 = estimated_measurement_time_range(
        ms, channels, ["I1"], {"SMU1": [20.0]}, True, 50
    )
    assert lo2 == hi2 == pytest.approx(2 * ST)

    lo, hi = estimated_measurement_time_range(
        ms, channels, ["I1"], {"SMU1": [20.0, 40.0]}, True, 50
    )
    assert lo == pytest.approx(2 * ST)
    assert hi == pytest.approx(4 * ST)


def test_measurement_voltage_unit_ignores_voltage_ranges():
    # An I-mode SMU measures voltage → no dependence on the voltage-range set.
    ms = _ms(ranges={"SMU1": {"mode": "AUTO"}})
    lo, hi = estimated_measurement_time_range(
        ms, [_smu(mode="I")], ["V1"], {}, True, 50
    )
    assert lo == hi == pytest.approx(2 * PLC50)  # MED voltage
