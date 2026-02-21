# =============================================================================
# FILE: app/models/vault_transaction.py
# DESCRIPTION: Vault transaction ledger entries tied to a specific user.
#              UUID FK alignment + cascade semantics + clean representation.
# =============================================================================

from datetime import datetime

from app.extensions import db


class VaultTransaction(db.Model):
    __tablename__ = "vault_transactions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK with cascade delete
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_id = db.Column(db.String(120), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False, default="USD")
    status = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship back to User
    user = db.relationship("User", back_populates="vault_transactions")

    def __repr__(self):
        return f"<VaultTransaction id={self.id} user_id={self.user_id} " f"amount={self.amount}>"
