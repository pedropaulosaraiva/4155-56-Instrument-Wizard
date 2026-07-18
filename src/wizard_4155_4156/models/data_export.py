"""
models/data_export.py
---------------------
Pure-Python (Qt-free) export of a tabular measurement dataset.

A dataset is an *ordered* mapping ``{var_name: [values]}`` — the canonical
shape used across the app (e.g. produced by
``db.assembler.execution_to_data_dict``).  Every value is a float; non-finite
readings are ``nan``.

This module is the single source of truth for turning a dataset into:
  * spreadsheet-style data (CSV text / XLSX bytes), and
  * a source-code snippet that recreates the dataset (pure Python,
    NumPy + Matplotlib, C/C++ arrays, MATLAB vectors).

No PySide6 imports — unit-testable without a GUI.  User-visible *labels* for
the formats deliberately live in ``gui_text`` (routed through ``tr_ui``); this
module only owns the logical formats and their technical metadata.
"""

from __future__ import annotations

import csv
import io
import math
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

Dataset = Mapping[str, Sequence[float]]


# =============================================================================
# Format registry
# =============================================================================


class DataFormat(Enum):
    """Every output format offered by the Table page."""

    CSV = "csv"
    XLSX = "xlsx"
    PY_PURE = "py_pure"
    PY_NUMPY = "py_numpy"
    C_ARRAY = "c_array"
    MATLAB = "matlab"


class FormatKind(Enum):
    """Whether a format renders as a table or as a code snippet."""

    TABLE = "table"
    CODE = "code"


@dataclass(frozen=True)
class FormatSpec:
    """Technical metadata for a :class:`DataFormat` (no user-facing copy)."""

    kind: FormatKind
    extension: str  # file extension without the dot
    language: str | None  # syntax-highlighter tag: python | c | matlab | None


#: Stable display order (drives the Format combo box order).
FORMATS: list[DataFormat] = [
    DataFormat.CSV,
    DataFormat.XLSX,
    DataFormat.PY_PURE,
    DataFormat.PY_NUMPY,
    DataFormat.C_ARRAY,
    DataFormat.MATLAB,
]

SPECS: dict[DataFormat, FormatSpec] = {
    DataFormat.CSV: FormatSpec(FormatKind.TABLE, "csv", None),
    DataFormat.XLSX: FormatSpec(FormatKind.TABLE, "xlsx", None),
    DataFormat.PY_PURE: FormatSpec(FormatKind.CODE, "py", "python"),
    DataFormat.PY_NUMPY: FormatSpec(FormatKind.CODE, "py", "python"),
    DataFormat.C_ARRAY: FormatSpec(FormatKind.CODE, "c", "c"),
    DataFormat.MATLAB: FormatSpec(FormatKind.CODE, "m", "matlab"),
}


def is_code(fmt: DataFormat) -> bool:
    """True if *fmt* is rendered as a code snippet (Copy), not a table."""
    return SPECS[fmt].kind is FormatKind.CODE


@dataclass(frozen=True)
class CsvOptions:
    """User-selectable CSV dialect.  Defaults reproduce the historical
    RFC-4180 output (comma delimiter, dot decimals, double-quote quoting)."""

    delimiter: str = ","  # "," | ";" | "\t" | " "
    decimal_separator: str = "."  # "." | ","
    quotechar: str | None = '"'  # '"' | "'" | None (no quoting)


DEFAULT_CSV_OPTIONS = CsvOptions()


#: Minimum columns before the NumPy export adds an x/y plot scaffold.
_PLOT_MIN_COLUMNS = 2


# =============================================================================
# Shared helpers
# =============================================================================


def _columns(data: Dataset) -> list[tuple[str, list[float]]]:
    """Ordered ``(name, values)`` pairs, padded to equal length with nan."""
    cols = [
        (name, [float(v) for v in values]) for name, values in data.items()
    ]
    n = max((len(values) for _, values in cols), default=0)
    for _, values in cols:
        if len(values) < n:
            values.extend([float("nan")] * (n - len(values)))
    return cols


def _row_count(cols: Sequence[tuple[str, list[float]]]) -> int:
    return len(cols[0][1]) if cols else 0


def _safe_ident(name: str) -> str:
    """Coerce a variable name into a valid C/Python/MATLAB identifier."""
    cleaned = re.sub(r"\W", "_", name)
    if not cleaned:
        cleaned = "col"
    if cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return cleaned


def _safe_idents(names: Sequence[str]) -> list[str]:
    """Sanitise a list of names, disambiguating any resulting collisions."""
    used: set[str] = set()
    out: list[str] = []
    for name in names:
        base = _safe_ident(name)
        ident = base
        k = 2
        while ident in used:
            ident = f"{base}_{k}"
            k += 1
        used.add(ident)
        out.append(ident)
    return out


