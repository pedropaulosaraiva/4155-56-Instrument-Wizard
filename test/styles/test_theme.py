"""
test/styles/test_theme.py
-------------------------
Unit tests for theme palette selection and the theme-preference reader.

Pure Python (``styles.theme`` builds no widgets), so this runs as a normal
pytest module.  The preference reader is exercised against ``tmp_path`` files
and never touches the real ``~/.wizard4155``.
"""

from __future__ import annotations

import re
from dataclasses import fields

import pytest

from wizard_4155_4156.styles.theme import (
    _BRASIL_OVERRIDES,
    _FRANCE_OVERRIDES,
    _ICON_VARIANTS,
    _LIGHT_OVERRIDES,
    _Palette,
    _read_theme_preference,
    load_palette,
)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_OVERRIDES = {
    "light": _LIGHT_OVERRIDES,
    "france": _FRANCE_OVERRIDES,
    "brasil": _BRASIL_OVERRIDES,
}

_THEMES = list(_OVERRIDES)


@pytest.fixture(autouse=True)
def _no_env_theme(monkeypatch):
    """WIZARD_THEME would win over every preference file under test."""
    monkeypatch.delenv("WIZARD_THEME", raising=False)


def _pref_file(tmp_path, content: str):
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_dark_palette_is_the_dataclass_baseline():
    assert load_palette("dark") == _Palette()


def test_unknown_theme_falls_back_to_light():
    assert load_palette("purple") == load_palette("light")


@pytest.mark.parametrize("theme_name", _THEMES)
def test_overrides_target_real_tokens_with_valid_colors(theme_name):
    field_names = {f.name for f in fields(_Palette)}
    palette = load_palette(theme_name)

    for key, value in _OVERRIDES[theme_name].items():
        assert key in field_names, f"unknown token: {key}"
        assert getattr(palette, key) == value
        if isinstance(value, str):
            assert _HEX.match(value), f"{key} not #rrggbb: {value}"


@pytest.mark.parametrize("theme_name", _THEMES)
def test_trace_cycle_keeps_its_length_and_is_valid_hex(theme_name):
    palette = load_palette(theme_name)

    assert len(palette.GRAPH_TRACE_COLORS) == len(
        load_palette("dark").GRAPH_TRACE_COLORS
    )
    assert all(_HEX.match(c) for c in palette.GRAPH_TRACE_COLORS)


def test_light_and_dark_trace_cycles_differ():
    assert (
        load_palette("light").GRAPH_TRACE_COLORS
        != load_palette("dark").GRAPH_TRACE_COLORS
    )


@pytest.mark.parametrize("theme_name", _THEMES)
def test_non_override_tokens_are_identical_across_themes(theme_name):
    """Geometry, typography and alpha tokens are shared between themes."""
    dark = load_palette("dark")
    palette = load_palette(theme_name)
    overrides = _OVERRIDES[theme_name]

    for f in fields(_Palette):
        if f.name in overrides:
            continue
        assert getattr(palette, f.name) == getattr(dark, f.name), f.name


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"theme": "light"}', "light"),
        ('{"theme": "france"}', "france"),
        ('{"theme": "BRASIL"}', "brasil"),
        ('{"theme": "dark"}', "dark"),
        ('{"theme": "purple"}', "light"),
        ("{ not valid json", "light"),
    ],
)
def test_preference_reader_parses_and_falls_back(tmp_path, content, expected):
    assert _read_theme_preference(_pref_file(tmp_path, content)) == expected


def test_preference_reader_falls_back_when_file_missing(tmp_path):
    assert _read_theme_preference(tmp_path / "missing.json") == "light"


def test_env_override_wins_over_file(tmp_path, monkeypatch):
    pref = _pref_file(tmp_path, '{"theme": "brasil"}')
    monkeypatch.setenv("WIZARD_THEME", "light")

    assert _read_theme_preference(pref) == "light"


def test_icon_variants_per_theme():
    """Light UIs use the light icon set, dark UIs the dark one."""
    assert _ICON_VARIANTS == {
        "dark": "dark",
        "light": "light",
        "france": "light",
        "brasil": "dark",
    }
