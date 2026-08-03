"""
Compatibility wrapper module exposing export_csv and import_csv in the short
`csv` module path.
"""

from __future__ import annotations

from .csv_utils import export_csv, import_csv

__all__ = ["export_csv", "import_csv"]
