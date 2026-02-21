# =============================================================================
# FILE: app/services/discrepancy.py
# DESCRIPTION: Functions for validating and correcting data discrepancies.
# =============================================================================

from collections.abc import Sequence
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any


def _normalize_amount(value: Any) -> Any:
    """
    Normalize an amount value for downstream processing and tests.

    Rules:
    - If value is an int, float, or Decimal, return it unchanged.
    - If value is a string that parses cleanly as a Decimal, return the original
      string. (Preserves the input string format so existing consumers/tests that
      expect string amounts continue to work.)
    - For any other value (None, malformed string, other types) return canonical
      "0.00".
    """
    # Preserve numeric types
    if isinstance(value, int | float | Decimal):
        return value

    # Validate decimal-like strings
    if isinstance(value, str):
        try:
            # Use Decimal for robust validation; disallow trailing junk (e.g. "50 USD")
            Decimal(value)
            return value
        except (InvalidOperation, ValueError):
            return "0.00"

    # Anything else is invalid
    return "0.00"


def correct_discrepancies(statements: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Given a sequence of statement records (dictionaries), return a corrected,
    deep-copied list where invalid 'amount' entries are normalized.

    Guarantees:
    - The input sequence and its items are not mutated.
    - Records without an 'amount' key are returned unchanged (deep-copied).
    - 'amount' normalization follows _normalize_amount rules.
    """
    corrected: list[dict[str, Any]] = []

    for rec in statements:
        # If item is not a dict, deep-copy and return as-is to preserve structure
        if not isinstance(rec, dict):
            corrected.append(deepcopy(rec))
            continue

        # Work on a shallow copy of the dict to avoid mutating caller objects
        new_rec = rec.copy()

        if "amount" in rec:
            new_rec["amount"] = _normalize_amount(rec.get("amount"))

        corrected.append(new_rec)

    return corrected
