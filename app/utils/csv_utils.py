#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/csv_utils.py

"""
CSV helper utilities.

Provides a flexible export_csv function that accepts destination paths,
file objects, or returns raw string content, alongside re-exported service
helpers (import_csv, save_statements_as_csv, generate_pdf_from_csv) for backward compatibility.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from app.services.csv_utils import (
    generate_pdf_from_csv,
    import_csv,
    save_statements_as_csv,
)


def _normalize_headers(
    data: Sequence[Mapping[str, Any]], headers: Optional[Sequence[str]] = None
) -> List[str]:
    """
    Determine CSV headers:
    - If headers provided, use them.
    - Otherwise, use keys from first item in data (preserve insertion order).
    """
    if headers:
        return list(headers)
    if not data:
        return []
    return list(data[0].keys())


def export_csv(
    data: Sequence[Mapping[str, Any]],
    output_path: Optional[str | Path] = None,
    file: Optional[Any] = None,
    headers: Optional[Sequence[str]] = None,
    columns: Optional[Sequence[str]] = None,
    dialect: str = "excel",
    extrasaction: str = "ignore",
    newline: str = "",
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    Export a sequence of mapping rows (list of dict-like objects) to CSV string/file.

    Parameters
    - data: sequence of dict-like rows. Order of keys defines column order if headers not provided.
    - output_path: optional path (str or Path). If given, CSV is written to this path.
    - file: optional file-like object opened for text write.
    - headers / columns: optional sequence of column names to use.
    - dialect: csv dialect name (default "excel").
    - extrasaction: how to handle extra keys when using csv.DictWriter (default "ignore").
    - newline / encoding: used when opening a file path.

    Returns
    - If output_path is provided: returns the path string (str(output_path))
    - If file is provided (and output_path not provided): returns None
    - If neither provided: returns the CSV content as a string.
    """
    effective_headers = headers if headers is not None else columns
    rows = list(data or [])
    cols = _normalize_headers(rows, effective_headers)

    # Write to filesystem path if requested
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding=encoding, newline=newline) as fh:
            writer = csv.DictWriter(
                fh, fieldnames=cols, dialect=dialect, extrasaction=extrasaction
            )
            if cols:
                writer.writeheader()
            for r in rows:
                writer.writerow(
                    {
                        k: ("" if r.get(k) is None else str(r.get(k)))
                        for k in cols
                    }
                )
        return str(p)

    # Write to provided file-like object
    if file is not None:
        writer = csv.DictWriter(
            file, fieldnames=cols, dialect=dialect, extrasaction=extrasaction
        )
        if cols:
            writer.writeheader()
        for r in rows:
            writer.writerow(
                {k: ("" if r.get(k) is None else str(r.get(k))) for k in cols}
            )
        return None

    # No destination: return CSV string
    sio = io.StringIO()
    writer = csv.DictWriter(
        sio, fieldnames=cols, dialect=dialect, extrasaction=extrasaction
    )
    if cols:
        writer.writeheader()
    for r in rows:
        writer.writerow(
            {k: ("" if r.get(k) is None else str(r.get(k))) for k in cols}
        )
    return sio.getvalue()


__all__ = [
    "export_csv",
    "import_csv",
    "save_statements_as_csv",
    "generate_pdf_from_csv",
]