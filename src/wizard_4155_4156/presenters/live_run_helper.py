"""
presenters/live_run_helper.py
-----------------------------
Ephemeral "quick" measurement runner shared by the three config presenters
(Sweep / Sampling / QSCV).

Given a live config dict, it builds the SCPI command lists with the setup / run
directors and delegates hardware I/O to the ConnectorPresenter, which owns the
single-thread GPIB pool.  Fetched data flows back through the connector's
``data_ready`` signal (cached and shown by the Table page) — nothing is
persisted here, mirroring the retired Measurements & Run page.

The two directors are stateless builders, so a single runner instance is reused
across every apply/run request on a page.
"""

from __future__ import annotations

from typing import Optional

from wizard_4155_4156.SCPI.measurement_run_director import (
    MeasurementRunDirector,
)
from wizard_4155_4156.SCPI.measurement_setup_director import (
    MeasurementSetupDirector,
)

# Defaults for fetching trace data (see MeasureRunCommandBuilder literals).
_FETCH_FORMAT = "REAL"
_FETCH_LENGTH = 64
_FETCH_BORDER = "NORM"

class _QuickMismatchState:
    """Session-scoped suppression of the quick-run mismatch warning.

    Deliberately INDEPENDENT of the Runs page's own
    ``_suppress_instrument_mismatch``: the Runs page and the quick apply/run
    actions are two different execution paths, each with its own opt-out.
    Module level (not per presenter) because
    MeasureConfigFactory destroys and rebuilds the config presenters every time
    a measurement-config page is generated.
    """

    suppressed = False


def reset_quick_mismatch_suppression() -> None:
    """Re-arm the quick-run mismatch warning (test hook)."""
    _QuickMismatchState.suppressed = False


def confirm_quick_instrument_match(
    view,  # config page view — provides confirm_instrument_mismatch()
    setup_model: str,
    connected_model: Optional[str],
) -> bool:
    """Warn once per session before a quick apply/run on a foreign model.

    Returns True to proceed.  No prompt when suppressed, when disconnected, or
    when the connected model matches the model the config was built for.
    """
    if _QuickMismatchState.suppressed:
        return True
    if (
        not connected_model
        or not setup_model
        or setup_model == connected_model
    ):
        return True
    proceed, dont_ask = view.confirm_instrument_mismatch(
        setup_model, connected_model
    )
    if proceed and dont_ask:
        _QuickMismatchState.suppressed = True
    return proceed


class LiveMeasurementRunner:
    """Builds and triggers Setup(+Run+Fetch) for a live config dict."""

    def __init__(self, connector_presenter, settings_provider=None) -> None:
        self._connector = connector_presenter
        # GlobalSettingsManager — read at call time so the advanced-option
        # reset/calibration toggles take effect on the next apply/run without
        # regenerating the page.  None in isolated tests ⇒ today's behavior.
        self._settings_provider = settings_provider
        self._setup_director = MeasurementSetupDirector()
        self._run_director = MeasurementRunDirector()

    def _reset_flags(self) -> tuple[bool, bool]:
        """(skip_reset, keep_auto_calibration) from global settings."""
        if self._settings_provider is not None:
            try:
                s = self._settings_provider.get()
                return bool(s.skip_reset), bool(s.keep_auto_calibration)
            except Exception:  # noqa: BLE001
                return False, False
        return False, False

    def apply_setup(self, config: dict) -> None:
        """Send instrument configuration only — no measurement execution."""
        skip_reset, keep_auto_cal = self._reset_flags()
        setup_cmds = self._setup_director.build_full_setup(
            config,
            skip_reset=skip_reset,
            keep_auto_calibration=keep_auto_cal,
        )
        self._connector.trigger_setup_only(setup_cmds)

    def apply_run_fetch(self, config: dict) -> None:
        """Full ephemeral cycle: Setup → Run → Fetch (data not persisted)."""
        skip_reset, keep_auto_cal = self._reset_flags()
        setup_cmds = self._setup_director.build_full_setup(
            config,
            skip_reset=skip_reset,
            keep_auto_calibration=keep_auto_cal,
        )
        run_cmds = self._run_director.run_measurement({"standby": "OFF"})
        fetch_cmds = self._run_director.take_data(self._fetch_config(config))
        self._connector.trigger_full_sequence(setup_cmds, run_cmds, fetch_cmds)

    @staticmethod
    def _fetch_config(config: dict) -> dict:
        return {
            "format": _FETCH_FORMAT,
            "length": _FETCH_LENGTH,
            "border": _FETCH_BORDER,
            "variables": config.get("display_vars", []),
        }
