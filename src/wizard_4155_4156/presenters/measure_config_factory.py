"""
presenters/measure_config_factory.py
------------------------------------
Lazy factory for the dynamic measurement-configuration page.

Lifecycle contract
------------------
- No configuration page exists at application startup.
- Each "Configure Measure" click on the Channels page calls generate():
  the previous page/presenter pair is discarded and a fresh pair is
  built from a STATIC deep-copied ChannelsConfig snapshot taken at that
  moment.  Generated objects never hold a reference to the
  ChannelsPresenter — later edits on the channels page do not leak in.
- The factory deletes the old presenter itself; the old page widget is
  handed back to MainWindow (which owns the QStackedWidget) so it can
  be removed from the stack BEFORE deleteLater() is called on it.

MeasurementsPresenter consumes the active configuration through the
duck-typed get_json() (same ValueError contract as the presenters).
"""

from __future__ import annotations

from PySide6.QtCore import QObject

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText,
    tr_ui,
)
from wizard_4155_4156.models.channels import MeasurementMode
from wizard_4155_4156.presenters.qscv_config_presenter import (
    QscvConfigPresenter,
)
from wizard_4155_4156.presenters.sampling_config_presenter import (
    SamplingConfigPresenter,
)
from wizard_4155_4156.presenters.sweep_config_presenter import (
    SweepConfigPresenter,
)
from wizard_4155_4156.views.pages import (
    BasePage,
    QscvConfigPageView,
    SamplingConfigPageView,
    SweepConfigPageView,
)


class MeasureConfigFactory(QObject):
    """
    Owns the lifecycle of the dynamic measurement-config page/presenter.

    Holds the ChannelsPresenter ONLY to take deep-copied snapshots at
    generation time (get_config() already returns a deepcopy).
    """

    def __init__(
        self,
        channels_presenter,  # ChannelsPresenter — loose type, no cycle
        settings_provider=None,  # GlobalSettingsManager — for QSCV line freq
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._channels_presenter = channels_presenter
        self._settings_provider = settings_provider
        self._page: BasePage | None = None
        self._presenter: QObject | None = None

    def _line_frequency(self) -> int:
        """Current AC line frequency (Hz) from global settings; default 50."""
        if self._settings_provider is not None:
            try:
                return self._settings_provider.get().line_frequency_hz
            except Exception:  # noqa: BLE001
                return 50
        return 50

    # ── Public API ─────────────────────────────────────────────────────────

    def current_page(self) -> BasePage | None:
        return self._page

    def get_active_presenter(self) -> QObject | None:
        return self._presenter

    def get_json(self) -> dict:
        """
        JSON of the currently generated configuration.

        Raises ValueError when no page has been generated yet or when
        the active presenter's validation fails (same contract as the
        sweep/sampling presenters).
        """
        if self._presenter is None:
            raise ValueError(tr_ui(CommandWizardText.MEAS_NO_CONFIG))
        return self._presenter.get_json()

    def get_instrument_model(self) -> str:
        """
        Instrument model of the channels snapshot behind the active page.

        A saved setup records the instrument *defined on the Channels page*,
        not a global default.  Raises ValueError when no page is generated yet.
        """
        if self._presenter is None:
            raise ValueError(tr_ui(CommandWizardText.MEAS_NO_CONFIG))
        return self._presenter.get_instrument_model()

    def generate(self) -> BasePage | None:
        """
        Build a fresh page/presenter pair for the measurement mode
        currently selected on the Channels page.

        Returns the new page widget, or None for unsupported modes
        (QSCV).  The PREVIOUS page widget is not deleted here — the
        caller must have removed it from the stack and called
        deleteLater() on it before invoking generate() (see
        MainWindow._on_measure_configured); the previous presenter is
        deleted here.
        """
        snapshot = self._channels_presenter.get_config()  # deepcopy

        # Discard the previous presenter; its page is handled by the
        # caller (removed from the stack before deletion).
        if self._presenter is not None:
            self._presenter.deleteLater()
        self._presenter = None
        self._page = None

        mode = snapshot.measurement_mode
        if mode == MeasurementMode.SWEEP:
            page = SweepConfigPageView()
            self._presenter = SweepConfigPresenter(
                view=page, channels_snapshot=snapshot, parent=self
            )
        elif mode == MeasurementMode.SAMPLING:
            page = SamplingConfigPageView()
            self._presenter = SamplingConfigPresenter(
                view=page, channels_snapshot=snapshot, parent=self
            )
        elif mode == MeasurementMode.QSCV:
            page = QscvConfigPageView()
            self._presenter = QscvConfigPresenter(
                view=page,
                channels_snapshot=snapshot,
                line_frequency_hz=self._line_frequency(),
                parent=self,
            )
        else:
            return None

        self._page = page
        return page

    def generate_from_setup(
        self, channels_config, setup_dict: dict
    ) -> BasePage | None:
        """
        Build a fresh config page for a *saved* setup (the "Copy to measurement
        configuration" action).

        ``channels_config`` is a ChannelsConfig reconstructed from the setup and
        ``setup_dict`` is the setup's canonical config dict; the new presenter
        preloads its parameters.  Like ``generate``, the caller must have
        removed/deleted the previous page first.  Returns None for unsupported
        modes (QSCV).
        """
        if self._presenter is not None:
            self._presenter.deleteLater()
        self._presenter = None
        self._page = None

        mode = channels_config.measurement_mode
        if mode == MeasurementMode.SWEEP:
            page = SweepConfigPageView()
            self._presenter = SweepConfigPresenter(
                view=page,
                channels_snapshot=channels_config,
                parent=self,
                initial_setup=setup_dict,
            )
        elif mode == MeasurementMode.SAMPLING:
            page = SamplingConfigPageView()
            self._presenter = SamplingConfigPresenter(
                view=page,
                channels_snapshot=channels_config,
                parent=self,
                initial_setup=setup_dict,
            )
        elif mode == MeasurementMode.QSCV:
            page = QscvConfigPageView()
            self._presenter = QscvConfigPresenter(
                view=page,
                channels_snapshot=channels_config,
                line_frequency_hz=self._line_frequency(),
                parent=self,
                initial_setup=setup_dict,
            )
        else:
            return None

        self._page = page
        return page
