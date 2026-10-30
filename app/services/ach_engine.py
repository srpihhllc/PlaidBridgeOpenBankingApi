# =============================================================================
# FILE: app/services/ach_engine.py
#
# DESCRIPTION:
#     Production-grade ACH orchestration engine.
#
# PURPOSE:
#     Provides ACH transfer lifecycle management.
#
# DOES:
#     - create ACH instructions
#     - validate ACH transfers
#     - build settlement batches
#     - support reconciliation
#     - support idempotency
#
# DOES NOT:
#     - talk directly to NACHA
#     - connect directly to sponsor bank
#     - move ledger balances
#
# Those responsibilities belong to:
#
#     LedgerEngine
#     SettlementEngine
#     ReconciliationEngine
#
# =============================================================================

from __future__ import annotations

from decimal import Decimal

from app.extensions import db

from app.models.payment_instruction import (
    PaymentInstruction,
    PaymentType,
    PaymentStatus,
)

from app.services.settlement_engine import (
    SettlementEngine,
)


class ACHEngineError(Exception):
    """Base ACH exception."""


class ACHValidationError(
    ACHEngineError
):
    """ACH validation failure."""


class ACHEngine:

    MAX_ACH_AMOUNT = Decimal(
        "1000000.00"
    )

    @staticmethod
    def create_transfer(
        *,
        debit_wallet_id: int,
        credit_wallet_id: int,
        amount,
        idempotency_key: str,
        memo: str | None = None,
        created_by: int | None = None,
    ) -> PaymentInstruction:

        amount = Decimal(str(amount))

        if amount <= 0:
            raise ACHValidationError(
                "Amount must be positive"
            )

        if amount > ACHEngine.MAX_ACH_AMOUNT:
            raise ACHValidationError(
                "ACH transfer exceeds limit"
            )

        existing = (
            PaymentInstruction.query
            .filter_by(
                idempotency_key=idempotency_key
            )
            .first()
        )

        if existing:
            return existing

        payment = PaymentInstruction(
            payment_type=PaymentType.ACH,
            status=PaymentStatus.PENDING,
            debit_wallet_id=debit_wallet_id,
            credit_wallet_id=credit_wallet_id,
            amount=amount,
            memo=memo,
            idempotency_key=idempotency_key,
            posted_by=created_by,
        )

        db.session.add(payment)

        return payment

    @staticmethod
    def validate(
        payment: PaymentInstruction,
    ) -> bool:

        if payment.amount <= 0:
            raise ACHValidationError(
                "Invalid ACH amount"
            )

        if (
            payment.debit_wallet_id
            == payment.credit_wallet_id
        ):
            raise ACHValidationError(
                "Debit and credit wallets cannot match"
            )

        return True

    @staticmethod
    def mark_processing(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:

        ACHEngine.validate(payment)

        payment.status = (
            PaymentStatus.PROCESSING
        )

        return payment

    @staticmethod
    def mark_failed(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:

        payment.status = (
            PaymentStatus.FAILED
        )

        return payment

    @staticmethod
    def settle(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:

        SettlementEngine.settle_payment(
            payment_id=payment.id
        )

        return payment

    @staticmethod
    def build_settlement_batch(
        *,
        payment_type: str = PaymentType.ACH,
        created_by: int | None = None,
    ):

        batch = (
            SettlementEngine.create_batch(
                payment_type=payment_type,
                created_by=created_by,
            )
        )

        SettlementEngine.open_batch(
            batch
        )

        return batch