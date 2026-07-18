"""
test/models/test_data_export.py
-------------------------------
Unit tests for the Qt-free dataset export model.
"""

import csv
import io
import zipfile
from datetime import datetime

import pytest

from wizard_4155_4156.models.data_export import (
    FORMATS,
    SPECS,
    CsvOptions,
    DataFormat,
    FormatKind,
    build_zip,
    csv_dialect_is_valid,
    export_filename,
    generate_bytes,
    generate_text,
    is_code,
    ordered_dataset,
    sanitize_filename,
    to_c_array,
    to_csv,
    to_matlab,
    to_numpy_matplotlib,
    to_pure_python,
    to_xlsx_bytes,
)

NAN = float("nan")


def test_specs_cover_every_format():
    assert set(SPECS) == set(DataFormat)
    assert set(FORMATS) == set(DataFormat)


def test_kind_classification():
    assert not is_code(DataFormat.CSV)
    assert not is_code(DataFormat.XLSX)
    assert is_code(DataFormat.PY_PURE)
    assert SPECS[DataFormat.C_ARRAY].kind is FormatKind.CODE


def test_csv_header_and_rows():
    text = to_csv({"V1": [0.0, 1.0], "I1": [2.0, 3.0]})
    rows = text.splitlines()
    assert rows[0] == "V1,I1"
    assert rows[1] == "0.0,2.0"
    assert rows[2] == "1.0,3.0"


def test_ragged_columns_padded_with_blank_in_csv():
    # Shorter column is padded with nan, which renders blank in CSV.
    text = to_csv({"a": [1.0, 2.0, 3.0], "b": [4.0]})
    rows = text.splitlines()
    assert rows[1] == "1.0,4.0"
    assert rows[2] == "2.0,"
    assert rows[3] == "3.0,"


def test_nan_tokens_per_language():
    data = {"x": [NAN]}
    assert "float('nan')" in to_pure_python(data)
    assert "np.nan" in to_numpy_matplotlib(data)
    assert "NAN" in to_c_array(data)
    assert "NaN" in to_matlab(data)
    # CSV leaves the cell blank (shown here in a normal multi-column row).
    assert to_csv({"a": [1.0], "x": [NAN]}).splitlines()[1] == "1.0,"


def test_identifier_sanitising_for_at_columns():
    data = {"@INDEX": [0.0, 1.0], "V1": [2.0, 3.0]}
    c_code = to_c_array(data)
    # The original name only survives as a comment, never as an identifier.
    assert "double _INDEX[N]" in c_code
    assert "double @INDEX" not in c_code
    # Pure-python keeps the verbatim name as a dict key.
    assert "'@INDEX'" in to_pure_python(data)


def test_numpy_includes_plot_scaffold():
    code = to_numpy_matplotlib({"V1": [0.0, 1.0], "I1": [2.0, 3.0]})
    assert "import numpy as np" in code
    assert "plt.plot(V1, I1" in code
    assert "plt.show()" in code


def test_generate_text_dispatch_matches_direct_call():
    data = {"V1": [1.0, 2.0]}
    assert generate_text(data, DataFormat.MATLAB) == to_matlab(data)


def test_xlsx_is_valid_zip_with_expected_parts():
    raw = to_xlsx_bytes({"V1": [1.0, 2.0], "I1": [3.0, 4.0]})
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    assert "[Content_Types].xml" in names
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names

    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "V1" in sheet
    assert "I1" in sheet
    assert '<c r="A2" t="n"><v>1.0</v></c>' in sheet


def test_xlsx_skips_nan_cells():
    raw = to_xlsx_bytes({"x": [1.0, NAN]})
    sheet = (
        zipfile.ZipFile(io.BytesIO(raw))
        .read("xl/worksheets/sheet1.xml")
        .decode("utf-8")
    )
    assert '<c r="A2" t="n"><v>1.0</v></c>' in sheet
    # The nan row exists but carries no value cell.
    assert '<row r="3">' in sheet
    assert "A3" not in sheet


def test_generate_bytes_for_table_formats():
    data = {"V1": [1.0]}
    assert generate_bytes(data, DataFormat.CSV) == to_csv(data).encode("utf-8")
    assert generate_bytes(data, DataFormat.XLSX)[:2] == b"PK"  # zip magic


# ── CSV options ──────────────────────────────────────────────────────────────


def test_csv_default_options_unchanged():
    # Regression lock: default CsvOptions must reproduce the historical output.
    data = {"V1": [0.0, 1.0], "I1": [2.0, NAN]}
    assert to_csv(data, CsvOptions()) == to_csv(data)
    assert to_csv(data) == "V1,I1\r\n0.0,2.0\r\n1.0,\r\n"


def test_csv_alternative_delimiters():
    data = {"a": [1.0], "b": [2.0]}
    assert to_csv(data, CsvOptions(delimiter=";")).splitlines()[1] == "1.0;2.0"
    assert (
        to_csv(data, CsvOptions(delimiter="\t")).splitlines()[1] == "1.0\t2.0"
    )
    assert to_csv(data, CsvOptions(delimiter=" ")).splitlines()[1] == "1.0 2.0"


def test_csv_decimal_comma_leaves_headers_untouched():
    text = to_csv(
        {"V.1": [1.5]}, CsvOptions(delimiter=";", decimal_separator=",")
    )
    rows = text.splitlines()
    assert rows[0] == "V.1"  # header dot untouched
    assert rows[1] == "1,5"


