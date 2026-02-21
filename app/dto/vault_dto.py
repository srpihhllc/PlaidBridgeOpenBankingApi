# app/dto/vault_dto.py

from dataclasses import dataclass


@dataclass
class VaultTransactionDTO:
    id: int
    amount: float
    currency: str
    status: str
    created_at: str

    @staticmethod
    def from_model(model):
        return VaultTransactionDTO(
            id=model.id,
            amount=model.amount,
            currency=model.currency,
            status=model.status,
            created_at=model.created_at.isoformat(),
        )
