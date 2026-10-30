"""
CSV helper utilities.

Provides a flexible export_csv function that accepts destination paths,
file objects, or returns raw string content, alongside re-exported service
helpers (import_csv, save_statements_as_csv, generate_pdf_from_csv) for
backward compatibility.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Sequence


from app.services.csv_utils import (
    generate_pdf_from_csv,
    import_csv,
    save_statements_as_csv,
)


def _normalize_headers(
    data: Sequence[Any],
    headers: Optional[Sequence[str]] = None,
) -> list[str]:
    """Determine CSV headers from the explicit headers or first data row."""
    if headers:
        return list(headers)
    if not data:
        return []

    first = data[0]
    if isinstance(first, Mapping):
        return [str(key) for key in first.keys()]
    return [str(index) for index in range(len(first))]


def _format_row(row: Any, columns: Sequence[str]) -> Any:
    """Convert a mapping or sequence row to CSV-compatible values."""
    if isinstance(row, Mapping):
        return {
            column: "" if row.get(column) is None else str(row.get(column))
            for column in columns
        }

    return ["" if value is None else str(value) for value in row]


def _write_rows(
    destination: Any,
    rows: Sequence[Any],
    columns: Sequence[str],
    *,
    dialect: str,
    extrasaction: Literal["raise", "ignore"],
) -> None:
    """Write rows using a dictionary writer or a standard CSV writer."""
    first_row = rows[0] if rows else None

    if columns and isinstance(first_row, Mapping):
        dict_writer = csv.DictWriter(
            destination,
            fieldnames=list(columns),
            dialect=dialect,
            extrasaction=extrasaction,
        )
        dict_writer.writeheader()
        for row in rows:
            formatted_row = _format_row(row, columns)
            dict_writer.writerow(formatted_row)
    else:
        row_writer = csv.writer(destination, dialect=dialect)
        for row in rows:
            formatted_row = _format_row(row, columns)
            row_writer.writerow(formatted_row)


def export_csv(
    data: Sequence[Any],
    output_path: Optional[str | Path] = None,
    file: Optional[Any] = None,
    headers: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    dialect: str = "excel",
    extrasaction: Literal["raise", "ignore"] = "ignore",
    newline: str = "",
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    Export mapping or sequence rows to a CSV string, file, or path.

    If ``output_path`` is provided, return its string representation. If
    ``file`` is provided, write to it and return ``None``. Otherwise, return
    the CSV content as a string.
    """
    effective_headers = headers if headers is not None else columns
    rows = list(data)
    normalized_headers = _normalize_headers(rows, effective_headers)

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding=encoding, newline=newline) as output_file:
            _write_rows(
                output_file,
                rows,
                normalized_headers,
                dialect=dialect,
                extrasaction=extrasaction,
            )

        return str(path)

    if file is not None:
        _write_rows(
            file,
            rows,
            normalized_headers,
            dialect=dialect,
            extrasaction=extrasaction,
        )
        return None

    output = io.StringIO()
    _write_rows(
        output,
        rows,
        normalized_headers,
        dialect=dialect,
        extrasaction=extrasaction,
    )
    return output.getvalue()


__all__ = [
    "export_csv",
    "import_csv",
    "save_statements_as_csv",
    "generate_pdf_from_csv",
]