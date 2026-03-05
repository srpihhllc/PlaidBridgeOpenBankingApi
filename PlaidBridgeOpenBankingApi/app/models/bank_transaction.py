# =============================================================================
# FILE: app/models/bank_transaction.py
# DESCRIPTION: BankTransaction model. Uses integer FKs matching BankAccount.id,
#              string-based relationship targets and column-based foreign_keys
#              to avoid import-time coupling and circular imports.
# =============================================================================
from datetime import datetime

from app.extensions import db


class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"

    id = db.Column(db.Integer, primary_key=True)
    from_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=True)

    amount = db.Column(db.Float, nullable=False)
    txn_type = db.Column(db.String(32))  # transfer, ach, wire, internal
    method = db.Column(db.String(64))  # online, teller, mobile
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # 🔹 ACH / Wire metadata (optional but realistic)
    ach_trace_number = db.Column(db.String(20), nullable=True)
    ach_sec_code = db.Column(db.String(10), nullable=True)  # PPD, CCD, WEB, TEL
    wire_reference = db.Column(db.String(50), nullable=True)
    originating_routing = db.Column(db.String(9), nullable=True)
    receiving_routing = db.Column(db.String(9), nullable=True)
    payment_channel = db.Column(db.String(20), nullable=True)  # ACH, WIRE, INTERNAL

    from_account = db.relationship(
        "BankAccount",
        back_populates="outgoing_transactions",
        foreign_keys=[from_account_id],
        lazy=True,
        passive_deletes=True,
    )

    to_account = db.relationship(
        "BankAccount",
        back_populates="incoming_transactions",
        foreign_keys=[to_account_id],
        lazy=True,
        passive_deletes=True,
    )

    def __repr__(self):
        return (
            f"<BankTransaction id={self.id} from={self.from_account_id} "
            f"to={self.to_account_id} amount={self.amount}>"
        )
