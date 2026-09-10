# =============================================================================
# FILE: app/models/vault_transaction.py
# DESCRIPTION: Vault transaction ledger entries tied to a specific user.
#              Backwards-compatible aliases added so both legacy code that
#              uses `user_id` and newer webhook/tests that use `borrower_id`
#              work without schema churn.
# =============================================================================

from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from ..extensions import db


class VaultTransaction(db.Model):
    __tablename__ = "vault_transactions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Primary ownership FK (legacy name kept for compatibility)
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provide a borrower_id attribute that maps to the same column as user_id.
    # This lets callers pass borrower_id=... when constructing instances.
    borrower_id = synonym("user_id")

    # Optional link to a BorrowerCard (integer PK)
    card_id = db.Column(
        db.Integer,
        db.ForeignKey("borrower_cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Monetary & method fields consumed by webhooks/tests
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(64), nullable=True)

    # Keep a created_at column for existing code; use as the canonical timestamp
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Expose received_at as a synonym for created_at for readability in webhook code
    received_at = synonym("created_at")

    # Operational flags
    reconciled = db.Column(db.Boolean, default=False)

    # Keep backward-compatible fields that some callers may expect.
    # Make them nullable so we don't force values during webhook-created records.
    transaction_id = db.Column(db.String(120), unique=True, nullable=True)
    currency = db.Column(db.String(5), nullable=True, default="USD")
    status = db.Column(db.String(50), nullable=True)

    # Relationship back to User (legacy name kept)
    user = db.relationship("User", back_populates="vault_transactions")

    # Convenience relationship to BorrowerCard
    card = db.relationship(
        "BorrowerCard", backref="vault_transactions", lazy="joined"
    )

    def __repr__(self):
        return (
            f"<VaultTransaction id={self.id} borrower_id={self.user_id} "
            f"card_id={self.card_id} amount={self.amount} reconciled={self.reconciled}>"
        )
