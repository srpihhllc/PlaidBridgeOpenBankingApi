# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/seed.py

"""
Seed script for Financial Powerhouse API.
Populates the database with sample borrowers, lenders, and transactions
for local testing and demos.

Usage:
    make seed
"""

import datetime

from sqlalchemy.orm import Session

from app import models
from app.database import Base, SessionLocal, engine


def seed():
    # Ensure tables exist (in case migrations not run)
    Base.metadata.create_all(bind=engine)

    session: Session = SessionLocal()

    try:
        # Clear existing demo data
        session.query(models.Transaction).delete()
        session.query(models.Loan).delete()
        session.query(models.Borrower).delete()
        session.query(models.Lender).delete()

        # Create sample lender
        lender = models.Lender(
            name="Demo Lender Inc.", account_number="LEND123456", health_score=95
        )

        # Create sample borrower
        borrower = models.Borrower(
            name="Alice Borrower", account_number="BORR654321", health_score=72
        )

        session.add_all([lender, borrower])
        session.flush()  # assign IDs

        # Create a loan agreement
        loan = models.Loan(
            borrower_id=borrower.id,
            lender_id=lender.id,
            principal_amount=5000,
            interest_rate=0.05,
            status="active",
            created_at=datetime.datetime.utcnow(),
        )
        session.add(loan)
        session.flush()

        # Add some transactions
        tx1 = models.Transaction(
            loan_id=loan.id,
            amount=-200,
            description="Monthly repayment",
            timestamp=datetime.datetime.utcnow(),
        )
        tx2 = models.Transaction(
            loan_id=loan.id,
            amount=+5000,
            description="Loan disbursement",
            timestamp=datetime.datetime.utcnow(),
        )

        session.add_all([tx1, tx2])
        session.commit()

        print("✅ Database seeded with demo borrower, lender, loan, and transactions.")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
