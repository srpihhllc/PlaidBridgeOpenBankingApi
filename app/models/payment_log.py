# =============================================================================
# FILE: app/models/payment_log.py
# DESCRIPTION: Payment logs linked to UUID-based user IDs with cascade delete
#              semantics and a dynamically defined User relationship.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class PaymentLog(db.Model):
    __tablename__ = "payment_log"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    payment_processor_id = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False, default="USD")

    status = db.Column(db.String(50), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "payment_logs",
            lazy="dynamic",
            passive_deletes=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentLog id={self.id} user_id={self.user_id} "
            f"status='{self.status}'>"
        )