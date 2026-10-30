# =============================================================================
# FILE: app/utils_legacy.py
# DESCRIPTION: Utility functions for monitoring, loan analysis, fraud detection,
# PDF generation, and PDF merging.
# =============================================================================

from __future__ import annotations

import base64
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, cast

import requests
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter


# ==========================
# PythonAnywhere API Monitoring
# ==========================


def get_pythonanywhere_cpu_quota() -> dict[str, Any]:
    """Fetch CPU quota info from the PythonAnywhere API."""
    username = "srpihhllc"
    token = os.getenv("API_TOKEN")

    response = requests.get(
        f"https://www.pythonanywhere.com/api/v0/user/{username}/cpu/",
        headers={"Authorization": f"Token {token}"} if token else {},
        timeout=10,
    )

    if response.status_code == 200:
        # requests.Response.json() is typed as Any. Cast it to the
        # function's declared return type for mypy.
        return cast(dict[str, Any], response.json())

    return {
        "error": f"Unexpected status {response.status_code}",
        "details": response.content.decode("utf-8", errors="replace"),
    }


# ==========================
# Loan & Financial Utilities
# ==========================


def analyze_loan_agreement(agreement_text: str) -> dict[str, str]:
    """Flag agreements containing terms that may be unethical."""
    unethical_terms: Sequence[str] = (
        "hidden fees",
        "predatory interest rates",
        "undisclosed penalties",
    )

    text = agreement_text.lower()

    for term in unethical_terms:
        if term in text:
            return {
                "status": "flagged",
                "reason": f"Contains unethical term: {term}",
            }

    return {"status": "approved"}


def detect_fraudulent_transaction(description: str, amount: float) -> bool:
    """Flag potentially fraudulent transactions based on patterns."""
    suspicious_terms: Sequence[str] = (
        "unexpected large withdrawal",
        "account drained",
        "unauthorized payment",
    )

    desc = description.lower()

    if amount > 5000:
        return True

    return any(term in desc for term in suspicious_terms)


def execute_smart_contract(loan_agreement_id: int) -> dict[str, Any]:
    """
    Simulate smart contract automation for a loan agreement.

    Load models lazily to avoid circular imports.
    """
    from app.extensions import db
    from app.models.loan_agreement import LoanAgreement

    agreement: LoanAgreement | None = db.session.get(
        LoanAgreement,
        loan_agreement_id,
    )

    if agreement is not None and agreement.status == "active":
        agreement.status = "under_contract"
        db.session.commit()

        return {
            "contract_status": "executed",
            "loan_agreement_id": loan_agreement_id,
        }

    return {
        "contract_status": "failed",
        "reason": "Invalid agreement or status.",
    }


def notify_authorities(issue_details: str) -> dict[str, str]:
    """Send a fraud alert to compliance officers."""
    print(f"Fraud Alert: {issue_details}")
    return {"status": "notified"}


def time_since(dt: datetime) -> str:
    """Return a compact human-readable delta, such as '5m', '2h', or '3d'."""
    delta = datetime.now(timezone.utc) - dt

    if delta.days > 0:
        return f"{delta.days}d"

    if delta.seconds > 3600:
        return f"{delta.seconds // 3600}h"

    if delta.seconds > 60:
        return f"{delta.seconds // 60}m"

    return f"{delta.seconds}s"


# ==========================
# PDF Generation Utilities
# ==========================


def create_bank_statement(
    data: Mapping[str, Any],
    signature_base64: str | None = None,
) -> BytesIO:
    """Generate a bank statement PDF and return it as a BytesIO stream."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header and metadata
    pdf.cell(200, 10, "Bank Statement", ln=True, align="C")
    pdf.cell(
        200,
        10,
        f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        ln=True,
        align="C",
    )
    pdf.ln(10)

    # Account details
    pdf.cell(
        100,
        10,
        f"Account Holder: {data.get('name', '')}",
        ln=True,
    )
    pdf.cell(
        100,
        10,
        f"Account Number: {data.get('account_number', '')}",
        ln=True,
    )
    pdf.ln(5)
    pdf.cell(
        100,
        10,
        f"Balance: ${data.get('balance', 0)}",
        ln=True,
    )
    pdf.ln(10)

    # Transactions
    pdf.cell(200, 10, "Transactions:", ln=True)

    transactions = data.get("transactions", [])
    if isinstance(transactions, Iterable) and not isinstance(
        transactions, (str, bytes, Mapping)
    ):
        for txn in transactions:
            if not isinstance(txn, Mapping):
                continue

            date_str = txn.get("date", "")
            desc = txn.get("description", "")
            amount = txn.get("amount", 0)
            line = f"{date_str} | {desc} | ${amount}"
            pdf.cell(200, 10, line, ln=True)

    # Optional signature
    if signature_base64:
        sig_filename = "signature.png"
        try:
            sig_data = base64.b64decode(signature_base64)
            with open(sig_filename, "wb") as signature_file:
                signature_file.write(sig_data)

            pdf.ln(20)
            pdf.image(
                sig_filename,
                x=10,
                y=pdf.get_y(),
                w=40,
            )
        except Exception as error:
            print("Error processing signature:", error)
        finally:
            if os.path.exists(sig_filename):
                os.remove(sig_filename)

    # PyFPDF returns a Latin-1 string when using dest="S".
    pdf_data = pdf.output(dest="S")
    if isinstance(pdf_data, str):
        pdf_bytes = pdf_data.encode("latin-1")
    else:
        pdf_bytes = bytes(pdf_data)

    pdf_stream = BytesIO(pdf_bytes)
    pdf_stream.seek(0)
    return pdf_stream


# ==========================
# PDF Processing & Merging Utility
# ==========================


def merge_pdfs(
    pdf_list: Iterable[BytesIO | str | os.PathLike[str]],
) -> BytesIO:
    """Combine PDF streams and filesystem paths into one PDF."""
    writer = PdfWriter()

    for pdf_file in pdf_list:
        if isinstance(pdf_file, BytesIO):
            reader = PdfReader(pdf_file)
        else:
            reader = PdfReader(str(pdf_file))

        for page in reader.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output
