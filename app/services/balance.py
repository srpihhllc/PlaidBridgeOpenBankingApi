# =============================================================================
# FILE: app/services/balance.py
# DESCRIPTION: Simple state management for a global account balance.
# Note: In a real app, this state would typically be managed in a database
#       or a thread-safe cache like Redis.
# =============================================================================

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global variable to hold the in-memory balance state
account_balance: float = 0.0


def compute_new_balance(statements: list[dict[str, Any]], start_balance: float) -> float:
    """
    Pure function: Calculates what the balance WOULD be without mutating global state.
    Used for validation, dry-runs, and unit testing.
    """
    new_total = start_balance
    for rec in statements:
        try:
            # Safely handle potential None or non-numeric types
            val = rec.get("amount")
            if val is None:
                continue
            new_total += float(val)
        except (TypeError, ValueError, KeyError):
            logger.warning(f"Skipping invalid transaction record: {rec}")
            continue
    return new_total


def update_account_balance(statements: list[dict[str, Any]]) -> None:
    """
    Mutates the global 'account_balance' by delegating to compute_new_balance.
    """
    global account_balance
    account_balance = compute_new_balance(statements, account_balance)


def get_balance(user_id: int = 0) -> dict[str, Any]:
    # ... (remains the same) ...
    return {
        "user_id": user_id,
        "available_balance": round(account_balance, 2),
        "ledger_balance": round(account_balance, 2),
        "currency": "USD",
    }
