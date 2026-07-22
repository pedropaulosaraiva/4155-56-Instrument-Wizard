"""
gui_text/documentation.py
-------------------------
In-app documentation content, defined as plain Python data (no Qt imports).

Each user-facing section header / page in the application maps to a
``DocTopic``.  The Documentation window renders ``DOC_TREE`` as a collapsible
navigation tree and shows the Markdown ``body`` of the selected topic in a
``QTextBrowser`` (via ``setMarkdown``).

Markdown page bodies live in the ``documentation_pages`` submodule — one module
per page (each exposing a ``BODY`` string) so very large pages stay out of
this logic module.  ``DOC_BODIES`` maps each ``DocTopic`` to its body; topics
without an entry fall back to ``PLACEHOLDER_MD``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wizard_4155_4156.gui_text import documentation_pages as pages


class DocTopic(StrEnum):
    """Stable key for every documentation page.

    The value is what travels over the documentation event bus and what gets
    reconstructed with ``DocTopic(value)`` on the receiving side.
    """

    # ── Channels ─────────────────────────────────────────────────────────────
    CHANNELS_OVERVIEW = "channels.overview"
    CHANNELS_INSTRUMENT_MODEL = "channels.instrument_model"
    CHANNELS_MEASUREMENT_MODE = "channels.measurement_mode"
    CHANNELS_SMU = "channels.smu"
    CHANNELS_VMU = "channels.vmu"
    CHANNELS_VSU = "channels.vsu"
    CHANNELS_FLOATING = "channels.floating_measurements"
    CHANNELS_INTERLOCK = "channels.interlock"

    # ── Shared between Sweep and Sampling ────────────────────────────────────
    CHANNEL_ASSIGNMENTS = "shared.channel_assignments"
    MEASUREMENT_SETUP = "shared.measurement_setup"
    MEASUREMENT_RANGES = "shared.measurement_ranges"
    CONSTANT_SOURCES = "shared.constant_sources"
    DISPLAY_VARIABLES = "shared.display_variables"

    # ── Sweep Mode ───────────────────────────────────────────────────────────
    SWEEP_OVERVIEW = "sweep.overview"
    SWEEP_TIMING = "sweep.timing"
    SWEEP_VAR1 = "sweep.var1"
    SWEEP_VAR2 = "sweep.var2"
    SWEEP_VARD = "sweep.vard"
    SWEEP_PULSE = "sweep.pulse"

    # ── Sampling Mode ────────────────────────────────────────────────────────
    SAMPLING_OVERVIEW = "sampling.overview"
    SAMPLING_PARAMETERS = "sampling.parameters"
    STOP_CONDITION = "sampling.stop_condition"

    # ── QSCV Mode ────────────────────────────────────────────────────────────
    QSCV_OVERVIEW = "qscv.overview"
    QSCV_USER_FUNCTIONS = "qscv.user_functions"
    QSCV_MEASURE_SETUP = "qscv.measure_setup"
    QSCV_TIMING = "qscv.timing"
    QSCV_VAR1 = "qscv.var1"

    # ── Setup Status (shared by every measurement-config mode) ───────────────
    STATUS_OVERVIEW = "status.overview"
    STATUS_CRITICAL = "status.critical"
    STATUS_WARNING = "status.warning"
    STATUS_INFO = "status.info"


@dataclass(frozen=True)
class DocPage:
    """A single rendered documentation page."""

    title: str
    body: str  # Markdown


@dataclass(frozen=True)
class DocNode:
    """A leaf entry in the navigation tree."""

    label: str
    topic: DocTopic


@dataclass(frozen=True)
class DocSection:
    """A top-level navigation section with its own landing page + children."""

    label: str
    topic: DocTopic
    children: tuple[DocNode, ...]


# ── Page titles ──────────────────────────────────────────────────────────────
# Human-readable H1/window title for every topic (used by placeholders too).

DOC_TITLES: dict[DocTopic, str] = {
    DocTopic.CHANNELS_OVERVIEW: "Channels",
    DocTopic.CHANNELS_INSTRUMENT_MODEL: "Instrument Model",
    DocTopic.CHANNELS_MEASUREMENT_MODE: "Measurement Mode",
    DocTopic.CHANNELS_SMU: "Source Monitor Units (SMU)",
    DocTopic.CHANNELS_VMU: "Voltage Monitor Units (VMU)",
    DocTopic.CHANNELS_VSU: "Voltage Source Units (VSU)",
    DocTopic.CHANNELS_FLOATING: "Floating Measurements",
    DocTopic.CHANNELS_INTERLOCK: "Interlock Terminal",
    DocTopic.CHANNEL_ASSIGNMENTS: "Channel Assignments",
    DocTopic.MEASUREMENT_SETUP: "Measurement Setup",
    DocTopic.MEASUREMENT_RANGES: "Measurement Ranges",
    DocTopic.CONSTANT_SOURCES: "Constant Sources",
    DocTopic.DISPLAY_VARIABLES: "Display Variables",
    DocTopic.SWEEP_OVERVIEW: "Sweep Mode",
    DocTopic.SWEEP_TIMING: "Sweep Timing",
    DocTopic.SWEEP_VAR1: "VAR1 — Basic Sweep",
    DocTopic.SWEEP_VAR2: "VAR2 — Subordinate Sweep",
    DocTopic.SWEEP_VARD: "VARD — Synchronous Sweep",
    DocTopic.SWEEP_PULSE: "PULSE — Pulse Source",
    DocTopic.SAMPLING_OVERVIEW: "Sampling Mode",
    DocTopic.SAMPLING_PARAMETERS: "Sampling Parameters",
    DocTopic.STOP_CONDITION: "Stop Condition",
    DocTopic.QSCV_OVERVIEW: "QSCV Mode",
    DocTopic.QSCV_USER_FUNCTIONS: "User Functions",
    DocTopic.QSCV_MEASURE_SETUP: "QSCV Measure Setup",
    DocTopic.QSCV_TIMING: "QSCV Timing",
    DocTopic.QSCV_VAR1: "VAR1 — Voltage Sweep",
    DocTopic.STATUS_OVERVIEW: "Setup Status",
    DocTopic.STATUS_CRITICAL: "Critical Notifications",
    DocTopic.STATUS_WARNING: "Warnings",
    DocTopic.STATUS_INFO: "Information",
}


# ── Navigation tree ──────────────────────────────────────────────────────────
# Shared topics (e.g. MEASUREMENT_RANGES) intentionally appear under both the
# Sweep and Sampling sections — the same DocTopic key drives one shared page.

_SHARED_CHILDREN: tuple[DocNode, ...] = (
    DocNode("Channel Assignments", DocTopic.CHANNEL_ASSIGNMENTS),
    DocNode("Measurement Setup", DocTopic.MEASUREMENT_SETUP),
    DocNode("Measurement Ranges", DocTopic.MEASUREMENT_RANGES),
    DocNode("Constant Sources", DocTopic.CONSTANT_SOURCES),
    DocNode("Display Variables", DocTopic.DISPLAY_VARIABLES),
)

DOC_TREE: tuple[DocSection, ...] = (
    DocSection(
        "Channels",
        DocTopic.CHANNELS_OVERVIEW,
        (
            DocNode("Instrument Model", DocTopic.CHANNELS_INSTRUMENT_MODEL),
            DocNode("Measurement Mode", DocTopic.CHANNELS_MEASUREMENT_MODE),
            DocNode("Source Monitor Units (SMU)", DocTopic.CHANNELS_SMU),
            DocNode("Voltage Monitor Units (VMU)", DocTopic.CHANNELS_VMU),
            DocNode("Voltage Source Units (VSU)", DocTopic.CHANNELS_VSU),
            DocNode("Floating Measurements", DocTopic.CHANNELS_FLOATING),
            DocNode("Interlock Terminal", DocTopic.CHANNELS_INTERLOCK),
        ),
    ),
    DocSection(
        "Sweep Mode",
        DocTopic.SWEEP_OVERVIEW,
        _SHARED_CHILDREN
        + (
            DocNode("Sweep Timing", DocTopic.SWEEP_TIMING),
            DocNode("VAR1 — Basic Sweep", DocTopic.SWEEP_VAR1),
            DocNode("VAR2 — Subordinate Sweep", DocTopic.SWEEP_VAR2),
            DocNode("VARD — Synchronous Sweep", DocTopic.SWEEP_VARD),
            DocNode("PULSE — Pulse Source", DocTopic.SWEEP_PULSE),
        ),
    ),
    DocSection(
        "Sampling Mode",
        DocTopic.SAMPLING_OVERVIEW,
        _SHARED_CHILDREN
        + (
            DocNode("Sampling Parameters", DocTopic.SAMPLING_PARAMETERS),
            DocNode("Stop Condition", DocTopic.STOP_CONDITION),
        ),
    ),
    DocSection(
        "QSCV Mode",
        DocTopic.QSCV_OVERVIEW,
        (
            DocNode("User Functions", DocTopic.QSCV_USER_FUNCTIONS),
            DocNode("QSCV Measure Setup", DocTopic.QSCV_MEASURE_SETUP),
            DocNode("QSCV Timing", DocTopic.QSCV_TIMING),
            DocNode("VAR1 — Voltage Sweep", DocTopic.QSCV_VAR1),
        ),
    ),
    # Shared by the status card on every measurement-config page (the ⓘ icons
    # beside the Critical / Warnings / Information columns in its modal).
    DocSection(
        "Setup Status",
        DocTopic.STATUS_OVERVIEW,
        (
            DocNode("Critical Notifications", DocTopic.STATUS_CRITICAL),
            DocNode("Warnings", DocTopic.STATUS_WARNING),
            DocNode("Information", DocTopic.STATUS_INFO),
        ),
    ),
)


# ── Page bodies ──────────────────────────────────────────────────────────────

# Landing page shown when the window is opened from the Home button.
WELCOME_MD = pages.welcome.BODY

# Shown for any topic that does not yet have an authored page.
PLACEHOLDER_MD = """
# {title}

