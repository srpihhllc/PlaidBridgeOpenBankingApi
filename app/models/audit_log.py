# =============================================================================
# FILE: app/models/audit_log.py
# DESCRIPTION: FinancialAuditLog (compliance-grade) and AuditLog (transaction-
#              linked cockpit analytics). Fully aligned with UUID User.id.
# =============================================================================

from datetime import datetime

from app.extensions import db


# -------------------------------------------------------------------------
# Compliance-grade audit log (operator actions, violations, locks, etc.)
# -------------------------------------------------------------------------
class FinancialAuditLog(db.Model):
    __tablename__ = "financial_audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK — must match User.id (String(36))
    actor_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action_type = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    def __repr__(self):
        return f"<FinancialAuditLog id={self.id} action_type={self.action_type}>"


# -------------------------------------------------------------------------
# Cockpit‑grade audit log for transaction‑linked events
# -------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK — must match User.id (String(36))
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional link to a transaction (mock or real)
    # FIXED: Changed from db.Integer to db.String(36) to match transactions.id UUID
    transaction_id = db.Column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Event classification (e.g., "mock_bank_transfer_audit")
    event_type = db.Column(db.String(64), nullable=False, index=True)

    # Structured JSON payload (risk flags, direction, metadata, etc.)
    payload = db.Column(db.JSON, nullable=False, default=dict)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # Relationships for cockpit drilldowns
    # NOTE: No imports — string-based relationships prevent circular imports
    user = db.relationship("User", back_populates="audit_events", lazy=True)
    transaction = db.relationship("Transaction", back_populates="audit_events", lazy=True)

    def __repr__(self):
        return f"<AuditLog id={self.id} event_type={self.event_type}>"

