# =============================================================================
# FILE: app/models/ledger.py
# DESCRIPTION: LedgerEntry model aligned with UUID User.id, cascade semantics,
#              and cockpit‑grade relationship clarity.
# =============================================================================

from datetime import datetime

from app import db
from app.models.vault_transaction import VaultTransaction

# Linter‑safe import anchor (prevents unused‑import warnings)
_ = VaultTransaction.__tablename__


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK — must match User.id (String(36))
    # Cascade delete ensures ledger entries vanish when a user is removed
    borrower_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # borrower_cards.id is Integer — correct
    # SET NULL ensures card deletion does not break ledger history
    card_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(64))
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    reconciled = db.Column(db.Boolean, default=False)

    # Reverse relationship to User
    borrower = db.relationship("User", back_populates="ledger_entries")

    def __repr__(self):
        return (
            f"<LedgerEntry id={self.id} borrower_id={self.borrower_id} "
            f"amount={self.amount} reconciled={self.reconciled}>"
        )
