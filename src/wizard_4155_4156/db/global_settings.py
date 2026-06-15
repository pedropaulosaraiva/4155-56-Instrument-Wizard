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


@dataclass(frozen=True)
class GlobalSettings:
    """User-level configuration shared across all projects."""

    author: str = ""
    organization: str = ""
    ascii_toggle: bool = False  # future: ASCII data collection w/ status flags
    accuracy_toggle: bool = False  # future: per-point accuracy tracking

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "organization": self.organization,
            "ascii_toggle": self.ascii_toggle,
            "accuracy_toggle": self.accuracy_toggle,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GlobalSettings":
        defaults = cls()
        return cls(
            author=data.get("author", defaults.author),
            organization=data.get("organization", defaults.organization),
            ascii_toggle=bool(data.get("ascii_toggle", defaults.ascii_toggle)),
            accuracy_toggle=bool(
                data.get("accuracy_toggle", defaults.accuracy_toggle)
            ),
        )

    def with_updates(self, **changes) -> "GlobalSettings":
        return replace(self, **changes)


class GlobalSettingsManager:
    """Loads / saves :class:`GlobalSettings` to ``~/.wizard4155/settings.json``."""

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
