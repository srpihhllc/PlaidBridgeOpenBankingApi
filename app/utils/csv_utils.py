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
    # Prefer opening the file in text mode with newline="" and letting the
    # csv module handle newline normalization. This avoids platform-specific
    # newline corruption and handles CR/LF correctly.
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            return []

        with p.open("r", encoding=encoding, newline="") as fh:
            reader = csv.DictReader(fh, dialect=dialect, **kwargs)

            results: List[Dict[str, str]] = []
            for row in reader:
                # Normalize header keys (strip BOM if present on the first fieldname)
                normalized: Dict[str, str] = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    nk = k.lstrip("\ufeff")
                    normalized[nk] = "" if v is None else str(v)

                # Keep the row only if at least one non-empty value exists
                if any(val.strip() for val in normalized.values()):
                    results.append(normalized)

            return results

    # If a file-like object was provided, assume it's a text stream compatible
    # with the csv module.
    if hasattr(source, "read"):
        # Ensure we are operating on a text stream. If a bytes stream is given,
        # decode it first.
        try:
            peek = source.read(0)
            # Reset if the stream supports seek
            if hasattr(source, "seek"):
                source.seek(0)
            reader = csv.DictReader(source, dialect=dialect, **kwargs)
        except Exception:
            # Fallback: read bytes and decode
            raw = source.read()
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode(encoding)
            if not raw or not str(raw).strip():
                return []
            fh = io.StringIO(str(raw), newline="")
            reader = csv.DictReader(fh, dialect=dialect, **kwargs)

        results = []
        for row in reader:
            normalized = {}
            for k, v in row.items():
                if k is None:
                    continue
                nk = k.lstrip("\ufeff")
                normalized[nk] = "" if v is None else str(v)

            if any(val.strip() for val in normalized.values()):
                results.append(normalized)

        return results

    # Otherwise coerce to string and parse
    raw = str(source)
    if not raw or not raw.strip():
        return []
    fh = io.StringIO(raw, newline="")
    reader = csv.DictReader(fh, dialect=dialect, **kwargs)

    results = []
    for row in reader:
        normalized = {}
        for k, v in row.items():
            if k is None:
                continue
            nk = k.lstrip("\ufeff")
            normalized[nk] = "" if v is None else str(v)

        if any(val.strip() for val in normalized.values()):
            results.append(normalized)

    return results
