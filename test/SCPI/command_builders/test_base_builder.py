from typing import ClassVar, Literal

import pytest

from wizard_4155_4156.SCPI.command_builders import (
    SCPICommandBuilder,
)


class DummyBuilder(SCPICommandBuilder):
    _BASE_COMMAND: ClassVar[str] = ":BASE"

    def build_something(self):
        self._add_command_segment(":SOME")
        self._is_command_ready = True

    def build_query(self):
        self._add_command_segment(":QUERY?")
        self._is_command_ready = True
        self._is_command_query = True

    def build_regex(self):
        self._building_command = ":BASE:CHAN:SMU1"
        self._add_command_segment(
            ":MODE I", required_base=r":BASE:CHAN:SMU[1-4]"
        )

    def build_regex_fail(self):
        self._building_command = ":BASE:CHAN:VMU1"
        self._add_command_segment(
            ":MODE I", required_base=r":BASE:CHAN:SMU[1-4]"
        )


def test_initial_state():
    b = SCPICommandBuilder()
    assert b.is_command_query is False
    with pytest.raises(ValueError, match="Building command is not completed"):
        b.build()


def test_build_success():
    b = DummyBuilder()
    b.build_something()
    assert b.is_command_query is False
    assert b.build() == ":BASE:SOME"

    assert b.is_command_query is False
    with pytest.raises(ValueError, match="Building command is not completed"):
        b.build()


def test_build_query():
    b = DummyBuilder()
    b.build_query()
    assert b.is_command_query is True
    assert b.build() == ":BASE:QUERY?"


def test_verify_base_regex_success():
    b = DummyBuilder()
    b.build_regex()
    assert b._building_command == ":BASE:CHAN:SMU1:MODE I"


def test_verify_base_regex_fail():
    b = DummyBuilder()
    with pytest.raises(
        ValueError, match="Building command wrongly constructed"
    ):
        b.build_regex_fail()


def test_verify_parameter():
    b = DummyBuilder()
    MockLiteral = Literal["VAL1", "VAL2"]

    b._verify_parameter("VAL1", MockLiteral)

    with pytest.raises(ValueError, match="Invalid parameter"):
        b._verify_parameter("INVALID", MockLiteral)
