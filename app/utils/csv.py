"""
Compatibility wrapper module exposing export_csv in the short "csv" module path.

Some code/tests import from app.utils.csv; others import app.utils.csv_utils.
We provide identical implementation in both modules to avoid inconsistent behavior.
"""

from __future__ import annotations

# Import implementation from csv_utils to keep single source of truth if you prefer.
