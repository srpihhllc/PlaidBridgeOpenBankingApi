# =============================================================================
# FILE: app/services/transaction_ingestion.py
# DESCRIPTION:
#   Fetch and idempotently ingest Plaid transactions into the Transaction model.
# =============================================================================

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models.transactions import Transaction
from app.services import plaid_api

logger = logging.getLogger(__name__)


def _parse_plaid_date(value: object) -> datetime:
    """Parse a Plaid date and return a timezone-aware UTC datetime."""
    if not isinstance(value, str) or not value:
        raise ValueError("Missing or invalid transaction date")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _fetch_recent_transactions(
    access_token: str,
) -> list[Mapping[str, Any]]:
    """Fetch transactions through the existing Plaid API service."""
    result = plaid_api.get_transactions(access_token)

    if isinstance(result, tuple):
        body, status = result
        if status != 200:
            raise RuntimeError(f"Plaid transaction request failed (HTTP {status})")
        result = body

    if not isinstance(result, Mapping) or result.get("error"):
        raise RuntimeError("Plaid transaction request returned an error")

    transactions = result.get("transactions")
    if not isinstance(transactions, list):
        raise TypeError("Plaid response did not contain a transactions list")

    return [
        transaction
        for transaction in transactions
        if isinstance(transaction, Mapping)
    ]


def sync_user_transactions_from_plaid(
    user_id: str,
    plaid_access_token: str,
) -> int:
    """
    Fetch and upsert recent Plaid transactions.

    Returns the number of newly inserted rows. Existing rows are updated.
    Requires an active Flask application context.
    """
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("A valid user_id is required")
    if not isinstance(plaid_access_token, str) or not plaid_access_token:
        raise ValueError("A Plaid access token is required")

    plaid_transactions = _fetch_recent_transactions(plaid_access_token)
    inserted_count = 0
    changed = False

    for transaction_data in plaid_transactions:
        try:
            transaction_id = transaction_data.get("transaction_id")
            if (
                not isinstance(transaction_id, str)
                or not transaction_id
                or len(transaction_id) > 120
            ):
                raise ValueError("Invalid Plaid transaction ID")

            amount = transaction_data.get("amount")
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                raise ValueError("Invalid transaction amount")

            name = transaction_data.get("name")
            if not isinstance(name, str) or not name:
                name = "(no description)"

            raw_category = transaction_data.get("category")
            if (
                isinstance(raw_category, list)
                and raw_category
                and isinstance(raw_category[0], str)
            ):
                category = raw_category[0][:255]
            else:
                category = "Uncategorized"

            currency = transaction_data.get("iso_currency_code")
            if not isinstance(currency, str) or not currency:
                currency = "USD"

            plaid_account_id = transaction_data.get("account_id")
            if not isinstance(plaid_account_id, str):
                plaid_account_id = None

            pending = transaction_data.get("pending")
            if not isinstance(pending, bool):
                pending = False

            values = {
                "plaid_account_id": plaid_account_id,
                "amount": float(amount),
                "currency": currency[:5],
                "date": _parse_plaid_date(transaction_data.get("date")),
                "name": name[:255],
                "category": category,
                "is_pending": pending,
            }

            existing = Transaction.query.filter_by(
                user_id=user_id,
                plaid_transaction_id=transaction_id,
            ).first()

            if existing is None:
                db.session.add(
                    Transaction(
                        user_id=user_id,
                        plaid_transaction_id=transaction_id,
                        **values,
                    )
                )
                inserted_count += 1
            else:
                for field, value in values.items():
                    setattr(existing, field, value)

            changed = True

        except (TypeError, ValueError, OverflowError) as error:
            logger.warning("Skipping invalid Plaid transaction: %s", error)

    if changed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    return inserted_count
