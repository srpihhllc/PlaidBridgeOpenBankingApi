# app/utils.py

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
    """Simulate smart contract automation for a loan agreement.
       In a production system, this could trigger blockchain smart contracts."""
    from app.models import LoanAgreement, db  # Import here to avoid circular imports
    agreement = LoanAgreement.query.get(loan_agreement_id)
    if agreement and agreement.status == "active":
        agreement.status = "under_contract"
        db.session.commit()
        return {"contract_status": "executed", "loan_agreement_id": loan_agreement_id}
    return {"contract_status": "failed", "reason": "Invalid agreement or status."}
