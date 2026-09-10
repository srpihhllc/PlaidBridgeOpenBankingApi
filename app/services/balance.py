# =============================================================================
# FILE: app/services/balance.py
# DESCRIPTION: Simple state management for a global account balance.
# Note: In a real app, this state would typically be managed in a database
#       or a thread-safe cache like Redis.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global variable to hold the in-memory balance state
account_balance: float = 0.0


def compute_new_balance(
    statements: list[dict[str, Any]], start_balance: float
) -> float:
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
    Mutates the global 'account_balance' by computing the statements against
    the current global total.
    """
    global account_balance

    try:
        account_balance = compute_new_balance(statements, account_balance)
        logger.info(
            f"Account balance globally updated to: {account_balance:.2f}"
        )
    except Exception as e:
        logger.error(f"Failed to update account balance: {e}", exc_info=True)