def _num(value: float, nan_token: str) -> str:
    """Round-trippable float literal, or *nan_token* for non-finite values."""
    if value is None or not math.isfinite(value):
        return nan_token
    return repr(float(value))


# =============================================================================
# Table formats
# =============================================================================


def to_csv(data: Dataset, options: CsvOptions = DEFAULT_CSV_OPTIONS) -> str:
    """CSV: header row + one row per sample; blanks for nan.

    With a quote character, fields containing the delimiter (e.g. comma
    decimals under a comma delimiter) are quoted per RFC 4180.  With
    ``quotechar=None`` nothing is ever quoted and collisions are
    backslash-escaped instead — the user's explicit choice.
    """
    cols = _columns(data)
    buf = io.StringIO()
    if options.quotechar is None:
        writer = csv.writer(
            buf,
            delimiter=options.delimiter,
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
    else:
        writer = csv.writer(
            buf,
            delimiter=options.delimiter,
            quotechar=options.quotechar,
            quoting=csv.QUOTE_MINIMAL,
        )

    def cell(value: float) -> str:
        text = _num(value, "")
        if options.decimal_separator != ".":
            text = text.replace(".", options.decimal_separator)
        return text

    writer.writerow([name for name, _ in cols])
    for i in range(_row_count(cols)):
        writer.writerow([cell(values[i]) for _, values in cols])
    return buf.getvalue()


# =============================================================================
# Code formats
# =============================================================================


def to_pure_python(data: Dataset) -> str:
    """A plain ``dict`` of lists keyed by the original variable names."""
    cols = _columns(data)
    lines = ["# Measurement data — pure Python", "", "data = {"]
    for name, values in cols:
        body = ", ".join(_num(v, "float('nan')") for v in values)
        lines.append(f"    {name!r}: [{body}],")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_numpy_matplotlib(data: Dataset) -> str:
    """NumPy arrays plus a minimal Matplotlib plotting scaffold."""
    cols = _columns(data)
    idents = _safe_idents([name for name, _ in cols])
    lines = ["import numpy as np", "import matplotlib.pyplot as plt", ""]
    for ident, (name, values) in zip(idents, cols):
        body = ", ".join(_num(v, "np.nan") for v in values)
        lines.append(f"{ident} = np.array([{body}])  # {name}")
    if len(idents) >= _PLOT_MIN_COLUMNS:
        x_ident, (x_name, _) = idents[0], cols[0]
        lines += ["", "plt.figure()"]
        for ident, (name, _) in zip(idents[1:], cols[1:]):
            lines.append(f"plt.plot({x_ident}, {ident}, label={name!r})")
        lines += [
            f"plt.xlabel({x_name!r})",
            "plt.legend()",
            "plt.grid(True)",
            "plt.show()",
        ]
    return "\n".join(lines) + "\n"


def to_c_array(data: Dataset) -> str:
    """One ``double[]`` per column with an ``N`` length macro."""
    cols = _columns(data)
    idents = _safe_idents([name for name, _ in cols])
    lines = [
        "/* Measurement data — C/C++ arrays */",
        "#include <math.h>  /* for NAN */",
        f"#define N {_row_count(cols)}",
        "",
    ]
    for ident, (name, values) in zip(idents, cols):
        body = ", ".join(_num(v, "NAN") for v in values)
        lines.append(f"double {ident}[N] = {{ {body} }}; /* {name} */")
    return "\n".join(lines) + "\n"


def to_matlab(data: Dataset) -> str:
    """One row vector per column."""
    cols = _columns(data)
    idents = _safe_idents([name for name, _ in cols])
    lines = ["% Measurement data — MATLAB vectors", ""]
    for ident, (name, values) in zip(idents, cols):
        body = " ".join(_num(v, "NaN") for v in values)
        lines.append(f"{ident} = [{body}]; % {name}")
    return "\n".join(lines) + "\n"


# =============================================================================
# XLSX (minimal OOXML writer — stdlib only)
# =============================================================================

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<Types xmlns="
    '"http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType='
    '"application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    '.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
    '"application/vnd.openxmlformats-officedocument.spreadsheetml'
    '.worksheet+xml"/>'
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<Relationships xmlns="
    '"http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type='
    '"http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    '/officeDocument" Target="xl/workbook.xml"/>'
    "</Relationships>"
)

_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<workbook xmlns="
    '"http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006'
    '/relationships">'
    '<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)

_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    "<Relationships xmlns="
    '"http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type='
    '"http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    '/worksheet" Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)


