# =============================================================================
# FILE: app/models/audit_log.py
# DESCRIPTION: FinancialAuditLog (compliance-grade) and AuditLog (transaction-
#              linked cockpit analytics). Fully aligned with UUID User.id.
# =============================================================================

from datetime import datetime, timezone
from ..extensions import db


def _get_naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# -------------------------------------------------------------------------
# Compliance-grade audit log (operator actions, violations, locks, etc.)
# -------------------------------------------------------------------------
class FinancialAuditLog(db.Model):
    __tablename__ = "financial_audit_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

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
        default=_get_naive_utc_now,
        nullable=False,
        index=True,
    )

    # Core Relationships
    actor = db.relationship("User", backref=db.backref("financial_audit_logs", lazy="dynamic"))

    def __repr__(self):
        return f"<FinancialAuditLog id={self.id} action_type={self.action_type}>"


# -------------------------------------------------------------------------
# Cockpit‑grade audit log for transaction‑linked events
# -------------------------------------------------------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    transaction_id = db.Column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=_get_naive_utc_now,
        nullable=False,
        index=True,
    )

    # Core Relationships
    user = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))

    # -----------------------------------------------------------------------
    # Transaction Bridge (Fixes the InvalidRequestError: KeyError: 'transaction')
    # -----------------------------------------------------------------------
    transaction = db.relationship(
        "Transaction",
        back_populates="audit_logs",
    )

    def __repr__(self):
        return f"<AuditLog id={self.id} user_id={self.user_id} transaction_id={self.transaction_id}>"