# =============================================================================
# FILE: app/services/pdf_parser.py
# DESCRIPTION: Functions for extracting bank statement data from PDF files.
# =============================================================================

"""
PDF parsing utilities for extracting structured data from bank statements.

This module provides a safe, typed `parse_pdf()` function that returns
an empty list for missing, unreadable, or invalid PDF files. It is designed
to be extended later with real PDF parsing logic (pdfminer, pdfplumber, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_pdf(path: str | Path) -> list[Any]:
    """
    Parse a PDF file and return extracted structured data.

    Current stub implementation:
    - Returns [] if the file does not exist
    - Returns [] if the file is unreadable or not a valid PDF
    - Designed to be extended with real parsing logic later
    """
    pdf_path = Path(path)

    if not pdf_path.exists() or not pdf_path.is_file():
        return []

    try:
        # Placeholder for real PDF parsing logic
        # Example future implementation:
        #   with pdfplumber.open(pdf_path) as pdf:
        #       ...
        return []
    except Exception:
        # Fail safe: never crash the caller
        return []
