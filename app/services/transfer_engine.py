from app.extensions import db
from app.models.idempotency_key import IdempotencyKey
from app.services.ledger_engine import LedgerEngine


class TransferEngine:
    @staticmethod
    def transfer(
        *,
        idempotency_key: str,
        debit_account_id: int,
        credit_account_id: int,
        amount,
    ) -> dict[str, str]:
        existing = IdempotencyKey.query.filter_by(
            idempotency_key=idempotency_key
        ).first()

        if existing:
            return {"status": "duplicate"}

        LedgerEngine.post(
            debit_account_id=debit_account_id,
            credit_account_id=credit_account_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )

        key = IdempotencyKey(
            idempotency_key=idempotency_key,
            response_hash="posted",
        )
        db.session.add(key)
        db.session.commit()

        return {"status": "posted"}
