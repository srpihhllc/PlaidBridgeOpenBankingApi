# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/journal_entry.py

from app.extensions import db


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"

    id = db.Column(
        db.BigInteger().with_variant(
            db.Integer,
            "sqlite",
        ),
        primary_key=True,
        autoincrement=True,
    )

    debit_account_id = db.Column(
        db.BigInteger,
        db.ForeignKey("gl_accounts.id"),
        nullable=False,
        index=True,
    )

    credit_account_id = db.Column(
        db.BigInteger,
        db.ForeignKey("gl_accounts.id"),
        nullable=False,
        index=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    currency = db.Column(
        db.String(8),
        nullable=False,
        default="USD",
        server_default="USD",
    )

    reference_id = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    description = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<JournalEntry "
            f"id={self.id} "
            f"reference_id={self.reference_id} "
            f"amount={self.amount}>"
        )