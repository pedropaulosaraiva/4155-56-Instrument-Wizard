"""
Tests for models/project.py::format_relative_time — the age label shown on the
recent-project rows of the home page.
"""

from datetime import datetime, timedelta

import pytest

from wizard_4155_4156.models.project import format_relative_time

NOW = datetime(2026, 7, 22, 12, 0, 0)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=0), "Just now"),
        (timedelta(seconds=59), "Just now"),
        (timedelta(minutes=1), "1 minute ago"),
        (timedelta(minutes=45), "45 minutes ago"),
        (timedelta(hours=1), "1 hour ago"),
        (timedelta(hours=2, minutes=30), "2 hours ago"),
        (timedelta(hours=23, minutes=59), "23 hours ago"),
        (timedelta(days=1), "Yesterday"),
        (timedelta(days=1, hours=5), "Yesterday"),
        (timedelta(days=3), "3 days ago"),
        (timedelta(days=7), "7 days ago"),
    ],
)
def test_relative_labels(delta: timedelta, expected: str) -> None:
    assert format_relative_time(NOW - delta, now=NOW) == expected


def test_falls_back_to_absolute_date_past_a_week() -> None:
    old = NOW - timedelta(days=8)
    assert format_relative_time(old, now=NOW) == "14/07/2026"


def test_future_timestamps_show_an_absolute_date() -> None:
    """Clock skew must not produce a negative "ago" label."""
    ahead = NOW + timedelta(hours=3)
    assert format_relative_time(ahead, now=NOW) == "22/07/2026"
