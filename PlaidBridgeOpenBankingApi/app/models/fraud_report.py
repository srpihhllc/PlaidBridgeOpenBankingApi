# =============================================================================
# FILE: app/models/fraud_report.py
# DESCRIPTION: Cockpit‑grade FraudReport model with explicit relationships,
#              UUID primary key, classification fields, and operator‑friendly
#              serialization helpers.
# =============================================================================
import uuid
from datetime import datetime

from ..extensions import db


class FraudReport(db.Model):
    __tablename__ = "fraud_reports"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # -------------------------------------------------------------------------
    # Foreign keys
    # -------------------------------------------------------------------------
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    transaction_id = db.Column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # Classification and status
    # -------------------------------------------------------------------------
    category = db.Column(db.String(64), nullable=False, default="fraud")
    severity = db.Column(db.String(16), nullable=False, default="medium")
    status = db.Column(db.String(32), nullable=False, default="open")

    # -------------------------------------------------------------------------
    # Details
    # -------------------------------------------------------------------------
    description = db.Column(db.Text, nullable=True)
    evidence = db.Column(db.Text, nullable=True)

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user = db.relationship("User", back_populates="fraud_reports")
    transaction = db.relationship("Transaction", back_populates="fraud_reports")

    # -------------------------------------------------------------------------
    # Serialization helpers
    # -------------------------------------------------------------------------
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "transaction_id": self.transaction_id,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    def __repr__(self):
        return f"<FraudReport #{self.id} user={self.user_id} status={self.status}>"
