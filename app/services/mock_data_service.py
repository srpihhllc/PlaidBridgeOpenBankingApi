# =============================================================================
# FILE: app/services/mock_data_service.py
# =============================================================================

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.services.bank_statement_generator import render_branded_bank_statement_pdf


class MockDataService:
    """
    Central mock-data engine for the lender sandbox.
    Generates high-fidelity fake accounts, balances, transactions, statements, 
    and analytics WITHOUT touching real subscriber data. Mirrors Open Banking 
    schemas (e.g., Plaid, MX) for realistic downstream testing.
    """

    BANK_NAMES = [
        "Found Bank",
        "Piermont Bank",
        "Mock Federal Savings",
        "Demo Community Bank",
        "First FinTech Trust",
    ]

    # Enriched merchant data for realistic transaction payloads
    MERCHANTS = [
        {"name": "Amazon", "channel": "online", "primary": "GENERAL_MERCHANDISE", "detailed": "GENERAL_MERCHANDISE_ONLINE_MARKETPLACE"},
        {"name": "Walmart", "channel": "in store", "primary": "GENERAL_MERCHANDISE", "detailed": "GENERAL_MERCHANDISE_SUPERSTORES"},
        {"name": "Costco", "channel": "in store", "primary": "GENERAL_MERCHANDISE", "detailed": "GENERAL_MERCHANDISE_SUPERSTORES"},
        {"name": "Target", "channel": "in store", "primary": "GENERAL_MERCHANDISE", "detailed": "GENERAL_MERCHANDISE_SUPERSTORES"},
        {"name": "Shell Gas", "channel": "in store", "primary": "TRANSPORTATION", "detailed": "TRANSPORTATION_GAS_STATIONS"},
        {"name": "Uber", "channel": "online", "primary": "TRANSPORTATION", "detailed": "TRANSPORTATION_TAXIS_AND_RIDE_SHARES"},
        {"name": "Lyft", "channel": "online", "primary": "TRANSPORTATION", "detailed": "TRANSPORTATION_TAXIS_AND_RIDE_SHARES"},
        {"name": "Starbucks", "channel": "in store", "primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_COFFEE"},
        {"name": "Whole Foods", "channel": "in store", "primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_GROCERIES"},
        {"name": "Stripe Payout", "channel": "online", "primary": "INCOME", "detailed": "INCOME_WAGES"},
        {"name": "ACH Credit", "channel": "online", "primary": "INCOME", "detailed": "INCOME_TRANSFER"},
    ]

    @classmethod
    def generate_mock_account_metadata(cls, lender_user_id: int) -> dict[str, Any]:
        """
        Returns rich account metadata mirroring an Open Banking Account object.
        Keys are bound to the lender sandbox context.
        """
        bank_name = random.choice(cls.BANK_NAMES)
        last4 = random.randint(1000, 9999)

        return {
            "account_id": f"acc_{uuid.uuid4().hex[:16]}",
            "bank_name": bank_name,
            "official_name": f"{bank_name} Premier Checking",
            "account_number_masked": f"****{last4}",
            "mask": str(last4),
            "routing_number": f"0210{random.randint(10000, 99999)}",
            "wire_routing_number": f"0210{random.randint(10000, 99999)}",
            "account_type": "depository",
            "account_subtype": "checking",
            "currency": "USD",
            "lender_user_id": lender_user_id,
            "status": "active",
            "verification_status": "automatically_verified",
            "owners": [
                {
                    "name": f"Lender Sandbox User {lender_user_id}",
                    "addresses": [{
                        "data": {
                            "city": "San Francisco",
                            "region": "CA",
                            "street": "123 Sandbox Blvd",
                            "postal_code": "94105",
                            "country": "US"
                        },
                        "primary": True
                    }],
                    "emails": [{"data": f"sandbox_{lender_user_id}@mock.local", "primary": True, "type": "primary"}],
                    "phone_numbers": [{"data": "+14155550199", "primary": True, "type": "mobile"}]
                }
            ]
        }

    @classmethod
    def generate_mock_balance(cls, initial: float | None = None) -> dict[str, Any]:
        """
        Generates a fake current and available balance with ISO currency codes
        and timestamps to mimic live institution checks.
        """
        base = initial if initial is not None else random.uniform(500.0, 5000.0)
        available = base - random.uniform(0.0, 200.0)

        return {
            "current_balance": round(base, 2),
            "available_balance": round(max(available, 0), 2),
            "iso_currency_code": "USD",
            "unofficial_currency_code": None,
            "credit_limit": None,
            "overdraft_limit": 0.0,
            "last_updated_datetime": datetime.utcnow().isoformat() + "Z"
        }

    @classmethod
    def generate_mock_transactions(
        cls,
        days: int = 30,
        min_per_day: int = 1,
        max_per_day: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Generates a highly detailed list of fake transactions.
        Maintains legacy keys for PDF generator while adding geolocation,
        pending flags, and taxonomy categories.
        """
        now = datetime.utcnow()
        txns: list[dict[str, Any]] = []

        for d in range(days):
            day = now - timedelta(days=d)
            count = random.randint(min_per_day, max_per_day)
            
            for _ in range(count):
                merchant = random.choice(cls.MERCHANTS)
                is_income = merchant["primary"] == "INCOME"

                # Standardize amounts: Positive for income, Negative for expense (or vice versa based on your DB schema)
                # Assuming your legacy code used negative for expense:
                if is_income:
                    amount = round(random.uniform(300.0, 2000.0), 2)
                else:
                    amount = round(-random.uniform(5.0, 250.0), 2)

                is_pending = d < 3 and random.choice([True, False])
                authorized_day = day - timedelta(hours=random.randint(4, 48))

                txns.append({
                    # Legacy keys for PDF generator compatibility
                    "date": day.strftime("%Y-%m-%d"),
                    "description": merchant["name"],
                    "amount": amount,
                    "category": merchant["primary"].lower(),
                    
                    # Enriched Open Banking attributes
                    "id": f"tx_{uuid.uuid4().hex}",
                    "account_id": f"acc_{uuid.uuid4().hex[:16]}", # Usually mapped to the actual account
                    "pending": is_pending,
                    "authorized_date": authorized_day.strftime("%Y-%m-%d"),
                    "payment_channel": merchant["channel"],
                    "merchant_name": merchant["name"],
                    "website": f"www.{merchant['name'].lower().replace(' ', '')}.com",
                    "personal_finance_category": {
                        "primary": merchant["primary"],
                        "detailed": merchant["detailed"],
                        "confidence_level": "VERY_HIGH"
                    },
                    "location": {
                        "address": f"{random.randint(100, 9999)} Mockingbird Ln",
                        "city": "San Francisco",
                        "region": "CA",
                        "postal_code": "94105",
                        "country": "US",
                        "lat": round(random.uniform(37.7, 37.8), 4),
                        "lon": round(random.uniform(-122.5, -122.4), 4),
                    } if merchant["channel"] == "in store" else None,
                })

        # Sort by date ascending
        txns.sort(key=lambda t: t["date"])
        return txns

    @classmethod
    def generate_mock_analytics(cls, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Compute category totals, monthly summaries, and mock risk indicators
        (e.g., velocity, overdraft risk).
        """
        category_totals: dict[str, float] = {}
        income_total = 0.0
        expense_total = 0.0
        transaction_count = len(transactions)

        for tx in transactions:
            amount = float(tx.get("amount", 0) or 0)
            # Use the new enriched category if available, fallback to legacy
            cat = tx.get("personal_finance_category", {}).get("primary", tx.get("category", "UNCATEGORIZED"))

            category_totals.setdefault(cat, 0.0)
            category_totals[cat] += amount

            if amount > 0:
                income_total += amount
            else:
                expense_total += amount

        net = income_total + expense_total

        return {
            "cash_flow": {
                "income_total": round(income_total, 2),
                "expense_total": round(expense_total, 2),
                "net_cash_flow": round(net, 2),
            },
            "category_totals": {k: round(v, 2) for k, v in category_totals.items()},
            "risk_indicators": {
                "days_with_negative_balance": 0,
                "insufficient_funds_count": random.choice([0, 0, 0, 1]), # Occasional mock NSF
                "high_velocity_transactions": transaction_count > 50,
            },
            "metadata": {
                "analyzed_transaction_count": transaction_count,
                "last_analyzed_at": datetime.utcnow().isoformat() + "Z"
            }
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
            "statement_period": {
                "start_date": (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "end_date": datetime.utcnow().strftime("%Y-%m-%d"),
            },
            "transaction_count": len(transactions),
            "pdf_bytes": pdf_bytes,
        }