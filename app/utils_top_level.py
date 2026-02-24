# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils.py_top_level.py

import base64
import datetime
import os
from io import BytesIO

import requests
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter

# ==========================
# PythonAnywhere API Monitoring
# ==========================


def get_pythonanywhere_cpu_quota():
    """Fetch CPU quota info from PythonAnywhere API."""
    username = "srpihhllc"
    token = os.getenv("API_TOKEN")  # Uses environment variable for security

    response = requests.get(
        f"https://www.pythonanywhere.com/api/v0/user/{username}/cpu/",
        headers={"Authorization": f"Token {token}"},
    )

    if response.status_code == 200:
        return response.json()
    else:
        return {
            "error": f"Unexpected status {response.status_code}",
            "details": response.content,
        }


# ==========================
# Loan & Financial Utilities
# ==========================


def analyze_loan_agreement(agreement_text):
    """AI analyzes loan agreements for compliance and ethical standards."""
    unethical_terms = [
        "hidden fees",
        "predatory interest rates",
        "undisclosed penalties",
    ]
    for term in unethical_terms:
        if term in agreement_text.lower():
            return {"status": "flagged", "reason": f"Contains unethical term: {term}"}
    return {"status": "approved"}


def detect_fraudulent_transaction(description, amount):
    """Flags potentially fraudulent transactions based on patterns."""
    suspicious_terms = [
        "unexpected large withdrawal",
        "account drained",
        "unauthorized payment",
    ]
    if amount > 5000 or any(term in description.lower() for term in suspicious_terms):
        return True
    return False


def execute_smart_contract(loan_agreement_id):
    """Simulate smart contract automation for a loan agreement."""
    from app.models import LoanAgreement, db  # Import here to avoid circular imports

    agreement = LoanAgreement.query.get(loan_agreement_id)
    if agreement and agreement.status == "active":
        agreement.status = "under_contract"
        db.session.commit()
        return {"contract_status": "executed", "loan_agreement_id": loan_agreement_id}
    return {"contract_status": "failed", "reason": "Invalid agreement or status."}


# ✅ Fraud Notification Utility
def notify_authorities(issue_details):
    """Sends fraud alerts to compliance officers."""
    print(f"🚨 Fraud Alert: {issue_details}")
    return {"status": "notified"}


def time_since(dt):
    delta = datetime.utcnow() - dt
    if delta.days > 0:
        return f"{delta.days}d"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600}h"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60}m"
    return f"{delta.seconds}s"


# ==========================
# PDF Generation Utilities
# ==========================


def create_bank_statement(data, signature_base64=None):
    """Generates a bank statement PDF using FPDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header and metadata
    pdf.cell(200, 10, "Bank Statement", ln=True, align="C")
    pdf.cell(
        200,
        10,
        f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        ln=True,
        align="C",
    )
    pdf.ln(10)

    # Account details
    pdf.cell(100, 10, f"Account Holder: {data.get('name')}", ln=True)
    pdf.cell(100, 10, f"Account Number: {data.get('account_number')}", ln=True)
    pdf.ln(5)
    pdf.cell(100, 10, f"Balance: ${data.get('balance')}", ln=True)
    pdf.ln(10)

    # Transactions
    pdf.cell(200, 10, "Transactions:", ln=True)
    for txn in data.get("transactions", []):
        line = f"{txn.get('date')} | {txn.get('description')} | ${txn.get('amount')}"
        pdf.cell(200, 10, line, ln=True)

    # Optional signature (basic image insertion)
    if signature_base64:
        try:
            sig_data = base64.b64decode(signature_base64)
            sig_filename = "signature.png"
            with open(sig_filename, "wb") as f:
                f.write(sig_data)
            pdf.ln(20)
            pdf.image(sig_filename, x=10, y=pdf.get_y(), w=40)
            os.remove(sig_filename)
        except Exception as e:
            print("Error processing signature:", e)

    pdf_stream = BytesIO()
    pdf.output(pdf_stream)
    pdf_stream.seek(0)
    return pdf_stream


# ==========================
# PDF Processing & Merging Utility
# ==========================


def merge_pdfs(pdf_list):
    """Combines multiple PDFs into a single document."""
    writer = PdfWriter()
    for pdf_file in pdf_list:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output
