# =============================================================================
# FILE: app/models/credit_ledger.py
# DESCRIPTION: Cockpit-grade CreditLedger model.
#              Represents credit lines, limits, and real-time balances for Users.
# =============================================================================
from ..extensions import db


class CreditLedger(db.Model):
    __tablename__ = "credit_ledger"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # -------------------------------------------------------------------------
    # Foreign Keys (Must match User.id String(36) UUID format)
    # -------------------------------------------------------------------------
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # Attributes
    # -------------------------------------------------------------------------
    card_id = db.Column(db.String(64), nullable=False)
    credit_limit = db.Column(db.Float, default=5000.00)
    balance_used = db.Column(db.Float, default=0.0)
    last_payment_ts = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )
    suspended = db.Column(db.Boolean, default=False)

    # -------------------------------------------------------------------------
    # Relationships (The Runtime Symmetry Fix)
    # -------------------------------------------------------------------------

    # ⭐ SENIOR FIX: Swapped back_populates for explicit dynamic backref.
    # This dynamically binds 'credit_ledger_entries' into the User mapper framework 
    # at initialization, bypassing strict missing-attribute compilation checks.
    user = db.relationship(
        "User",
        backref=db.backref("credit_ledger_entries", lazy="dynamic", passive_deletes=True),
    )

    def __repr__(self) -> str:
        return (
            f"<CreditLedger id={self.id} user_id='{self.user_id}' "
            f"limit={self.credit_limit} balance={self.balance_used}>"
        )