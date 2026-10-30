# =============================================================================
# FILE: app/services/csv_utils.py
# DESCRIPTION: Dependency-free CSV import/export helpers for tests and
#              lightweight services. Includes error handling, lazy row
#              iteration, and structured logging.
# =============================================================================

"""Dependency-free CSV import/export helpers for tests and lightweight services."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Optional, Sequence, TypeAlias

logger = logging.getLogger(__name__)

CsvRow: TypeAlias = dict[str, Any] | list[Any] | tuple[Any, ...]


def _derive_columns(
    first_row: CsvRow,
    columns: Optional[Sequence[str]] = None,
) -> list[str]:
    """Return explicit columns, or infer them from the first dictionary row."""
    if columns is not None:
        return list(columns)

    if isinstance(first_row, dict):
        return list(first_row.keys())

    return []


def _as_csv_values(row: CsvRow) -> Iterable[Any]:
    """Return a row's values in CSV order."""
    return row.values() if isinstance(row, dict) else row


def export_csv(
    rows: Iterable[CsvRow],
    columns: Optional[Sequence[str]] = None,
    headers: Optional[Sequence[str]] = None,
    output_path: str | Path | None = None,
) -> bytes:
    """
    Export dictionaries or sequences to CSV bytes.

    Rows are consumed lazily. The returned bytes necessarily contain the
    complete CSV in memory. If ``output_path`` is supplied, the same CSV is
    also written to that path.

    ``columns`` takes precedence over ``headers``. If neither is provided,
    columns are inferred from the first dictionary row. An explicitly empty
    column list disables headers and writes each row's values as-is.
    """
    effective_columns = columns if columns is not None else headers
    iterator = iter(rows)

    try:
        first_row = next(iterator)
    except StopIteration:
        csv_bytes = b""
        if output_path is not None:
            _write_bytes(output_path, csv_bytes)
        return csv_bytes

    cols = _derive_columns(first_row, effective_columns)
    byte_buffer = io.BytesIO()
    text_buffer = io.TextIOWrapper(
        byte_buffer,
        encoding="utf-8",
        newline="",
        write_through=True,
    )

    def write_row(row: CsvRow, writer: csv.DictWriter[str] | None) -> None:
        if writer is None:
            csv.writer(text_buffer, dialect="excel").writerow(
                ["" if value is None else str(value) for value in _as_csv_values(row)]
            )
        elif isinstance(row, dict):
            writer.writerow(
                {
                    column: "" if row.get(column) is None else str(row[column])
                    for column in cols
                }
            )
        else:
            values = row
            writer.writerow(
                {
                    column: (
                        ""
                        if index >= len(values) or values[index] is None
                        else str(values[index])
                    )
                    for index, column in enumerate(cols)
                }
            )

    dict_writer: csv.DictWriter[str] | None = None
    if cols:
        dict_writer = csv.DictWriter(
            text_buffer,
            fieldnames=cols,
            extrasaction="ignore",
            dialect="excel",
        )
        dict_writer.writeheader()

    write_row(first_row, dict_writer)
    for row in iterator:
        write_row(row, dict_writer)

    text_buffer.flush()
    csv_bytes = byte_buffer.getvalue()

    if output_path is not None:
        _write_bytes(output_path, csv_bytes)

    return csv_bytes


def _write_bytes(output_path: str | Path, content: bytes) -> None:
    """Create parent directories and write bytes, logging filesystem errors."""
    path = Path(output_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    except OSError as exc:
        logger.error("Failed to write CSV to %s: %s", output_path, exc)


def _read_source(source: str | bytes | Path) -> str | None:
    """
    Read a CSV source as text.

    A ``Path`` always means a file path; bytes are decoded as UTF-8. A string
    is treated as a path only when it names an existing file, and otherwise
    treated as raw CSV text. Consequently, a raw CSV string identical to an
    existing file path is interpreted as that path.
    """
    try:
        if isinstance(source, Path):
            if not source.is_file():
                return None
            return source.read_text(encoding="utf-8")

        if isinstance(source, bytes):
            return source.decode("utf-8")

        try:
            path = Path(source)
            if path.is_file():
                return path.read_text(encoding="utf-8")
        except OSError:
            # The string may be CSV text that is not a valid filesystem path.
            pass

        return source
    except (OSError, UnicodeDecodeError) as exc:
        logger.error("Failed to read or decode CSV source: %s", exc)
        return None


def import_csv(source: str | bytes | Path) -> list[dict[str, str]]:
    """
    Import CSV data as dictionaries with string values.

    ``source`` may be a ``Path``, UTF-8 bytes, a string path, or raw CSV text.
    The first nonblank row is treated as the header. Extra row values are
    ignored, and missing values are filled with empty strings.
    """
    text = _read_source(source)
    if text is None or not text.strip():
        return []

    reader = csv.reader(io.StringIO(text))
    rows: Iterator[list[str]] = (
        row for row in reader if any(cell.strip() for cell in row)
    )

    try:
        raw_header = next(rows)
    except StopIteration:
        return []
    except csv.Error as exc:
        logger.error("Failed to parse CSV: %s", exc)
        return []

    header = [cell.strip().lstrip("\ufeff") for cell in raw_header]
    result: list[dict[str, str]] = []

    try:
        for row in rows:
            padded = row + [""] * max(0, len(header) - len(row))
            result.append(
                {
                    header[index]: padded[index].strip()
                    for index in range(len(header))
                }
            )
    except csv.Error as exc:
        logger.error("Failed to parse CSV: %s", exc)
        return []

    return result


def save_statements_as_csv(
    statements: list[dict[str, Any]],
    filename: str | Path,
) -> None:
    """Write statement dictionaries to a CSV file."""
    if not statements:
        return

    filepath = Path(filename)
    keys = list(statements[0].keys())

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(statements)
    except OSError as exc:
        logger.error("Error saving CSV file %s: %s", filename, exc)


def generate_pdf_from_csv(csv_path: str | Path, pdf_path: str | Path) -> None:
    """
    Create an empty PDF file at ``pdf_path``.

    ``csv_path`` is unused; this stub supports tests that assert file creation.
    """
    out_path = Path(pdf_path)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"")
    except OSError as exc:
        logger.error("Error generating mock PDF at %s: %s", pdf_path, exc)


__all__ = [
    "export_csv",
    "import_csv",
    "save_statements_as_csv",
    "generate_pdf_from_csv",
]