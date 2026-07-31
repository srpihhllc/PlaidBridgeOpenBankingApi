# =============================================================================
# FILE: app/models/complaint_log.py
# DESCRIPTION: Finalized relationship constraints coordinating both dynamic 
#              backrefs (for User) and strict back_populates (for Transaction).
# =============================================================================

from ..extensions import db


class ComplaintLog(db.Model):
    __tablename__ = "complaint_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Transaction.id is String(36) in your repo
    transaction_id = db.Column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    category = db.Column(db.String(64), nullable=True)
    description = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------

    # ⭐ User Fix: Kept as backref because User model lacks 'complaint_logs'.
    user = db.relationship(
        "User",
        backref=db.backref("complaint_logs", lazy="dynamic", passive_deletes=True),
    )

    # ⭐ Transaction Fix: Reverted to back_populates because Transaction 
    # explicitly defines 'complaint_logs' on its own end.
    transaction = db.relationship("Transaction", back_populates="complaint_logs")

    def __repr__(self):
        return f"<ComplaintLog {self.id}>"