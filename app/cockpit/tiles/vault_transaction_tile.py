# app/cockpit/tiles/vault_transaction_tile.py

from app.extensions import redis_client
from app.models.borrower_card import BorrowerCard
from app.models.user import User
from app.models.vault_transaction import VaultTransaction  # ✅ Clean, TTL-ready, cockpit-grade


def get_vault_transaction_tile():
    transactions = (
        VaultTransaction.query.order_by(VaultTransaction.received_at.desc()).limit(50).all()
    )
    tile_data = []

    for tx in transactions:
        borrower = User.query.get(tx.borrower_id)
        card = BorrowerCard.query.get(tx.card_id)

        ttl_key = f"vault_txn:{tx.id}:ttl"
        ttl = redis_client.ttl(ttl_key)

        tile_data.append(
            {
                "id": tx.id,
                "amount": tx.amount,
                "method": tx.method,
                "received_at": tx.received_at.isoformat(),
                "ttl_seconds": ttl,
                "reconciled": tx.reconciled,
                "borrower": {
                    "id": borrower.id if borrower else None,
                    "username": borrower.username if borrower else "Orphaned",
                    "role": borrower.role if borrower else "Unknown",
                },
                "card_last4": card.last4 if card else "Missing",
            }
        )

    return tile_data
