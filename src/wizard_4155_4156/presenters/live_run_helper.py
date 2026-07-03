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


class LiveMeasurementRunner:
    """Builds and triggers Setup(+Run+Fetch) for a live config dict."""

    def __init__(self, connector_presenter) -> None:
        self._connector = connector_presenter
        self._setup_director = MeasurementSetupDirector()
        self._run_director = MeasurementRunDirector()

    def apply_setup(self, config: dict) -> None:
        """Send instrument configuration only — no measurement execution."""
        setup_cmds = self._setup_director.build_full_setup(config)
        self._connector.trigger_setup_only(setup_cmds)

    def apply_run_fetch(self, config: dict) -> None:
        """Full ephemeral cycle: Setup → Run → Fetch (data not persisted)."""
        setup_cmds = self._setup_director.build_full_setup(config)
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
