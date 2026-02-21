# =============================================================================
# FILE: app/services/transaction_dto.py
# DESCRIPTION:
#   DTO + helpers for safe, UI-friendly transaction presentation.
# =============================================================================

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.models.transactions import Transaction


@dataclass
class TransactionDTO:
    id: str
    date: datetime
    account: str
    description: str
    category: str
    amount: float
    status: str
    verification_status: str

    @property
    def is_debit(self) -> bool:
        return self.amount < 0

    @property
    def is_credit(self) -> bool:
        return self.amount > 0


def from_model(txn: Transaction) -> TransactionDTO:
    return TransactionDTO(
        id=txn.id,
        date=txn.date,
        account=txn.account_id or txn.plaid_account_id or "N/A",
        description=txn.name or "(no description)",
        category=txn.category or "Uncategorized",
        amount=txn.amount or 0.0,
        status="pending" if getattr(txn, "is_pending", False) else "posted",
        verification_status=getattr(txn, "verification_status", "") or "unverified",
    )


def to_dtos(txns: Iterable[Transaction]) -> list[TransactionDTO]:
    return [from_model(t) for t in txns]