def _col_letter(idx: int) -> str:
    """0-based column index -> spreadsheet column letters (A, B, ... AA)."""
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sheet_xml(cols: Sequence[tuple[str, list[float]]]) -> str:
    rows: list[str] = []

    header = "".join(
        f'<c r="{_col_letter(c)}1" t="inlineStr">'
        f'<is><t xml:space="preserve">{_xml_escape(name)}</t></is></c>'
        for c, (name, _) in enumerate(cols)
    )
    rows.append(f'<row r="1">{header}</row>')

    for i in range(_row_count(cols)):
        cells = []
        for c, (_, values) in enumerate(cols):
            v = values[i]
            if v is None or not math.isfinite(v):
                continue  # leave the cell blank for nan
            ref = f"{_col_letter(c)}{i + 2}"
            cells.append(f'<c r="{ref}" t="n"><v>{repr(float(v))}</v></c>')
        rows.append(f'<row r="{i + 2}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<worksheet xmlns="
        '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows)}</sheetData>"
        "</worksheet>"
    )


def to_xlsx_bytes(data: Dataset) -> bytes:
    """Serialise *data* into a minimal single-sheet .xlsx workbook."""
    sheet = _sheet_xml(_columns(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("xl/workbook.xml", _WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


# =============================================================================
# Dispatchers
# =============================================================================

_TEXT_GENERATORS = {
    DataFormat.CSV: to_csv,
    DataFormat.PY_PURE: to_pure_python,
    DataFormat.PY_NUMPY: to_numpy_matplotlib,
    DataFormat.C_ARRAY: to_c_array,
    DataFormat.MATLAB: to_matlab,
}


def generate_text(data: Dataset, fmt: DataFormat) -> str:
    """Code/CSV snippet for *fmt* (used for the on-screen preview and Copy)."""
    try:
        return _TEXT_GENERATORS[fmt](data)
    except KeyError:
        raise ValueError(f"{fmt} has no text representation") from None


def generate_bytes(
    data: Dataset,
    fmt: DataFormat,
    csv_options: CsvOptions = DEFAULT_CSV_OPTIONS,
) -> bytes:
    """Encoded file payload for a table-format download (CSV or XLSX)."""
    if fmt is DataFormat.XLSX:
        return to_xlsx_bytes(data)
    if fmt is DataFormat.CSV:
        return to_csv(data, csv_options).encode("utf-8")
    raise ValueError(f"{fmt} is not a downloadable table format")


# =============================================================================
# Export filenames / dataset ordering / zip bundling
# =============================================================================

#: Timestamp suffix appended to exported filenames (filesystem-safe).
_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M"

#: Characters illegal in Windows filenames (superset of POSIX restrictions).
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, fallback: str = "data") -> str:
    """Coerce *name* into a filesystem-safe base name (no extension)."""
    cleaned = _ILLEGAL_FILENAME_CHARS.sub("", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or fallback


def export_filename(
    base: str, fmt: DataFormat, timestamp: datetime | None = None
) -> str:
    """Suggested filename: sanitized base, optional timestamp, extension."""
    name = sanitize_filename(base)
    if timestamp is not None:
        name += f"_{timestamp:{_TIMESTAMP_FMT}}"
    return f"{name}.{SPECS[fmt].extension}"


def ordered_dataset(
    data: Dataset, order: Sequence[str]
) -> dict[str, list[float]]:
    """Copy of *data* with columns from *order* first (those present), then
    any remaining columns in their original order."""
    result: dict[str, list[float]] = {}
    for name in order:
        if name in data:
            result[name] = list(data[name])
    for name, values in data.items():
        if name not in result:
            result[name] = list(values)
    return result


def build_zip(
    entries: Sequence[tuple[str, datetime | None, Dataset]],
    fmt: DataFormat,
    csv_options: CsvOptions = DEFAULT_CSV_OPTIONS,
    include_timestamp: bool = False,
) -> bytes:
    """Bundle ``(name, date, dataset)`` entries into one zip archive.

    Each entry becomes an individual CSV/XLSX file named after its
    (sanitized) name, optionally suffixed with its timestamp; name
    collisions are disambiguated with ``_2``, ``_3``, …
    """
    used: set[str] = set()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, date, dataset in entries:
            ts = date if include_timestamp else None
            filename = export_filename(name, fmt, ts)
            stem, dot, ext = filename.rpartition(".")
            k = 2
            while filename in used:
                filename = f"{stem}_{k}{dot}{ext}"
                k += 1
            used.add(filename)
            zf.writestr(filename, generate_bytes(dataset, fmt, csv_options))
    return buf.getvalue()
