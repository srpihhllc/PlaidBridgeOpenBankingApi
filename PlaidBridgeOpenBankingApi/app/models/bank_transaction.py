from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.extensions import db

class BankTransaction(db.Model):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True)

    # Ensure ON DELETE CASCADE appears in the emitted DDL by setting ondelete="CASCADE"
    from_account_id = Column(
        Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=True
    )
    to_account_id = Column(
        Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=True
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

    # (Optional) relationships  keep them read-only for cascades handled by DB.
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
