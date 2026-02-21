# FILE: app/services/mock_data_service.py

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from app.services.bank_statement_generator import render_branded_bank_statement_pdf


class MockDataService:
    """
    Central mock-data engine for lender sandbox.
    Generates fake accounts, balances, transactions, statements, and analytics
    WITHOUT ever touching real subscriber data.
    """

    BANK_NAMES = [
        "Found Bank",
        "Piermont Bank",
        "Mock Federal Savings",
        "Demo Community Bank",
    ]

    MERCHANTS = [
        "Amazon",
        "Walmart",
        "Costco",
        "Target",
        "Shell Gas",
        "Uber",
        "Lyft",
        "Starbucks",
        "Whole Foods",
        "Stripe Payout",
        "ACH Credit",
    ]

    CATEGORIES = [
        "groceries",
        "fuel",
        "utilities",
        "subscriptions",
        "income",
        "misc",
    ]

    @classmethod
    def generate_mock_account_metadata(cls, lender_user_id: int) -> dict[str, Any]:
        """
        Returns fake account metadata ONLY keyed to the lender user,
        never referencing a real subscriber.
        """
        bank_name = random.choice(cls.BANK_NAMES)
        last4 = random.randint(1000, 9999)

        return {
            "bank_name": bank_name,
            "account_number_masked": f"****{last4}",
            "routing_number": "021000021",
            "account_type": "checking",
            "currency": "USD",
            "lender_user_id": lender_user_id,
        }

    @classmethod
    def generate_mock_balance(cls, initial: float | None = None) -> dict[str, Any]:
        """
        Generates a fake current and available balance.
        """
        base = initial if initial is not None else random.uniform(500, 5000)
        available = base - random.uniform(0, 200)

        return {
            "current_balance": round(base, 2),
            "available_balance": round(max(available, 0), 2),
            "credit_limit": None,
            "overdraft_limit": 0.0,
        }

    @classmethod
    def generate_mock_transactions(
        cls,
        days: int = 30,
        min_per_day: int = 1,
        max_per_day: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Generates a list of fake transactions over the last N days.
        Matches the shape expected by your statement generator.
        """
        now = datetime.utcnow()
        txns: list[dict[str, Any]] = []

        for d in range(days):
            day = now - timedelta(days=d)
            count = random.randint(min_per_day, max_per_day)
            for _ in range(count):
                merchant = random.choice(cls.MERCHANTS)
                category = random.choice(cls.CATEGORIES)

                # Income vs expense vs neutral
                if category == "income":
                    amount = round(random.uniform(300, 2000), 2)
                else:
                    amount = round(-random.uniform(5, 250), 2)

                txns.append(
                    {
                        "date": day.strftime("%Y-%m-%d"),
                        "description": merchant,
                        "amount": amount,
                        "category": category,
                        "id": f"MOCK_{day.strftime('%Y%m%d')}_{random.randint(1000,9999)}",
                    }
                )

        # Sort by date ascending
        txns.sort(key=lambda t: t["date"])
        return txns

    @classmethod
    def generate_mock_analytics(cls, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Compute simple category totals and a monthly summary
        from the mock transactions.
        """
        category_totals: dict[str, float] = {}
        income_total = 0.0
        expense_total = 0.0

        for tx in transactions:
            amount = float(tx.get("amount", 0) or 0)
            cat = tx.get("category") or "uncategorized"

            category_totals.setdefault(cat, 0.0)
            category_totals[cat] += amount

            if amount > 0:
                income_total += amount
            else:
                expense_total += amount

        net = income_total + expense_total

        return {
            "category_totals": category_totals,
            "income_total": round(income_total, 2),
            "expense_total": round(expense_total, 2),
            "net_cash_flow": round(net, 2),
        }

    @classmethod
    def generate_mock_statement_pdf(
        cls,
        lender_user_id: int,
        days: int = 30,
        static_folder: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a branded mock bank statement PDF and return metadata + bytes.
        """
        account_meta = cls.generate_mock_account_metadata(lender_user_id)
        transactions = cls.generate_mock_transactions(days=days)

        pdf_bytes = render_branded_bank_statement_pdf(
            bank_name=account_meta["bank_name"],
            account_number=account_meta["account_number_masked"],
            transactions=transactions,
            static_folder=static_folder,
        )

        analytics = cls.generate_mock_analytics(transactions)

        return {
            "account": account_meta,
            "analytics": analytics,
            "transaction_count": len(transactions),
            "pdf_bytes": pdf_bytes,
        }
