# =============================================================================
# FILE: app/services/category_analytics.py
# DESCRIPTION: Financial category summary and cash flow analytics engine.
#               Uses Decimal arithmetic to prevent floating-point drift.
# =============================================================================

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from app.dto.category_summary_dto import CategorySummaryDTO
from app.dto.transaction_dto import TransactionDTO

logger = logging.getLogger(__name__)


def _to_decimal(val: Any) -> Decimal:
    """Safely convert any input value to a Decimal figure."""
    if val is None:
        return Decimal("0.00")
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        logger.warning(
            f"⚠️ [ANALYTICS] Invalid transaction amount '{val}', defaulting to 0.00"
        )
        return Decimal("0.00")


def compute_category_summary(
    transactions: list[TransactionDTO | dict[str, Any]] | None,
) -> CategorySummaryDTO:
    """
    Computes financial summary metrics and per-category breakdowns from a transaction list.

    :param transactions: List of TransactionDTO objects or dictionaries.
    :return: Populated CategorySummaryDTO instance.
    """
    categories_map: dict[str, Decimal] = {}
    income_dec = Decimal("0.00")
    expenses_dec = Decimal("0.00")

    for txn in transactions or []:
        # Support both object attribute and dictionary key access
        if isinstance(txn, dict):
            raw_amt = txn.get("amount")
            raw_cat = txn.get("category")
        else:
            raw_amt = getattr(txn, "amount", 0.0)
            raw_cat = getattr(txn, "category", None)

        category = str(raw_cat or "").strip() or "Uncategorized"
        amt = _to_decimal(raw_amt)

        # Aggregate category total
        categories_map[category] = (
            categories_map.get(category, Decimal("0.00")) + amt
        )

        # Aggregate income vs expenses
        if amt >= Decimal("0.00"):
            income_dec += amt
        else:
            expenses_dec += amt

    # Net and total calculations
    net_dec = income_dec + expenses_dec
    total_dec = net_dec
    abs_expenses_dec = abs(expenses_dec)

    # Convert category map totals to floats rounded to 2 decimal places
    formatted_categories = {
        cat_name: float(round(cat_amt, 2))
        for cat_name, cat_amt in categories_map.items()
    }

    return CategorySummaryDTO(
        total_amount=float(round(total_dec, 2)),
        income=float(round(income_dec, 2)),
        expenses=float(round(abs_expenses_dec, 2)),
        net_cash_flow=float(round(net_dec, 2)),
        categories=formatted_categories,
    )


# -----------------------------------------------------------------------------
# Explicit Exports
# -----------------------------------------------------------------------------
__all__ = [
    "compute_category_summary",
]
