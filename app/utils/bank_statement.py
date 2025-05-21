# app/utils/bank_statement.py

import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
# If you want to integrate PyHanko later, you can import signing functions here

def generate_bank_statement_pdf(user, transactions):
    """
    Generates a PDF bank statement for a given user.
    
    Args:
      user (dict): Contains user details like 'name' and 'account_number'.
      transactions (list): A list of dicts with transaction details (e.g. date, description, amount).
    
    Returns:
      bytes: Binary data representing the generated PDF.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header with advanced digital signature simulation info (customize as needed)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, f"Bank Statement for {user.get('name', '')}")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 90, f"Account: {user.get('account_number', 'N/A')}")
    c.line(72, height - 100, width - 72, height - 100)
    
    # Table headers for transactions
    c.drawString(72, height - 120, "Date")
    c.drawString(150, height - 120, "Description")
    c.drawString(400, height - 120, "Amount")
    
    y = height - 140
    for txn in transactions:
        c.drawString(72, y, txn.get("date", ""))
        c.drawString(150, y, txn.get("description", ""))
        c.drawString(400, y, str(txn.get("amount", "")))
        y -= 20
        if y < 72:
            c.showPage()
            y = height - 72

    # Simulated digital signature (placeholder text)
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(72, 50, "Digitally signed by Advanced Signature Service")
    
    c.showPage()
    c.save()
    
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
