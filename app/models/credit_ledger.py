# app/models/credit_ledger.py

from app.extensions import db


class CreditLedger(db.Model):
    __tablename__ = "credit_ledger"

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

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

    user = db.relationship("User", back_populates="credit_ledger_entries")
