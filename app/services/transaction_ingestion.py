# =============================================================================
# FILE: app/services/transaction_ingestion.py
# DESCRIPTION:
#   Plaid-backed ingestion into the Transaction model.
#   - Safe date parsing for Plaid date formats
#   - Idempotent upserts keyed by Plaid transaction ID
#   - Normalized fields for UI safety
#   - Resilient ingestion: one bad record does not stop the batch
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, cast

from app.extensions import db
from app.models.transactions import Transaction
from app.services import plaid_api


def _safe_parse_date(value: object) -> datetime:
    """Parse a Plaid date value, returning a timezone-aware UTC datetime."""
    if not isinstance(value, str) or not value:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _fetch_recent_transactions(
    access_token: str,
) -> list[Mapping[str, Any]]:
    """Call the recent-transactions function exposed by plaid_api."""
    fetcher = getattr(plaid_api, "fetch_recent_transactions", None)
    if not callable(fetcher):
        raise RuntimeError(
            "app.services.plaid_api does not expose a callable "
            "'fetch_recent_transactions'. Update this lookup to match "
            "the function provided by plaid_api."
        )

    result = fetcher(access_token)
    if not isinstance(result, list):
        raise TypeError("fetch_recent_transactions must return a list.")

    return cast(list[Mapping[str, Any]], result)


def sync_user_transactions_from_plaid(
    user_id: int,
    plaid_access_token: str,
) -> int:
    """
    Fetch and upsert recent Plaid transactions.

    Return the number of newly inserted rows; existing rows are updated.
    """
    plaid_transactions = _fetch_recent_transactions(plaid_access_token)
    inserted_count = 0
    changed = False

    for transaction_data in plaid_transactions:
        try:
            if not isinstance(transaction_data, Mapping):
                raise TypeError("Transaction record must be a mapping.")

            transaction_id = transaction_data.get("transaction_id")
            if not isinstance(transaction_id, str) or not transaction_id:
                raise ValueError("Transaction record has no valid transaction_id.")

            existing = Transaction.query.filter_by(id=transaction_id).first()

            raw_category = transaction_data.get("category")
            category_name = (
                raw_category[0]
                if isinstance(raw_category, list)
                and raw_category
                and isinstance(raw_category[0], str)
                else "Uncategorized"
            )

            amount = transaction_data.get("amount")
            if not isinstance(amount, (int, float)):
                amount = 0.0

            currency = transaction_data.get("iso_currency_code")
            if not isinstance(currency, str) or not currency:
                currency = "USD"

            name = transaction_data.get("name")
            if not isinstance(name, str) or not name:
                name = "(no description)"

            pending = transaction_data.get("pending", False)
            if not isinstance(pending, bool):
                pending = False

            merchant_name = transaction_data.get("merchant_name")
            if not isinstance(merchant_name, str):
                merchant_name = None

            payment_channel = transaction_data.get("payment_channel")
            if not isinstance(payment_channel, str):
                payment_channel = None

            account_id = transaction_data.get("account_id")
            if not isinstance(account_id, str):
                account_id = None

            values = {
                "amount": float(amount),
                "currency": currency,
                "date": _safe_parse_date(transaction_data.get("date")),
                "name": name,
                "category": category_name,
                "is_pending": pending,
                "merchant_name": merchant_name,
                "payment_channel": payment_channel,
            }

            if existing is not None:
                for field, value in values.items():
                    setattr(existing, field, value)
                changed = True
                continue

            transaction = Transaction(
                id=transaction_id,
                user_id=user_id,
                plaid_account_id=account_id,
                account_id=account_id,
                **values,
            )
            db.session.add(transaction)
            inserted_count += 1
            changed = True

        except Exception as error:
            transaction_id_for_log = transaction_data.get("transaction_id")
            print(
                f"[WARN] Failed to ingest transaction "
                f"{transaction_id_for_log}: {error}"
            )

    if changed:
        db.session.commit()

    return inserted_count