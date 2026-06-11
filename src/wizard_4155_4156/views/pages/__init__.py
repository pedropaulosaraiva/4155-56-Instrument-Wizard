"""
views/pages/__init__.py
-----------------------
Public surface of the pages sub-package.

Defines
-------
Page      — IntEnum of canonical page identifiers.
BasePage  — Minimal QWidget contract all page classes must satisfy.

Re-exports all concrete page classes so the rest of the codebase
uses a single, stable import path:

    from wizard_4155_4156.views.pages import (
        Page,
        BasePage,
        HomePageView,
        ChannelsPageView,
        SweepConfigPageView,
        SamplingConfigPageView,
        MeasurementsPageView,
        GraphPage,
        TablePageView,
    )

Architectural rules enforced here
----------------------------------
1. Page values are stable identifiers only — navigation resolves
   widgets through MainWindow's page registry (setCurrentWidget),
   NOT through QStackedWidget indices.  Page.MEASURE_CONFIG is a
   dynamic slot: its widget is generated lazily by
   MeasureConfigFactory from the Channels page and may be absent.
2. BasePage.on_activate() is the only lifecycle hook the
   navigation system calls — pages must not rely on any other
   external trigger to refresh their state.
3. New pages: add a Page member, create the module under pages/,
   import it here, and add it to __all__.  No other file changes
   are required by the architecture.
"""

from enum import IntEnum

from PySide6.QtWidgets import QWidget

# ---------------------------------------------------------------------------
# Page registry
# ---------------------------------------------------------------------------


class Page(IntEnum):
    """
    Canonical identifiers for every top-level application page.

    Values are stable ids (also used as QButtonGroup ids in the nav
    bar) — they are NOT QStackedWidget indices.  MainWindow resolves
    each Page to its widget through its page registry and navigates
    with setCurrentWidget().

    MEASURE_CONFIG is the dynamic measurement-configuration slot:
    its widget (sweep or sampling page) is generated lazily by the
    Channels page "Configure Measure" button.
    """

    HOME = 0
    CHANNELS = 1
    MEASURE_CONFIG = 2
    MEASUREMENTS = 3
    GRAPH = 4
    TABLE = 5


# ---------------------------------------------------------------------------
# Base contract
# ---------------------------------------------------------------------------


class BasePage(QWidget):
    """
    Minimal interface that every page widget must satisfy.

    Subclasses
    ----------
    - Must call ``super().__init__(parent)`` before any Qt setup.
    - Should override ``on_activate()`` if they need to refresh data
      or trigger deferred initialisation when becoming visible.
    - Must never import from presenters or models directly;
      all external data arrives through signals connected by MainWindow
      or the page's own presenter.
    """

    def on_activate(self) -> None:
        """
        Called by MainWindow._navigate_to() each time this page is
        brought into view.  Default implementation is a no-op so
        stub pages don't need to override it.
        """


# ---------------------------------------------------------------------------
# Concrete page re-exports
# ---------------------------------------------------------------------------
# Imported after Page and BasePage are defined to avoid circular imports
# (the modules below import BasePage from this file).

from wizard_4155_4156.views.pages.channels_page import (  # noqa: E402
    ChannelsPageView,
)
from wizard_4155_4156.views.pages.home_page import HomePageView  # noqa: E402
from wizard_4155_4156.views.pages.measurements_page import (  # noqa: E402
    MeasurementsPageView,
)
from wizard_4155_4156.views.pages.sampling_config_page import (  # noqa: E402
    SamplingConfigPageView,
)
from wizard_4155_4156.views.pages.stub_pages import GraphPage  # noqa: E402
from wizard_4155_4156.views.pages.sweep_config_page import (  # noqa: E402
    SweepConfigPageView,
)
from wizard_4155_4156.views.pages.table_page import TablePageView  # noqa: E402

# ---------------------------------------------------------------------------
# Explicit public API
# ---------------------------------------------------------------------------

__all__ = [
    # Primitives
    "Page",
    "BasePage",
    # Concrete pages
    "HomePageView",
    "ChannelsPageView",
    "SweepConfigPageView",
    "SamplingConfigPageView",
    "MeasurementsPageView",
    "GraphPage",
    "TablePageView",
]