def test_csv_comma_delimiter_comma_decimal_quotes_and_round_trips():
    text = to_csv(
        {"a": [1.5], "b": [2.25]}, CsvOptions(decimal_separator=",")
    )
    assert text.splitlines()[1] == '"1,5","2,25"'
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed[1] == ["1,5", "2,25"]


def test_csv_quote_none_escapes_collisions():
    text = to_csv(
        {"a,b": [1.5]},
        CsvOptions(decimal_separator=",", quotechar=None),
    )
    rows = text.splitlines()
    assert rows[0] == "a\\,b"
    assert rows[1] == "1\\,5"


def test_csv_single_quote_char():
    text = to_csv(
        {"a": [1.5]},
        CsvOptions(decimal_separator=",", quotechar="'"),
    )
    assert text.splitlines()[1] == "'1,5'"


def test_csv_dialect_rule_comma_comma_requires_quoting():
    # The one restricted combination: comma delimiter + comma decimal
    # without a quote character (unparseable on import).
    assert not csv_dialect_is_valid(",", ",", None)
    assert csv_dialect_is_valid(",", ",", '"')
    assert csv_dialect_is_valid(",", ",", "'")
    # Distinct delimiter/decimal is always fine, quoted or not.
    assert csv_dialect_is_valid(";", ",", None)
    assert csv_dialect_is_valid(",", ".", None)
    assert csv_dialect_is_valid(" ", ",", None)
    assert csv_dialect_is_valid("\t", ".", '"')


def test_generate_bytes_passes_csv_options():
    data = {"a": [1.0], "b": [2.0]}
    opts = CsvOptions(delimiter=";")
    assert generate_bytes(data, DataFormat.CSV, opts) == to_csv(
        data, opts
    ).encode("utf-8")
    # XLSX ignores CSV options entirely.
    assert generate_bytes(data, DataFormat.XLSX, opts) == generate_bytes(
        data, DataFormat.XLSX
    )


# ── Filenames / ordering / zip bundling ──────────────────────────────────────


def test_sanitize_filename():
    assert sanitize_filename('a<b>:"/\\|?*c') == "abc"
    assert sanitize_filename("  my   run  ") == "my_run"
    assert sanitize_filename("run...") == "run"
    assert sanitize_filename("???") == "data"
    assert sanitize_filename("", fallback="x") == "x"


def test_export_filename_with_and_without_timestamp():
    ts = datetime(2026, 7, 18, 14, 30)
    assert export_filename("data", DataFormat.CSV) == "data.csv"
    assert (
        export_filename("data", DataFormat.XLSX, ts)
        == "data_2026-07-18_14-30.xlsx"
    )


def test_ordered_dataset_reorders_and_preserves_values():
    data = {"a": [1.0], "b": [2.0], "c": [3.0]}
    result = ordered_dataset(data, ["c", "a", "b"])
    assert list(result) == ["c", "a", "b"]
    assert result["c"] == [3.0]


def test_ordered_dataset_mismatched_order_keeps_leftovers():
    data = {"a": [1.0], "b": [2.0]}
    # Unknown names ignored; unlisted columns follow in original order.
    result = ordered_dataset(data, ["b", "zz"])
    assert list(result) == ["b", "a"]
    assert list(ordered_dataset(data, [])) == ["a", "b"]


def test_build_zip_entry_names_and_payloads():
    entries = [
        ("Run 1", None, {"a": [1.0]}),
        ("Run 2", None, {"a": [2.0]}),
    ]
    opts = CsvOptions(delimiter=";")
    raw = build_zip(entries, DataFormat.CSV, csv_options=opts)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert zf.namelist() == ["Run_1.csv", "Run_2.csv"]
    assert zf.read("Run_2.csv") == to_csv({"a": [2.0]}, opts).encode("utf-8")


def test_build_zip_timestamp_flag():
    ts = datetime(2026, 7, 18, 14, 30)
    entries = [("Run", ts, {"a": [1.0]}), ("Other", None, {"a": [2.0]})]
    with_ts = zipfile.ZipFile(
        io.BytesIO(build_zip(entries, DataFormat.CSV, include_timestamp=True))
    )
    # Entries lacking a date get no timestamp even when the flag is on.
    assert with_ts.namelist() == ["Run_2026-07-18_14-30.csv", "Other.csv"]
    without = zipfile.ZipFile(io.BytesIO(build_zip(entries, DataFormat.CSV)))
    assert without.namelist() == ["Run.csv", "Other.csv"]


def test_build_zip_deduplicates_names():
    entries = [
        ("Run", None, {"a": [1.0]}),
        ("Run", None, {"a": [2.0]}),
        ("Run", None, {"a": [3.0]}),
    ]
    zf = zipfile.ZipFile(io.BytesIO(build_zip(entries, DataFormat.CSV)))
    assert zf.namelist() == ["Run.csv", "Run_2.csv", "Run_3.csv"]


def test_build_zip_rejects_code_formats():
    with pytest.raises(ValueError, match="not a downloadable table format"):
        build_zip([("Run", None, {"a": [1.0]})], DataFormat.PY_PURE)


def test_build_zip_xlsx_entries_are_valid_zip_payloads():
    raw = build_zip([("Run", None, {"a": [1.0]})], DataFormat.XLSX)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    inner = zipfile.ZipFile(io.BytesIO(zf.read("Run.xlsx")))
    assert "xl/worksheets/sheet1.xml" in inner.namelist()
