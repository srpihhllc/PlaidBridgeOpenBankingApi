"""
CSV helper utilities.

Provides a flexible export_csv function that accepts either:
- output_path (str / pathlib.Path) as a destination path (keyword)
- file (a file-like object opened for text write)
- or no destination (returns CSV string)

The function is tolerant and documents return behavior.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence


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
    dialect: str = "excel",
    extrasaction: str = "ignore",
    newline: str = "",
    encoding: str = "utf-8",
) -> Optional[str]:
    """
    Export a sequence of mapping rows (list of dict-like objects) to CSV.

    Parameters
    - data: sequence of dict-like rows. Order of keys defines column order if headers not provided.
    - output_path: optional path (str or Path). If given, CSV is written to this path.
    - file: optional file-like object opened for text write. If provided, CSV will be written to it.
            If both output_path and file are provided, output_path takes precedence.
    - headers: optional sequence of column names to use. If not provided, derived from first row.
    - dialect: csv dialect name (default "excel").
    - extrasaction: how to handle extra keys when using csv.DictWriter (default "ignore").
    - newline / encoding: used when opening a file path.

    Returns
    - If output_path is provided: returns the path string (str(output_path))
    - If file is provided (and output_path not provided): returns None
    - If neither provided: returns the CSV content as a string.
    """
    rows = list(data or [])
    cols = _normalize_headers(rows, headers)

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
