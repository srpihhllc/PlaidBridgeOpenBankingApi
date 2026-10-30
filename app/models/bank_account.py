"""BankAccount model using string-based relationship targets and foreign keys
to avoid import-time resolution and circular-import problems. Keep IDs and
foreign-key types consistent with BankTransaction (both use Integer here).
"""

from datetime import datetime, timezone

from ..extensions import db


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"
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
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    last_synced_at = db.Column(db.DateTime)
    trace_status = db.Column(db.String(32), default="healthy")

    # Relationship to User; the string target avoids a top-level import.
    user = db.relationship("User", back_populates="bank_accounts")

    # String foreign keys let SQLAlchemy resolve BankTransaction lazily.
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

    def __repr__(self) -> str:
        return (
            f"<BankAccount id={self.id} user={self.user_id} "
            f"balance={self.balance}>"
        )