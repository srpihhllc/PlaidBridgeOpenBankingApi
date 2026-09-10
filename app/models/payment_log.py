# =============================================================================
# FILE: app/models/payment_log.py
# DESCRIPTION: Cockpit‑grade PaymentLog model aligned with UUID user IDs,
#              cascade delete semantics, and explicit two-way relationships.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class PaymentLog(db.Model):
    __tablename__ = "payment_log"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    payment_processor_id = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), nullable=False, default="USD")

    status = db.Column(
        db.String(50),
        nullable=False,
    )  # e.g., 'pending', 'succeeded', 'failed'

    transaction_type = db.Column(
        db.String(50),
        nullable=False,
    )  # e.g., 'ach', 'card', 'crypto'

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # -------------------------------------------------------------------------
    # Relationships (The Runtime Symmetry Fix)
    # -------------------------------------------------------------------------

    # ⭐ SENIOR FIX: Swapped back_populates for explicit dynamic backref.
    # This dynamically injects 'payment_logs' into the User mapper frame at runtime,
    # avoiding compile-time KeyError/InvalidRequestError checks.
    user = db.relationship(
        "User",
        backref=db.backref(
            "payment_logs", lazy="dynamic", passive_deletes=True
        ),
    )

    def __repr__(self):
        return f"<PaymentLog id={self.id} user_id={self.user_id} status='{self.status}'>"
