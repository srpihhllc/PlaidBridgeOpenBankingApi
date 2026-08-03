"""
CSV helper utilities.

Provides flexible export_csv and import_csv functions.

export_csv accepts either:
- output_path (str / pathlib.Path) as a destination path (keyword)
- file (a file-like object opened for text write)
- or no destination (returns CSV string)

import_csv accepts:
- source (str / pathlib.Path or file-like object)
- returns list of dict rows with automatic cross-platform newline handling

The functions are cross-platform safe (Windows/Linux/macOS) and handle line endings reliably.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO, Union

__all__ = ["export_csv", "import_csv"]


def _normalize_headers(
    data: Sequence[Mapping[str, Any]], 
    headers: Optional[Sequence[str]] = None
) -> List[str]:
    """
    Determine CSV headers:
    - If explicit headers provided, use them as a list.
    - Otherwise, aggregate keys from ALL rows in data (preserving insertion order).
    """
    if headers is not None:
        return list(headers)

    seen_keys: Dict[str, None] = {}
    for row in data:
        if isinstance(row, Mapping):
            for key in row.keys():
                seen_keys[key] = None

    return list(seen_keys.keys())


def _write_csv_to_stream(
    stream: TextIO,
    data: Sequence[Mapping[str, Any]],
    cols: List[str],
    dialect: str = "excel",
    extrasaction: str = "ignore",
    lineterminator: Optional[str] = None,
) -> None:
    """Internal helper to write formatted CSV data to any text stream."""
    writer_kwargs: Dict[str, Any] = {
        "dialect": dialect,
        "extrasaction": extrasaction,
    }
    if lineterminator is not None:
        writer_kwargs["lineterminator"] = lineterminator

    writer = csv.DictWriter(stream, fieldnames=cols, **writer_kwargs)
    if cols:
        writer.writeheader()

    for row in data:
        formatted_row = {
            k: ("" if row.get(k) is None else str(row.get(k))) 
            for k in cols
        }
        writer.writerow(formatted_row)


def export_csv(
    data: Sequence[Mapping[str, Any]],
    output_path: Optional[Union[str, Path]] = None,
    file: Optional[TextIO] = None,
    headers: Optional[Sequence[str]] = None,
    dialect: str = "excel",
    extrasaction: str = "ignore",
    newline: str = "",
    encoding: str = "utf-8",
    lineterminator: Optional[str] = None,
) -> Optional[str]:
    """
    Export a sequence of mapping rows (list of dict-like objects) to CSV.

    Parameters
    ----------
    data : Sequence[Mapping[str, Any]]
        Sequence of dict-like rows.
    output_path : Optional[Union[str, Path]]
        Destination path. If provided, CSV is written to this path.
    file : Optional[TextIO]
        File-like object opened for text write.
        Note: output_path takes precedence if both are provided.
    headers : Optional[Sequence[str]]
        Explicit column headers. If None, derived automatically from row keys.
    dialect : str
        CSV dialect name (default "excel").
    extrasaction : str
        How to handle extra keys when using csv.DictWriter (default "ignore").
    newline : str
        Newline handling when opening output_path (default "").
    encoding : str
        File encoding (default "utf-8").
    lineterminator : Optional[str]
        Explicit line terminator override (e.g. "\\n" or "\\r\\n").

    Returns
    -------
    Optional[str]
        - str(output_path) if output_path is provided.
        - None if file object is provided (and no output_path).
        - CSV content string if neither output_path nor file is provided.
    """
    rows = list(data or [])
    cols = _normalize_headers(rows, headers)

    # Destination 1: Write to file path
    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding=encoding, newline=newline) as fh:
            _write_csv_to_stream(
                fh, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
            )
        return str(p)

    # Destination 2: Write to provided file handle
    if file is not None:
        _write_csv_to_stream(
            file, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
        )
        return None

    # Destination 3: Return string representation
    sio = io.StringIO()
    _write_csv_to_stream(
        sio, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
    )
    return sio.getvalue()


def import_csv(
    source: Union[str, Path, TextIO],
    encoding: str = "utf-8",
    dialect: str = "excel",
    **kwargs: Any,
) -> List[Dict[str, str]]:
    """
    Import CSV data from a file path or file-like object into a list of dicts.

    Parameters
    ----------
    source : Union[str, Path, TextIO]
        File path or text stream object.
    encoding : str
        File encoding (default "utf-8").
    dialect : str
        CSV dialect (default "excel").

    Returns
    -------
    List[Dict[str, str]]
        List of dictionaries corresponding to CSV rows.
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            return []

        # Read bytes and decode explicitly to bypass OS-level newline corruption
        # This prevents \r\n from turning into \r\r\n on Windows text files
        raw = p.read_bytes().decode(encoding)
    elif hasattr(source, "read"):
        raw = source.read()
    else:
        raw = str(source)

    if not raw or not raw.strip():
        return []

    # Normalize line endings strictly to \n
    cleaned = raw.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    
    # Strip BOM and any leading blank lines
    cleaned = cleaned.lstrip("\ufeff").lstrip("\n")

    # Re-parse using StringIO (newline="" is strictly required by the csv module)
    fh = io.StringIO(cleaned, newline="")
    reader = csv.DictReader(fh, dialect=dialect, **kwargs)
    
    results = []
    for row in reader:
        # csv.DictReader will sometimes yield fully blank rows as empty strings
        # Keep the row only if it contains at least one non-empty value
        if any(str(v).strip() for v in row.values() if v is not None):
            results.append(dict(row))
            
    return results
