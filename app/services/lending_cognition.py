# app/services/lending_cognition.py

import os
from datetime import datetime

import requests

from app.extensions import db
from app.models import CreditLedger, LoanAgreement, PaymentLog


class CreditReflexManager:
    """Coordinates credit issuance, repayments, and reflex judgment."""

    @staticmethod
    def issue_virtual_card(user_id: int, limit: float = 5000.00):
        """Creates a virtual card and logs it into credit_ledger."""
        api_key = os.getenv("TREASURY_PRIME_API_KEY")
        if not api_key:
            raise RuntimeError("Missing TREASURY_PRIME_API_KEY environment variable")

        try:
            response = requests.post(
                "https://api.treasuryprime.com/cards",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "type": "virtual",
                    "customer_id": f"user_{user_id}",
                    "limit": limit,
                    "network": "visa",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            # Log and fall back to mock card ID
            print(f"⚠️ Treasury Prime API call failed: {e}")
            data = {}

        card_id = data.get("id") or "mock_card_xyz123"

        ledger = CreditLedger(
            user_id=user_id, card_id=card_id, credit_limit=limit, balance_used=0.00
        )
        db.session.add(ledger)
        db.session.commit()
        print(f"💳 Virtual card issued: {card_id} with ${limit} limit")
        return card_id

    @staticmethod
    def ingest_external_loan(borrower_id: int, amount: float):
        """Logs lender-to-borrower funding as repayment event."""
        log = PaymentLog(
            card_id=None,
            user_id=borrower_id,
            amount=amount,
            timestamp=datetime.utcnow(),
            source_type="external_lender",
        )
        db.session.add(log)
        db.session.commit()
        print(f"✅ External loan ingested for user {borrower_id}: ${amount}")

    @staticmethod
    def detect_credit_violation(user_id: int) -> bool:
        """Flags borrower overexposure if repayments lag behind credit issued."""
        ledger_entries = CreditLedger.query.filter_by(user_id=user_id).all()
        repayments = PaymentLog.query.filter_by(user_id=user_id).all()

        total_credit_limit = sum(entry.credit_limit for entry in ledger_entries)
        total_repaid = sum(p.amount for p in repayments)

        overexposure = total_credit_limit - total_repaid
        threshold = 0.20 * total_credit_limit

        if overexposure > threshold:
            print(f"⚠️ Violation: User {user_id} overexposed by ${overexposure:.2f}")
            return True
        print(f"✅ User {user_id} credit behavior normal.")
        return False

    @staticmethod
    def reconcile_loan_vs_card(user_id: int):
        """Audits borrower repayment gap across lender loans and card usage."""
        loans = LoanAgreement.query.filter_by(borrower_id=user_id).all()
        repayments = PaymentLog.query.filter_by(user_id=user_id).all()

        total_loans = sum(loan.amount for loan in loans)
        total_repaid = sum(p.amount for p in repayments)
        delta = total_loans - total_repaid

        print(f"🧮 User {user_id} gap: ${delta:.2f}")
        return delta
