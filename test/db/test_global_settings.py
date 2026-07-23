"""
test/db/test_global_settings.py
-------------------------------
Unit tests for global-settings JSON persistence.

Pure persistence layer (no PySide6).  Every manager is built against
``tmp_path`` and never touches the real ``~/.wizard4155``.
"""

from __future__ import annotations

import pytest

from wizard_4155_4156.db.global_settings import (
    GlobalSettings,
    GlobalSettingsManager,
)


def test_defaults_when_no_file_present(tmp_path):
    settings = GlobalSettingsManager(config_dir=tmp_path).get()

    assert settings.author == ""
    assert not (tmp_path / "settings.json").exists()


def test_save_writes_settings_json(tmp_path):
    manager = GlobalSettingsManager(config_dir=tmp_path)

    manager.save(manager.get().with_updates(author="Ada Lovelace"))

    assert (tmp_path / "settings.json").exists()


def test_settings_round_trip_through_json(tmp_path):
    manager = GlobalSettingsManager(config_dir=tmp_path)
    updated = manager.get().with_updates(
        author="Ada Lovelace",
        organization="Analytical Engines Ltd",
        skip_reset=True,
    )
    manager.save(updated)

    reloaded = GlobalSettingsManager(config_dir=tmp_path).get()

    assert reloaded == updated
    assert reloaded.author == "Ada Lovelace"
    assert reloaded.skip_reset is True
    assert reloaded.keep_auto_calibration is False


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text(
        "{ not valid json", encoding="utf-8"
    )

    assert GlobalSettingsManager(config_dir=tmp_path).get() == GlobalSettings()


def test_theme_defaults_to_light():
    assert GlobalSettings().theme == "light"


@pytest.mark.parametrize("name", ["dark", "france", "brasil"])
def test_theme_round_trips(name):
    themed = GlobalSettings().with_updates(theme=name)

    assert GlobalSettings.from_dict(themed.to_dict()) == themed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("purple", "light"),
        (3, "light"),
        ("DARK", "dark"),
        ("BrAsIl", "brasil"),
        (" france ", "france"),
    ],
)
def test_theme_coerces_invalid_and_unnormalized_values(raw, expected):
    assert GlobalSettings.from_dict({"theme": raw}).theme == expected


def test_advanced_options_default_to_false():
    defaults = GlobalSettings()

    assert defaults.skip_reset is False
    assert defaults.keep_auto_calibration is False


def test_advanced_options_round_trip():
    advanced = GlobalSettings().with_updates(
        skip_reset=True, keep_auto_calibration=True
    )

    assert GlobalSettings.from_dict(advanced.to_dict()) == advanced


def test_legacy_file_keeps_known_keys_and_ignores_unknown_ones():
    """Old ASCII/accuracy keys are dropped; advanced options get defaults."""
    legacy = GlobalSettings.from_dict(
        {"author": "Grace", "ascii_toggle": True, "accuracy_toggle": True}
    )

    assert legacy.author == "Grace"
    assert legacy.skip_reset is False
    assert legacy.keep_auto_calibration is False
