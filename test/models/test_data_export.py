"""
test/models/test_data_export.py
-------------------------------
Unit tests for the Qt-free dataset export model.
"""
import io
import zipfile

from wizard_4155_4156.models.data_export import (
    FORMATS,
    SPECS,
    DataFormat,
    FormatKind,
    generate_bytes,
    generate_text,
    is_code,
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
    sheet = zipfile.ZipFile(io.BytesIO(raw)).read(
        "xl/worksheets/sheet1.xml"
    ).decode("utf-8")
    assert '<c r="A2" t="n"><v>1.0</v></c>' in sheet
    # The nan row exists but carries no value cell.
    assert '<row r="3">' in sheet
    assert "A3" not in sheet


def test_generate_bytes_for_table_formats():
    data = {"V1": [1.0]}
    assert generate_bytes(data, DataFormat.CSV) == to_csv(data).encode("utf-8")
    assert generate_bytes(data, DataFormat.XLSX)[:2] == b"PK"  # zip magic
