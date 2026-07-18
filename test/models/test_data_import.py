"""
test/models/test_data_import.py
-------------------------------
Unit tests for the Qt-free external-measurement import model.
"""

import math

from wizard_4155_4156.models.data_export import to_csv
from wizard_4155_4156.models.data_import import (
    WHITESPACE_DELIMITER,
    CsvOptions,
    parse_import_files,
)

OPTS = CsvOptions()


def _write(tmp_path, name, text, encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return str(path)


# ── Happy paths ──────────────────────────────────────────────────────────────


def test_two_valid_files_share_variables(tmp_path):
    a = _write(tmp_path, "a.csv", "V1,I1\n0.0,1e-3\n0.5,2E-3\n")
    b = _write(tmp_path, "b.csv", "V1,I1\n1.0,3.0\n")
    result = parse_import_files([a, b], OPTS)
    assert result.all_ok
    assert result.variables == ["V1", "I1"]
    assert result.files[0].stem == "a"
    assert result.files[0].data == {"V1": [0.0, 0.5], "I1": [1e-3, 2e-3]}
    assert result.files[1].data == {"V1": [1.0], "I1": [3.0]}


def test_blank_cell_becomes_nan(tmp_path):
    path = _write(tmp_path, "a.csv", "a,b\n1.0,\n,2.0\n")
    result = parse_import_files([path], OPTS)
    assert result.all_ok
    data = result.files[0].data
    assert math.isnan(data["b"][0])
    assert math.isnan(data["a"][1])
    assert data["a"][0] == 1.0


def test_blank_lines_and_crlf_and_bom(tmp_path):
    path = tmp_path / "a.csv"
    path.write_bytes(b"\xef\xbb\xbfV1,I1\r\n1.0,2.0\r\n\r\n3.0,4.0\r\n")
    result = parse_import_files([str(path)], OPTS)
    assert result.all_ok
    assert result.variables == ["V1", "I1"]
    assert result.files[0].data == {"V1": [1.0, 3.0], "I1": [2.0, 4.0]}


def test_semicolon_and_tab_delimiters(tmp_path):
    semi = _write(tmp_path, "semi.csv", "a;b\n1.0;2.0\n")
    tab = _write(tmp_path, "tab.csv", "a\tb\n1.0\t2.0\n")
    ok_semi = parse_import_files([semi], CsvOptions(delimiter=";"))
    ok_tab = parse_import_files([tab], CsvOptions(delimiter="\t"))
    assert ok_semi.all_ok
    assert ok_tab.all_ok
    assert ok_semi.variables == ok_tab.variables == ["a", "b"]


def test_quote_char_variants(tmp_path):
    single = _write(tmp_path, "sq.csv", "'a','b'\n1.0,2.0\n")
    result = parse_import_files([single], CsvOptions(quotechar="'"))
    assert result.all_ok
    assert result.variables == ["a", "b"]

    none = _write(tmp_path, "nq.csv", "a,b\n1.0,2.0\n")
    result = parse_import_files([none], CsvOptions(quotechar=None))
    assert result.all_ok


def test_whitespace_delimiter_mixed_runs(tmp_path):
    # Runs of spaces and tabs (any mix) separate columns.
    path = _write(tmp_path, "ws.csv", "V1   I1\tR\n1.0 \t 2.0   3.0\n")
    opts = CsvOptions(delimiter=WHITESPACE_DELIMITER)
    result = parse_import_files([path], opts)
    assert result.all_ok
    assert result.variables == ["V1", "I1", "R"]
    assert result.files[0].data == {
        "V1": [1.0],
        "I1": [2.0],
        "R": [3.0],
    }


def test_whitespace_delimiter_missing_value_is_ragged(tmp_path):
    # split() cannot represent an empty cell — a missing value shows up as
    # a ragged row and is reported, never silently shifted.
    path = _write(tmp_path, "ws.csv", "a b\n1.0 2.0\n3.0\n")
    result = parse_import_files(
        [path], CsvOptions(delimiter=WHITESPACE_DELIMITER)
    )
    assert result.files[0].error == "row 3 has 1 cell(s), expected 2"


def test_whitespace_delimiter_with_comma_decimal(tmp_path):
    path = _write(tmp_path, "ws.csv", "a b\n1,5\t2,5\n")
    opts = CsvOptions(delimiter=WHITESPACE_DELIMITER, decimal=",")
    result = parse_import_files([path], opts)
    assert result.all_ok
    assert result.files[0].data == {"a": [1.5], "b": [2.5]}


def test_comma_decimal_separator(tmp_path):
    path = _write(tmp_path, "eu.csv", "a;b\n1,5;2,5e-3\n-0,25;\n")
    opts = CsvOptions(delimiter=";", decimal=",")
    result = parse_import_files([path], opts)
    assert result.all_ok
    data = result.files[0].data
    expected_b0 = 2.5e-3
    assert data["a"] == [1.5, -0.25]
    assert data["b"][0] == expected_b0
    assert math.isnan(data["b"][1])


def test_comma_decimal_bad_token_still_fails(tmp_path):
    path = _write(tmp_path, "eu.csv", "a\n1,5,5\n")
    result = parse_import_files([path], CsvOptions(delimiter=";", decimal=","))
    assert "non-numeric value '1,5,5'" in result.files[0].error


def test_round_trip_with_own_export(tmp_path):
    dataset = {"V1": [0.0, 1.5, float("nan")], "I1": [1e-9, 2e-9, 3e-9]}
    path = _write(tmp_path, "export.csv", to_csv(dataset))
    result = parse_import_files([path], OPTS)
    assert result.all_ok
    data = result.files[0].data
    assert data["V1"][:2] == [0.0, 1.5]
    assert math.isnan(data["V1"][2])
    assert data["I1"] == [1e-9, 2e-9, 3e-9]


# ── Per-file format errors ───────────────────────────────────────────────────


def test_missing_file_is_reported(tmp_path):
    result = parse_import_files([str(tmp_path / "nope.csv")], OPTS)
    assert not result.all_ok
    assert "cannot read file" in result.files[0].error
    assert result.variables is None


def test_empty_file(tmp_path):
    path = _write(tmp_path, "a.csv", "")
    result = parse_import_files([path], OPTS)
    assert result.files[0].error == "file is empty"


def test_header_only_file(tmp_path):
    path = _write(tmp_path, "a.csv", "V1,I1\n")
    result = parse_import_files([path], OPTS)
    assert result.files[0].error == "no data rows (only a header)"


def test_empty_header_cell(tmp_path):
    path = _write(tmp_path, "a.csv", "V1,,I1\n1.0,2.0,3.0\n")
    result = parse_import_files([path], OPTS)
    assert "empty column name" in result.files[0].error
    assert "column 2" in result.files[0].error


def test_duplicate_header_name(tmp_path):
    path = _write(tmp_path, "a.csv", "V1,V1\n1.0,2.0\n")
    result = parse_import_files([path], OPTS)
    assert result.files[0].error == "duplicate column name 'V1'"


def test_ragged_row(tmp_path):
    path = _write(tmp_path, "a.csv", "a,b\n1.0,2.0\n3.0\n")
    result = parse_import_files([path], OPTS)
    assert result.files[0].error == "row 3 has 1 cell(s), expected 2"


def test_non_numeric_cell_names_row_and_column(tmp_path):
    path = _write(tmp_path, "a.csv", "a,b\n1.0,oops\n")
    result = parse_import_files([path], OPTS)
    assert result.files[0].error == (
        "non-numeric value 'oops' at row 2, column 'b'"
    )


def test_not_utf8(tmp_path):
    path = tmp_path / "a.csv"
    path.write_bytes(b"\xff\xfe\x00\x01binary")
    result = parse_import_files([str(path)], OPTS)
    assert result.files[0].error == "file is not valid UTF-8 text"


# ── Cross-file consistency ───────────────────────────────────────────────────


def test_header_mismatch_names(tmp_path):
    a = _write(tmp_path, "a.csv", "V1,I1\n1.0,2.0\n")
    b = _write(tmp_path, "b.csv", "V2,I2\n1.0,2.0\n")
    result = parse_import_files([a, b], OPTS)
    assert result.files[0].error is None
    assert "variables do not match" in result.files[1].error
    assert result.variables == ["V1", "I1"]


def test_header_mismatch_order_sensitive(tmp_path):
    a = _write(tmp_path, "a.csv", "V1,I1\n1.0,2.0\n")
    b = _write(tmp_path, "b.csv", "I1,V1\n1.0,2.0\n")
    result = parse_import_files([a, b], OPTS)
    assert "variables do not match" in result.files[1].error


def test_first_invalid_file_standard_comes_from_second(tmp_path):
    bad = _write(tmp_path, "bad.csv", "")
    good = _write(tmp_path, "good.csv", "V1\n1.0\n")
    result = parse_import_files([bad, good], OPTS)
    assert result.variables == ["V1"]
    assert result.files[1].error is None


def test_no_valid_file_gives_no_standard(tmp_path):
    a = _write(tmp_path, "a.csv", "")
    b = _write(tmp_path, "b.csv", "x\n")
    result = parse_import_files([a, b], OPTS)
    assert result.variables is None
    assert not result.all_ok


def test_empty_selection_is_not_ok():
    result = parse_import_files([], OPTS)
    assert not result.all_ok
    assert result.variables is None


def test_expected_variables_match(tmp_path):
    path = _write(tmp_path, "a.csv", "V1,I1\n1.0,2.0\n")
    result = parse_import_files(
        [path], OPTS, expected_variables=["V1", "I1"]
    )
    assert result.all_ok
    assert result.variables == ["V1", "I1"]


def test_expected_variables_mismatch(tmp_path):
    path = _write(tmp_path, "a.csv", "V1,I1\n1.0,2.0\n")
    result = parse_import_files(
        [path], OPTS, expected_variables=["V2", "I2"]
    )
    assert "variables do not match" in result.files[0].error
    # The standard stays the setup's list even though no file was valid.
    assert result.variables == ["V2", "I2"]


# ── Name collisions ──────────────────────────────────────────────────────────


def test_duplicate_stems_across_directories(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    a = _write(tmp_path / "one", "run.csv", "V1\n1.0\n")
    b = _write(tmp_path / "two", "run.csv", "V1\n2.0\n")
    result = parse_import_files([a, b], OPTS)
    assert result.files[0].error is None
    assert "duplicate file name 'run'" in result.files[1].error


def test_taken_name_collision(tmp_path):
    path = _write(tmp_path, "run.csv", "V1\n1.0\n")
    result = parse_import_files([path], OPTS, taken_names={"run"})
    assert "already exists" in result.files[0].error
    assert result.variables is None
