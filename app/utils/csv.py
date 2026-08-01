"""
Compatibility wrapper module exposing export_csv and import_csv in the short
`csv` module path.

Some code/tests import from `app.utils.csv`; others import `app.utils.csv_utils`.
This wrapper re‑exports both functions so both import paths behave identically.
"""

from __future__ import annotations

# Re‑export the real implementations from csv_utils
from .csv_utils import export_csv, import_csv
