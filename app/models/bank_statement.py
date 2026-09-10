# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/banking/bank_statement.py

from datetime import datetime, timezone

from ..extensions import db


class BankStatement(db.Model):
    __tablename__ = "bank_statements"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    bank = db.Column(db.String(100), nullable=False)
    account = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    txn_count = db.Column(db.Integer, default=0)
    source_api = db.Column(db.String(64))
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="bank_statements")
