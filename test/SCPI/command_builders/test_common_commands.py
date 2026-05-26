import pytest

from wizard_4155_4156.SCPI.command_builders import (
    CommonCommandBuilder,
)


@pytest.fixture
def builder():
    return CommonCommandBuilder()


@pytest.mark.parametrize(
    ("method", "expected", "is_query"),
    [
        ("identify", "*IDN?", True),
        ("reset", "*RST", False),
        ("clear", "*CLS", False),
        ("get_operation_complete", "*OPC?", True),
    ],
)
def test_common_commands(builder, method, expected, is_query):
    getattr(builder, method)()
    assert builder.is_command_query is is_query
    assert builder.build() == expected
