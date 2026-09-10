# =============================================================================
# FILE: app/services/discrepancy.py
# DESCRIPTION: Functions for validating, normalizing, and correcting data
#               discrepancies in statement records.
# =============================================================================

from __future__ import annotations

import logging
from collections.abc import Sequence
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_amount(value: Any) -> Any:
    """
    Normalize an amount value for downstream processing and tests.

    Rules:
    - Booleans are rejected and converted to "0.00" (since bool inherits from int).
    - If value is an int, float, or Decimal, return it unchanged.
    - If value is a string that parses cleanly as a Decimal, return the original string.
      (Preserves input string format for tests/consumers expecting raw string amounts.)
    - For any other value (None, malformed string, complex objects) return "0.00".
    """
    # Exclude booleans because bool is a subclass of int in Python
    if isinstance(value, bool):
        return "0.00"

    # Preserve numeric types
    if isinstance(value, (int, float, Decimal)):
        return value

    # Validate decimal-like strings
    if isinstance(value, str):
        try:
            Decimal(value)
            return value
        except (InvalidOperation, ValueError):
            return "0.00"

    # Anything else is invalid
    return "0.00"


def correct_discrepancies(
    statements: Sequence[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    Given a sequence of statement records (dictionaries), return a corrected,
    deep-copied list where invalid 'amount' entries are normalized.

    Guarantees:
    - The input sequence and its items are not mutated.
    - Records without an 'amount' key are returned unchanged (deep-copied).
    - 'amount' normalization follows _normalize_amount rules.

    :param statements: Sequence of statement record dictionaries.
    :return: Deep-copied list of statement records with normalized amounts.
    """
    if not statements:
        return []

    corrected: list[dict[str, Any]] = []

    for rec in statements:
        # If item is not a dict, deep-copy and return as-is to preserve structure
        if not isinstance(rec, dict):
            corrected.append(deepcopy(rec))
            continue

        # Perform a true deep copy to prevent mutation of nested structures
        new_rec = deepcopy(rec)

        if "amount" in new_rec:
            orig_val = new_rec["amount"]
            norm_val = _normalize_amount(orig_val)

            if orig_val != norm_val:
                logger.warning(
                    f"⚠️ [DISCREPANCY] Normalized invalid amount '{orig_val}' "
                    f"(type: {type(orig_val).__name__}) -> '{norm_val}'"
                )

            new_rec["amount"] = norm_val

        corrected.append(new_rec)

    return corrected


# -----------------------------------------------------------------------------
# Explicit Exports
# -----------------------------------------------------------------------------
__all__ = [
    "correct_discrepancies",
]
