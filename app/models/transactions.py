# =============================================================================
# FILE: app/models/transactions.py
# DESCRIPTION: Defines the Transaction model and its relationships. FraudReport
#              is defined in app/models/fraud_report.py to avoid duplicate
#              registrations in SQLAlchemy's declarative registry.
# =============================================================================

import uuid
from datetime import datetime, timezone
from typing import Any

from ..extensions import db

# Flask-SQLAlchemy's dynamically provided Model may not be visible to mypy.
Model: Any = db.Model


class Transaction(Model):
    __tablename__ = "transactions"
    __table_args__ = {"extend_existing": True}

    # -------------------------------------------------------------------------
    # Primary Key
    # -------------------------------------------------------------------------
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # -------------------------------------------------------------------------
    # Foreign Keys
    # -------------------------------------------------------------------------
    # MUST match User.id (String(36))
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Core Transaction Fields
    # -------------------------------------------------------------------------
    plaid_account_id = db.Column(db.String(120))
    account_id = db.Column(db.String(120))
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(5), default="USD")
    date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(255))
    category = db.Column(db.String(255))
    description = db.Column(db.String(255), nullable=True)
    is_pending = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    # -------------------------------------------------------------------------
    # Plaid-style enrichment fields
    # -------------------------------------------------------------------------
    mcc = db.Column(db.String(10), nullable=True)
    fraud_score = db.Column(db.Float, nullable=True)
    cluster = db.Column(db.String(50), nullable=True)
    category_hierarchy = db.Column(db.JSON, nullable=True)
    location = db.Column(db.JSON, nullable=True)
    payment_meta = db.Column(db.JSON, nullable=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = db.relationship("User", back_populates="transactions")

    fraud_reports = db.relationship(
        "FraudReport",
        back_populates="transaction",
        lazy="dynamic",
        passive_deletes=True,
    )

    complaint_logs = db.relationship(
        "ComplaintLog",
        back_populates="transaction",
        lazy="dynamic",
        passive_deletes=True,
    )

    # Named audit_logs to avoid collision with User.audit_events.
    audit_logs = db.relationship(
        "AuditLog",
        back_populates="transaction",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} user_id={self.user_id} "
            f"amount={self.amount}>"
        )