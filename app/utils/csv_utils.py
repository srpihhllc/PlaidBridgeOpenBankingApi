"""
CSV helper utilities.

Provides flexible export_csv and import_csv functions.

export_csv accepts:
- output_path (str / pathlib.Path) destination path
- file (file-like object opened for text write)
- or no destination (returns CSV string)

import_csv accepts:
- source (str / pathlib.Path, bytes, or file-like stream)
- returns list of dict rows with native cross-platform newline handling
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
    """Determine CSV headers from explicit list or by aggregating row keys."""
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
    """Export sequence of mapping rows to file, stream, or CSV string."""
    rows = list(data or [])
    cols = _normalize_headers(rows, headers)

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding=encoding, newline=newline) as fh:
            _write_csv_to_stream(
                fh, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
            )
        return str(p)

    if file is not None:
        _write_csv_to_stream(
            file, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
        )
        return None

    sio = io.StringIO()
    _write_csv_to_stream(
        sio, rows, cols, dialect=dialect, extrasaction=extrasaction, lineterminator=lineterminator
    )
    return sio.getvalue()


def _parse_dict_reader(reader: csv.DictReader) -> List[Dict[str, str]]:
    """
    Helper to consume a DictReader, strip BOMs from header keys, and skip blank rows.
    Note: This deliberately preserves intentional leading/trailing whitespace in header names.
    """
    results = []
    for row in reader:
        normalized = {}
        for k, v in row.items():
            if k is None:
                continue
            # Strip BOM only; preserve intentional leading/trailing whitespace
            nk = str(k).lstrip("\ufeff")
            normalized[nk] = "" if v is None else str(v)
        if any(val.strip() for val in normalized.values()):
            results.append(normalized)
    return results


def import_csv(
    source: Union[str, Path, bytes, TextIO],
    encoding: str = "utf-8",
    dialect: str = "excel",
    **kwargs: Any,
) -> List[Dict[str, str]]:
    """
    Import CSV data from a file path, raw string/bytes, or text stream into a list of dicts.
    """
    # 1. Explicit Path object or path string
    if isinstance(source, (str, Path)):
        try:
            p = Path(source)
            if p.exists() and p.is_file():
                with p.open("r", encoding=encoding, newline="") as fh:
                    return _parse_dict_reader(csv.DictReader(fh, dialect=dialect, **kwargs))
        except OSError:
            # Catch OS errors if `source` is a massive raw CSV string exceeding path length limits
            pass

    # 2. Raw bytes input
    if isinstance(source, (bytes, bytearray)):
        text = source.decode(encoding)
        if not text.strip():
            return []
        fh = io.StringIO(text, newline="")
        return _parse_dict_reader(csv.DictReader(fh, dialect=dialect, **kwargs))

    # 3. File-like stream (TextIO, StringIO, BytesIO)
    if hasattr(source, "read"):
        # Try to use it directly as a text stream, but rewind if needed
        try:
            peek = source.read(0)
            if hasattr(source, "seek"):
                source.seek(0)
            if isinstance(peek, (bytes, bytearray)):
                # Force fallback to decoding if it's a binary stream
                raise ValueError("binary stream")
            return _parse_dict_reader(csv.DictReader(source, dialect=dialect, **kwargs))
        except Exception:
            raw = source.read()
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode(encoding)
            if not raw or not str(raw).strip():
                return []
            fh = io.StringIO(str(raw), newline="")
            return _parse_dict_reader(csv.DictReader(fh, dialect=dialect, **kwargs))

    # 4. Fallback: Raw CSV text string
    raw_str = str(source)
    if not raw_str.strip():
        return []
    fh = io.StringIO(raw_str, newline="")
    return _parse_dict_reader(csv.DictReader(fh, dialect=dialect, **kwargs))
