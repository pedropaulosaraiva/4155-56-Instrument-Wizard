from wizard_4155_4156.SCPI.base_director import BaseDirector
from wizard_4155_4156.SCPI.command_builders.common_commands import (
    CommonCommandBuilder,
)

TEST_RESULT_KEY = "ID"
EXPECTED_RESET_CMD = "*RST"
EXPECTED_IDN_CMD = "*IDN?"


def test_base_director_build_pair_none():
    pair = BaseDirector._build_pair(CommonCommandBuilder)

    assert pair.set_command is None
    assert pair.get_command is None
    assert pair.is_binary_query is False
    assert pair.result_key is None


def test_base_director_build_pair_set_only():
    pair = BaseDirector._build_pair(
        CommonCommandBuilder, setter=CommonCommandBuilder.reset
    )

    assert pair.set_command == EXPECTED_RESET_CMD
    assert pair.get_command is None


def test_base_director_build_pair_get_only():
    pair = BaseDirector._build_pair(
        CommonCommandBuilder, getter=CommonCommandBuilder.identify
    )

    assert pair.set_command is None
    assert pair.get_command == EXPECTED_IDN_CMD


def test_base_director_build_pair_both():
    pair = BaseDirector._build_pair(
        CommonCommandBuilder,
        setter=CommonCommandBuilder.reset,
        getter=CommonCommandBuilder.identify,
        is_binary_query=True,
        result_key=TEST_RESULT_KEY,
    )

    assert pair.set_command == EXPECTED_RESET_CMD
    assert pair.get_command == EXPECTED_IDN_CMD
    assert pair.is_binary_query is True
    assert pair.result_key == TEST_RESULT_KEY
