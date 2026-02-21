# =============================================================================
# FILE: app/services/transaction_ingestion.py
# DESCRIPTION:
#   Plaid-backed ingestion into Transaction model (cockpit‑grade).
#   - Safe date parsing for all Plaid formats
#   - Idempotent upserts keyed by Plaid transaction_id
#   - Normalized fields for UI safety
#   - Resilient ingestion (one bad record never breaks the batch)
# =============================================================================

from datetime import datetime

from app.extensions import db
from app.models.transactions import Transaction
from app.services.plaid_api import fetch_recent_transactions


# -----------------------------------------------------------------------------
# Safe date parsing
# -----------------------------------------------------------------------------
def _safe_parse_date(value: str | None) -> datetime:
    """
    Safely parse Plaid date formats:
    - "2024-01-15"
    - "2024-01-15T00:00:00Z"
    - "2024-01-15T00:00:00"
    Falls back to UTC now if parsing fails.
    """
    if not value:
        return datetime.utcnow()

    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except Exception:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except Exception:
            return datetime.utcnow()


# -----------------------------------------------------------------------------
# Ingestion / Upsert
# -----------------------------------------------------------------------------
def sync_user_transactions_from_plaid(user_id: int, plaid_access_token: str) -> int:
    """
    Fetches recent Plaid transactions and upserts them into the Transaction table.
    Returns the count of newly inserted rows (not updates).
    """
    plaid_txns = fetch_recent_transactions(plaid_access_token)
    upserted = 0

    for p in plaid_txns:
        try:
            txn_id = p["transaction_id"]
            existing = Transaction.query.filter_by(id=txn_id).first()

            # Normalize date
            date_val = _safe_parse_date(p.get("date"))

            # Normalize category
            category_list = p.get("category") or []
            category_name = category_list[0] if category_list else "Uncategorized"

            # -----------------------------------------------------------------
            # Update existing transaction
            # -----------------------------------------------------------------
            if existing:
                existing.amount = p.get("amount") or 0.0
                existing.currency = p.get("iso_currency_code") or "USD"
                existing.date = date_val
                existing.name = p.get("name") or "(no description)"
                existing.category = category_name
                existing.is_pending = p.get("pending", False)
                existing.merchant_name = p.get("merchant_name")
                existing.payment_channel = p.get("payment_channel")
                continue

            # -----------------------------------------------------------------
            # Insert new transaction
            # -----------------------------------------------------------------
            txn = Transaction(
                id=txn_id,
                user_id=user_id,
                plaid_account_id=p.get("account_id"),
                account_id=p.get("account_id"),
                amount=p.get("amount") or 0.0,
                currency=p.get("iso_currency_code") or "USD",
                date=date_val,
                name=p.get("name") or "(no description)",
                category=category_name,
                is_pending=p.get("pending", False),
                merchant_name=p.get("merchant_name"),
                payment_channel=p.get("payment_channel"),
            )

            db.session.add(txn)
            upserted += 1

        except Exception as e:
            # Ingestion must be resilient — log and continue
            print(f"[WARN] Failed to ingest transaction {p.get('transaction_id')}: {e}")

    if upserted:
        db.session.commit()

    return upserted
