from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.extensions import db

class BankAccount(db.Model):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    # user_id must reference users.id so relationships can be resolved
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    account_type = Column(String(32))
    account_number = Column(String(64))
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship back to User  User likely defines `bank_accounts`
    user = relationship("User", back_populates="bank_accounts")

    # Use passive_deletes=True so SQLAlchemy defers deletes to the DB cascade.
    transactions_from = relationship(
        "BankTransaction",
        foreign_keys="BankTransaction.from_account_id",
        back_populates="from_account",
        passive_deletes=True,
        cascade="save-update, merge",
    )

    transactions_to = relationship(
        "BankTransaction",
        foreign_keys="BankTransaction.to_account_id",
        back_populates="to_account",
        passive_deletes=True,
        cascade="save-update, merge",
    )
