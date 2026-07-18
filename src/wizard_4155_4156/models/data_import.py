"""
models/data_import.py
---------------------
Pure-Python (Qt-free) parsing/validation of external measurement files.

The import feature turns user-supplied CSV files into the canonical ordered
``{var_name: [values]}`` dataset shape (the same shape
``db.assembler.fetch_result_to_execution`` consumes).  Each file becomes one
execution named after the file stem; all files of one import must share the
same ordered header (the "standard" variable set, defined by the first file
that parses cleanly).

This module never touches the database — callers pass in ``taken_names``
(execution names that already exist) so name collisions surface as per-file
errors alongside the format ones.  No PySide6 imports — unit-testable without
a GUI.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: Sentinel delimiter: split each line on any run of spaces and/or tabs.
WHITESPACE_DELIMITER = " "


@dataclass(frozen=True)
class CsvOptions:
    """User-selected CSV dialect options.

    ``decimal`` is the character the files use as decimal separator; when it
    is ``","`` the delimiter may only also be a comma if a quote character is
    set (``data_export.csv_dialect_is_valid`` — the dialog enforces this;
    unquoted, every row would be unparseable).  With the whitespace delimiter
    the quote character is ignored (columns are plain tokens).
    """

    delimiter: str = ","  # "," | ";" | "\t" | WHITESPACE_DELIMITER
    quotechar: Optional[str] = '"'  # '"' | "'" | None (None ⇒ no quoting)
    decimal: str = "."  # "." | ","


@dataclass(frozen=True)
class FileImportResult:
    """Outcome for one file: either ``data`` or a human-readable ``error``."""

    path: str
    stem: str  # file name without extension — the execution name
    error: Optional[str]  # None ⇒ valid
    data: Optional[dict[str, list[float]]]  # ordered {var: values}


@dataclass(frozen=True)
class ImportResult:
    """Outcome for a whole selection of files."""

    files: list[FileImportResult]
    #: The "standard" variable set — ordered headers of the first cleanly
    #: parsed file; None when no file parsed cleanly.
    variables: Optional[list[str]]

    @property
    def all_ok(self) -> bool:
        return bool(self.files) and all(f.error is None for f in self.files)


def parse_import_files(
    paths: Sequence[str],
    options: CsvOptions,
    taken_names: Collection[str] = (),
    expected_variables: Optional[Sequence[str]] = None,
) -> ImportResult:
    """Parse and cross-validate *paths* into per-file results.

    Files are processed in order; the first file that parses cleanly defines
    the standard variable list every other file must match (same names, same
    order).  When ``expected_variables`` is given (importing into an existing
    setup) that list is the standard instead, and every file must match it.
    A file also fails when its stem duplicates an earlier file's or appears
    in ``taken_names``.
    """
    files: list[FileImportResult] = []
    variables: Optional[list[str]] = (
        list(expected_variables) if expected_variables else None
    )
    seen_stems: set[str] = set()

    for path in paths:
        stem = Path(path).stem
        error, data = _parse_one(path, options)

        if error is None and variables is not None and data is not None:
            headers = list(data.keys())
            if headers != variables:
                error = (
                    f"variables do not match — expected "
                    f"{', '.join(variables)}; found {', '.join(headers)}"
                )
                data = None

        if error is None:
            if stem in seen_stems:
                error = f"duplicate file name '{stem}' in the selection"
                data = None
            elif stem in taken_names:
                error = (
                    f"an execution named '{stem}' already exists "
                    f"in this project"
                )
                data = None

        if error is None and variables is None and data is not None:
            variables = list(data.keys())
        seen_stems.add(stem)
        files.append(FileImportResult(path, stem, error, data))

    return ImportResult(files=files, variables=variables)


class _ParseError(Exception):
    """Internal: carries a per-file, human-readable failure reason."""


def _parse_one(
    path: str, options: CsvOptions
) -> tuple[Optional[str], Optional[dict[str, list[float]]]]:
    """Parse one CSV file → ``(error, data)`` with exactly one non-None."""
    try:
        return None, _rows_to_data(_read_rows(path, options), options.decimal)
    except _ParseError as exc:
        return str(exc), None


def _read_rows(path: str, options: CsvOptions) -> list[list[str]]:
    try:
        # utf-8-sig strips a BOM if present; newline="" is the csv-module
        # contract and keeps CRLF files working on every platform.
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            if options.delimiter == WHITESPACE_DELIMITER:
                # str.split() collapses runs of spaces/tabs into one
                # separator; quoting does not apply to whitespace tables.
                return [line.split() for line in fh.read().splitlines()]
            return list(
                csv.reader(
                    fh,
                    delimiter=options.delimiter,
                    quotechar=options.quotechar or '"',
                    quoting=(
                        csv.QUOTE_NONE
                        if options.quotechar is None
                        else csv.QUOTE_MINIMAL
                    ),
                )
            )
    except OSError as exc:
        raise _ParseError(
            f"cannot read file: {exc.strerror or exc}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise _ParseError("file is not valid UTF-8 text") from exc
    except csv.Error as exc:
        raise _ParseError(f"malformed CSV: {exc}") from exc


def _rows_to_data(
    rows: list[list[str]], decimal: str
) -> dict[str, list[float]]:
    if not rows:
        raise _ParseError("file is empty")

    header = [cell.strip() for cell in rows[0]]
    seen: set[str] = set()
    for i, name in enumerate(header, start=1):
        if not name:
            raise _ParseError(f"empty column name in header (column {i})")
        if name in seen:
            raise _ParseError(f"duplicate column name '{name}'")
        seen.add(name)

    columns: list[list[float]] = [[] for _ in header]
    data_rows = 0
    for row_no, row in enumerate(rows[1:], start=2):
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue  # fully-blank line (e.g. trailing newline)
        if len(cells) != len(header):
            raise _ParseError(
                f"row {row_no} has {len(cells)} cell(s), "
                f"expected {len(header)}"
            )
        for idx, cell in enumerate(cells):
            if cell == "":
                # The app's own CSV export writes non-finite points as blank
                # cells; nan round-trips to NULL in the database.
                columns[idx].append(math.nan)
                continue
            try:
                columns[idx].append(
                    float(cell.replace(decimal, "."))
                    if decimal != "."
                    else float(cell)
                )
            except ValueError:
                raise _ParseError(
                    f"non-numeric value '{cell}' at row {row_no}, "
                    f"column '{header[idx]}'"
                ) from None
        data_rows += 1

    if data_rows == 0:
        raise _ParseError("no data rows (only a header)")
    return dict(zip(header, columns))
