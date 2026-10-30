# =============================================================================
# FILE: app/services/bank_statement_generator.py
# DESCRIPTION: Generate cockpit-grade PDF bank statements with logo resolution.
#              Safe logging, CSV-driven logo lookup, and CLI harness included.
#              No Flask app context is pushed at import time; safe for CLI/WSGI.
# =============================================================================

from __future__ import annotations

import csv
import logging
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context
from fpdf import FPDF

# Path to FDIC branch attributes CSV (operator-visible, no import-time I/O).
BRANCH_CSV_PATH = (
    Path(__file__).parent.parent / "data" / "CSV_ATTRIBUTES_BRANCHES.csv"
)


# -------------------------------------------------------------------------
# Logging helpers (safe inside/outside Flask context)
# -------------------------------------------------------------------------
def _log_debug(msg: str) -> None:
    if has_app_context():
        current_app.logger.debug(msg)
    else:
        logging.debug(msg)


def _log_warning(msg: str) -> None:
    if has_app_context():
        current_app.logger.warning(msg)
    else:
        logging.warning(msg)


def _log_error(msg: str) -> None:
    if has_app_context():
        current_app.logger.error(msg)
    else:
        logging.error(msg)


# -------------------------------------------------------------------------
# Logo resolution helpers
# -------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _load_branch_bank_names() -> set[str]:
    """Load unique legal bank names from the FDIC branch attributes CSV."""
    try:
        if not BRANCH_CSV_PATH.exists():
            _log_warning(
                f"[LOGO_RESOLVE] Branch CSV not found: {BRANCH_CSV_PATH}"
            )
            return set()

        with BRANCH_CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            names = {
                value.strip()
                for row in reader
                if (value := row.get("NM_LGL")) is not None and value.strip()
            }

        _log_debug(
            f"[LOGO_RESOLVE] Loaded {len(names)} bank names from branch CSV"
        )
        return names
    except Exception as e:
        _log_warning(f"[LOGO_RESOLVE] Could not load branch CSV: {e}")
        return set()


def _normalize_filename(name: str) -> str:
    """Normalize a bank name to match logo filenames in static/logos."""
    return "".join(character for character in name.lower() if character.isalnum())


def _resolve_static_base(static_folder: str | None) -> Path:
    """Return the logos directory for an explicit or current Flask static folder."""
    base_static = static_folder

    if base_static is None and has_app_context():
        base_static = current_app.static_folder

    return Path(base_static or "static") / "logos"


def _logo_path(bank_name: str, static_folder: str | None = None) -> str:
    """Resolve the logo path for a bank name from static/logos."""
    base = _resolve_static_base(static_folder)
    _log_debug(
        f"[LOGO_RESOLVE] Resolving logo for bank: '{bank_name}' (base={base})"
    )

    candidates = {
        "Piermont Bank": base / "PiermontBankLogo.png",
        "Found Bank": base / "FoundBankLogo.png",
    }

    candidate = candidates.get(bank_name)
    if candidate is not None and candidate.exists():
        _log_debug(f"[LOGO_RESOLVE] Using hardcoded logo: {candidate}")
        return str(candidate)

    if bank_name in _load_branch_bank_names():
        normalized = _normalize_filename(bank_name)
        for extension in (".png", ".jpg", ".jpeg", ".webp"):
            logo_file = base / f"{normalized}{extension}"
            if logo_file.exists():
                _log_debug(f"[LOGO_RESOLVE] Found CSV match: {logo_file}")
                return str(logo_file)

    fallback_logo = base / "NoLogo.png"
    if fallback_logo.exists():
        _log_warning(
            f"[LOGO_RESOLVE] No match found for '{bank_name}', "
            f"using fallback: {fallback_logo}"
        )
        return str(fallback_logo)

    _log_error(
        f"[LOGO_RESOLVE] No logo found for '{bank_name}' and fallback "
        f"missing in {base}!"
    )
    return ""


# -------------------------------------------------------------------------
# PDF rendering
# -------------------------------------------------------------------------
def _safe_amount(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError, OverflowError):
        return "0.00"


def _safe_text(value: Any, default: str = "") -> str:
    try:
        text = str(value).strip()
        return text.encode("latin-1", "replace").decode("latin-1") if text else default
    except Exception:
        return default


def render_branded_bank_statement_pdf(
    bank_name: str,
    account_number: str,
    transactions: list[dict[str, Any]],
    static_folder: str | None = None,
) -> bytes:
    """Generate a PDF bank statement for the given bank, account, and transactions."""
    pdf = FPDF()
    pdf.add_page()

    logo = _logo_path(bank_name, static_folder=static_folder)
    if logo:
        try:
            pdf.image(logo, x=10, y=8, w=33)
        except Exception as e:
            _log_warning(f"[PDF] Failed to place logo '{logo}': {e}")

    pdf.set_font("Arial", "B", 16)
    pdf.cell(
        0,
        10,
        _safe_text(bank_name, "Bank Statement"),
        ln=True,
        align="C",
    )

    pdf.set_font("Arial", size=12)
    pdf.cell(
        0,
        10,
        f"Account Number: {_safe_text(account_number, 'N/A')}",
        ln=True,
    )
    pdf.cell(
        0,
        10,
        f"Statement Date: {datetime.now().strftime('%Y-%m-%d')}",
        ln=True,
    )

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(60, 10, "Date", border=1)
    pdf.cell(80, 10, "Description", border=1)
    pdf.cell(40, 10, "Amount", border=1, ln=True)

    pdf.set_font("Arial", size=12)
    for transaction in transactions:
        pdf.cell(
            60,
            10,
            _safe_text(transaction.get("date"), "—"),
            border=1,
        )
        pdf.cell(
            80,
            10,
            _safe_text(transaction.get("description"), "—"),
            border=1,
        )
        pdf.cell(
            40,
            10,
            _safe_amount(transaction.get("amount")),
            border=1,
            ln=True,
        )

    try:
        output = pdf.output(dest="S")
        if isinstance(output, str):
            return output.encode("latin-1")
        return bytes(output)
    except Exception as e:
        _log_error(f"[PDF] Failed to generate PDF bytes: {e}")
        return b""


# -------------------------------------------------------------------------
# TEST COMPATIBILITY WRAPPER
# -------------------------------------------------------------------------
def render_bank_statement_pdf(csv_path: str, pdf_path: str) -> None:
    """Read a CSV file and write a simple PDF listing its rows."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                pdf.cell(
                    0,
                    10,
                    _safe_text(" | ".join(row)),
                    ln=True,
                )
    except OSError as e:
        _log_warning(f"[PDF] Could not read CSV '{csv_path}': {e}")

    pdf.output(pdf_path)


if __name__ == "__main__":
    pass