> **Documentation not yet written.**
>
> This page is a placeholder. Content for **{title}** will be added in a future
> update.
""".strip()


# Topic → Markdown body, sourced from the documentation_pages submodule.
# Add an entry here once a page module is authored; anything missing falls
# back to PLACEHOLDER_MD.
DOC_BODIES: dict[DocTopic, str] = {
    DocTopic.CHANNELS_SMU: pages.channels_smu.BODY,
    DocTopic.MEASUREMENT_RANGES: pages.measurement_ranges.BODY,
    DocTopic.SWEEP_VAR1: pages.var1_basic_sweep.BODY,
    DocTopic.SWEEP_VAR2: pages.var2_subordinate_sweep.BODY,
    DocTopic.SWEEP_VARD: pages.vard_synchronous_sweep.BODY,
    DocTopic.SWEEP_PULSE: pages.sweep_pulse.BODY,
    DocTopic.SAMPLING_OVERVIEW: pages.sampling_mode.BODY,
    DocTopic.SAMPLING_PARAMETERS: pages.sampling_parameters.BODY,
    DocTopic.STOP_CONDITION: pages.stop_condition.BODY,
    DocTopic.QSCV_OVERVIEW: pages.qscv_mode.BODY,
    DocTopic.QSCV_MEASURE_SETUP: pages.qscv_measure_setup.BODY,
    DocTopic.QSCV_VAR1: pages.qscv_var1_voltage_sweep.BODY,
    DocTopic.STATUS_OVERVIEW: pages.status_overview.BODY,
    DocTopic.STATUS_CRITICAL: pages.status_critical.BODY,
    DocTopic.STATUS_WARNING: pages.status_warning.BODY,
    DocTopic.STATUS_INFO: pages.status_information.BODY,
}


def get_doc_page(topic: DocTopic) -> DocPage:
    """Return the page for ``topic`` (or a placeholder if not yet authored)."""
    title = DOC_TITLES.get(topic, topic.value)
    body = DOC_BODIES.get(topic)
    if body is None:
        body = PLACEHOLDER_MD.format(title=title)
    return DocPage(title=title, body=body)
