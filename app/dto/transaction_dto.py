# app/dto/transaction_dto.py

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TransactionDTO:
    id: str
    user_id: int
    amount: float
    currency: str
    category: str | None
    description: str | None
    date: str  # ISO string for template safety
    account: str | None
    verification_status: str | None
    mcc: str | None
    fraud_score: float | None
    cluster: str | None

    @staticmethod
    def from_model(txn) -> "TransactionDTO":
        return TransactionDTO(
            id=txn.id,
            user_id=txn.user_id,
            amount=float(txn.amount),
            currency=txn.currency or "USD",
            category=txn.category,
            description=txn.description,
            date=(txn.date.isoformat() if isinstance(txn.date, datetime) else str(txn.date)),
            # Plaid-style fields
            account=txn.account_id,
            verification_status="pending" if txn.is_pending else "posted",
            mcc=txn.mcc,
            fraud_score=txn.fraud_score,
            cluster=txn.cluster,
        )
