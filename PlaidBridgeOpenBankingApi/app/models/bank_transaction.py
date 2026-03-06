from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from app.extensions import db

class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True)

    # Columns reference bank_accounts via explicit ForeignKeyConstraint below.
    # Keep columns simple here; avoid Column-level ForeignKey to prevent duplicate constraints.
    from_account_id = Column(Integer, nullable=True)
    to_account_id = Column(Integer, nullable=True)

    # Explicit ForeignKeyConstraint entries (named, with ON DELETE CASCADE)
    __table_args__ = (
        ForeignKeyConstraint(
            ["from_account_id"],
            ["bank_accounts.id"],
            name="fk_bank_transactions_from_account_id_bank_accounts",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["to_account_id"],
            ["bank_accounts.id"],
            name="fk_bank_transactions_to_account_id_bank_accounts",
            ondelete="CASCADE",
        ),
    )

    amount = Column(Float, nullable=False)
    txn_type = Column(String(32))
    method = Column(String(64))
    timestamp = Column(DateTime, default=datetime.utcnow)
    ach_trace_number = Column(String(20))
    ach_sec_code = Column(String(10))
    wire_reference = Column(String(50))
    originating_routing = Column(String(9))
    receiving_routing = Column(String(9))
    payment_channel = Column(String(20))

    # Relationships  leave passive_deletes=True so DB handles cascade semantics.
    from_account = relationship(
        "BankAccount",
        foreign_keys=[from_account_id],
        back_populates="transactions_from",
        passive_deletes=True,
    )
    to_account = relationship(
        "BankAccount",
        foreign_keys=[to_account_id],
        back_populates="transactions_to",
        passive_deletes=True,
    )
