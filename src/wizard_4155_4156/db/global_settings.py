"""
db/global_settings.py
----------------------
Global application configuration, persisted as JSON.

Per the project constraints, JSON storage is permitted only for the
recent-projects list and this global configuration.  Everything else lives in
the normalized per-project SQLite database.

``GlobalSettingsManager`` mirrors ``models/project.py::RecentProjectsManager``:
Qt-free, owns the JSON file at ``~/.wizard4155/settings.json``.  No PySide6
imports.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

# Permitted AC line frequencies (Hz).  The QSCV integration-time limits scale
# with line frequency, so this is read by the QSCV configuration page.
ALLOWED_LINE_FREQUENCIES: tuple[int, ...] = (50, 60)
DEFAULT_LINE_FREQUENCY_HZ: int = 50

# Selectable application themes (styles/theme.py builds PALETTE from this
# preference at import time; changes apply on the next launch).  Internal
# names are lowercase; the Preferences dialog maps them to UI labels
# ("dark" → "Black", …).
ALLOWED_THEMES: tuple[str, ...] = ("dark", "light", "france", "brasil")
DEFAULT_THEME: str = "light"


def _coerce_theme(value: object) -> str:
    """Snap any stored value to a permitted theme name (default light)."""
    name = str(value).strip().lower()
    return name if name in ALLOWED_THEMES else DEFAULT_THEME


def _coerce_line_frequency(value: object) -> int:
    """Snap any stored value to a permitted line frequency (default 50 Hz)."""
    try:
        ivalue = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_LINE_FREQUENCY_HZ
    return (
        ivalue
        if ivalue in ALLOWED_LINE_FREQUENCIES
        else DEFAULT_LINE_FREQUENCY_HZ
    )


@dataclass(frozen=True)
class GlobalSettings:
    """User-level configuration shared across all projects."""

    author: str = ""
    organization: str = ""
    line_frequency_hz: int = DEFAULT_LINE_FREQUENCY_HZ  # 50 or 60 Hz
    theme: str = DEFAULT_THEME  # applied on next launch (styles/theme.py)
    # Advanced options (Preferences dialog).  Both default False so existing
    # users keep today's behavior after updating.
    skip_reset: bool = False  # skip *RST at the start of each setup/run
    keep_auto_calibration: bool = False  # skip :CAL:AUTO OFF at setup start

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "organization": self.organization,
            "line_frequency_hz": self.line_frequency_hz,
            "theme": self.theme,
            "skip_reset": self.skip_reset,
            "keep_auto_calibration": self.keep_auto_calibration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GlobalSettings":
        defaults = cls()
        return cls(
            author=data.get("author", defaults.author),
            organization=data.get("organization", defaults.organization),
            line_frequency_hz=_coerce_line_frequency(
                data.get("line_frequency_hz", defaults.line_frequency_hz)
            ),
            theme=_coerce_theme(data.get("theme", defaults.theme)),
            skip_reset=bool(data.get("skip_reset", defaults.skip_reset)),
            keep_auto_calibration=bool(
                data.get(
                    "keep_auto_calibration", defaults.keep_auto_calibration
                )
            ),
        )

    def with_updates(self, **changes) -> "GlobalSettings":
        return replace(self, **changes)


class GlobalSettingsManager:
    """Loads / saves :class:`GlobalSettings`.

    Target path: ``~/.wizard4155/settings.json``.
    """

    _DEFAULT_DIR = Path.home() / ".wizard4155"
    _CONFIG_FILE = "settings.json"

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        base = config_dir if config_dir is not None else self._DEFAULT_DIR
        self._config_path = Path(base) / self._CONFIG_FILE
        self._settings = self._load()

    # ── Public API ───────────────────────────────────────────────────────────

    def get(self) -> GlobalSettings:
        return self._settings

    def save(self, settings: GlobalSettings) -> None:
        self._settings = settings
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, indent=2)

    # ── Private ──────────────────────────────────────────────────────────────

    def _load(self) -> GlobalSettings:
        if not self._config_path.exists():
            return GlobalSettings()
        try:
            with open(self._config_path, encoding="utf-8") as fh:
                return GlobalSettings.from_dict(json.load(fh))
        except Exception:  # noqa: BLE001
            return GlobalSettings()
