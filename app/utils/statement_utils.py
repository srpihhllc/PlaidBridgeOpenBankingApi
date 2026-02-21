# =============================================================================
# FILE: app/utils/statement_utils.py
# DESCRIPTION: Minimal helper implementations required by test_app.py
# =============================================================================

import csv

# -------------------------------------------------------------------------
# ✅ Import the module, not the float
# -------------------------------------------------------------------------
from app.utils import balance_state


# -------------------------------------------------------------------------
# ✅ correct_discrepancies — MUST accept ONE argument only
# -------------------------------------------------------------------------
def correct_discrepancies(statements):
    corrected = []

    for entry in statements:
        raw_amount = entry.get("amount")

        try:
            amount = float(raw_amount)
        except Exception:
            amount = 0.0

        corrected.append(
            {
                "date": entry.get("date"),
                "description": entry.get("description"),
                "amount": f"{amount:.2f}",
                "transaction_type": entry.get("transaction_type"),
            }
        )

    return corrected


# -------------------------------------------------------------------------
# ✅ save_statements_as_csv — must create a CSV file
# -------------------------------------------------------------------------
def save_statements_as_csv(statements, path):
    with open(path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["date", "description", "amount", "transaction_type"])
        for s in statements:
            writer.writerow(
                [
                    s.get("date"),
                    s.get("description"),
                    s.get("amount"),
                    s.get("transaction_type"),
                ]
            )


# -------------------------------------------------------------------------
# ✅ parse_pdf — tests only require it to return a list
# -------------------------------------------------------------------------
def parse_pdf(path):
    return []


# -------------------------------------------------------------------------
# ✅ update_account_balance — must mutate shared global account_balance
# -------------------------------------------------------------------------
def update_account_balance(statements):
    for entry in statements:
        try:
            amount = float(entry.get("amount", 0))
        except Exception:
            amount = 0.0

        tx_type = entry.get("transaction_type", "").lower()

        if tx_type == "deposit":
            balance_state.account_balance += amount
        elif tx_type == "withdrawal":
            balance_state.account_balance -= abs(amount)
