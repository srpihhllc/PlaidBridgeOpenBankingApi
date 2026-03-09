# =============================================================================
# FILE: app/models/bank_account.py
# DESCRIPTION: BankAccount model using string-based relationship targets and
#              string foreign_keys to avoid import-time resolution and
#              circular-import problems. Keep IDs and FK types consistent
#              with BankTransaction (both use Integer here).
# =============================================================================
from datetime import datetime

from ..extensions import db


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"
    __table_args__ = {"extend_existing": True}
    __table_args__ = (
        db.Index("ix_account_number", "account_number"),
        db.Index("ix_user_id", "user_id"),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    account_type = db.Column(db.String(32))
    account_number = db.Column(db.String(64), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_synced_at = db.Column(db.DateTime)
    trace_status = db.Column(db.String(32), default="healthy")

    # Relationship to User (string target avoids top-level import)
    user = db.relationship("User", back_populates="bank_accounts")

    # Use string foreign_keys so SQLAlchemy resolves them lazily against the
    # declarative registry; this avoids referencing BankTransaction at import time.
    outgoing_transactions = db.relationship(
        "BankTransaction",
        foreign_keys="BankTransaction.from_account_id",
        back_populates="from_account",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    incoming_transactions = db.relationship(
        "BankTransaction",
        foreign_keys="BankTransaction.to_account_id",
        back_populates="to_account",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<BankAccount id={self.id} user={self.user_id} balance={self.balance}>"
