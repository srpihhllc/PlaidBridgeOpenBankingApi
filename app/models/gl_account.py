# app/models/gl_account.py

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from app.extensions import db


class GLAccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class GLAccount(db.Model):
    """General Ledger Account.

    Every banking movement must ultimately debit one GL account
    and credit another.
    """

    __tablename__ = "gl_accounts"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    code = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        index=True,
    )

    name = db.Column(
        db.String(128),
        nullable=False,
    )

    account_type = db.Column(
        db.String(32),
        nullable=False,
        index=True,
    )

    active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )

    journal_debits = db.relationship(
        "JournalEntry",
        foreign_keys="JournalEntry.debit_account_id",
        lazy="dynamic",
    )

    journal_credits = db.relationship(
        "JournalEntry",
        foreign_keys="JournalEntry.credit_account_id",
        lazy="dynamic",
    )

    @property
    def balance(self) -> Decimal:
        debit_total = sum(
            (entry.amount for entry in self.journal_debits),
            Decimal("0.00"),
        )
        credit_total = sum(
            (entry.amount for entry in self.journal_credits),
            Decimal("0.00"),
        )
        return debit_total - credit_total

    def __repr__(self) -> str:
        return f"<GLAccount {self.code} {self.name}>"
