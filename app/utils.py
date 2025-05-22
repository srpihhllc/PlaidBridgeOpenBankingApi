# app/utils.py

import datetime
import base64
from io import BytesIO
from fpdf import FPDF
from PyPDF2 import PdfReader, PdfWriter

def analyze_loan_agreement(agreement_text):
    """AI analyzes loan agreements for compliance and ethical standards."""
    unethical_terms = ["hidden fees", "predatory interest rates", "undisclosed penalties"]
    for term in unethical_terms:
        if term in agreement_text.lower():
            return {"status": "flagged", "reason": f"Contains unethical term: {term}"}
    return {"status": "approved"}

def detect_fraudulent_transaction(description, amount):
    """Flags potentially fraudulent transactions based on patterns."""
    suspicious_terms = ["unexpected large withdrawal", "account drained", "unauthorized payment"]
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

def create_bank_statement(data, signature_base64=None):
    """Generates a bank statement PDF using FPDF."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header and metadata
    pdf.cell(200, 10, "Bank Statement", ln=True, align='C')
    pdf.cell(200, 10, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)

    # Account details
    pdf.cell(100, 10, f"Account Holder: {data.get('name')}", ln=True)
    pdf.cell(100, 10, f"Account Number: {data.get('account_number')}", ln=True)
    pdf.ln(5)
    pdf.cell(100, 10, f"Balance: ${data.get('balance')}", ln=True)
    pdf.ln(10)

    # Transactions
    pdf.cell(200, 10, "Transactions:", ln=True)
    for txn in data.get('transactions', []):
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

