# =============================================================================
# FILE: app/services/fednow_engine.py
#
# DESCRIPTION:
#     Production-grade FedNow orchestration engine.
#
# PURPOSE:
#     Provides real-time payment workflow management for
#     FedNow-based transfers.
#
# DESIGN GOALS:
#
#     - idempotent
#     - transaction-safe
#     - real-time settlement
#     - treasury-ready
#     - reconciliation-friendly
#     - sponsor-bank compatible
#     - audit-friendly
#
# IMPORTANT:
#
#     This engine does NOT:
#
#         - connect directly to the Federal Reserve
#         - manage customer balances
#         - post ledger entries
#
#     Those responsibilities belong to:
#
#         LedgerEngine
#         SettlementEngine
#         ReconciliationEngine
#
# =============================================================================

from __future__ import annotations

from decimal import Decimal

from app.extensions import db

from app.models.payment_instruction import (
    PaymentInstruction,
    PaymentStatus,
    PaymentType,
)

from app.services.settlement_engine import (
    SettlementEngine,
)


class FedNowError(Exception):
    """Base FedNow exception."""


class FedNowValidationError(
    FedNowError
):
    """FedNow validation exception."""


class FedNowEngine:

    MAX_FEDNOW_AMOUNT = Decimal(
        "500000.00"
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
        """
        Create a FedNow payment instruction.

        Idempotent by design.
        """

        amount = Decimal(str(amount))

        if amount <= 0:
            raise FedNowValidationError(
                "Amount must be positive"
            )

        if amount > FedNowEngine.MAX_FEDNOW_AMOUNT:
            raise FedNowValidationError(
                "FedNow transfer exceeds maximum"
            )

        if (
            debit_wallet_id
            == credit_wallet_id
        ):
            raise FedNowValidationError(
                "Debit and credit wallets cannot match"
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
            payment_type=PaymentType.FEDNOW,
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
        """
        Validate FedNow payment.
        """

        if payment.amount <= 0:
            raise FedNowValidationError(
                "Invalid amount"
            )

        if (
            payment.debit_wallet_id
            == payment.credit_wallet_id
        ):
            raise FedNowValidationError(
                "Invalid payment participants"
            )

        return True

    @staticmethod
    def mark_processing(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:
        """
        Place payment into processing state.
        """

        FedNowEngine.validate(payment)

        payment.status = (
            PaymentStatus.PROCESSING
        )

        return payment

    @staticmethod
    def mark_failed(
        payment: PaymentInstruction,
        *,
        reason: str | None = None,
    ) -> PaymentInstruction:
        """
        Mark payment failed.
        """

        payment.status = (
            PaymentStatus.FAILED
        )

        if reason:
            payment.memo = (
                f"{payment.memo or ''} "
                f"[FAILED:{reason}]"
            ).strip()

        return payment

    @staticmethod
    def settle(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:
        """
        Real-time settlement path.

        Unlike ACH, FedNow should
        generally settle immediately.
        """

        SettlementEngine.settle_payment(
            payment_id=payment.id
        )

        return payment

    @staticmethod
    def reverse(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:
        """
        Administrative reversal workflow.
        """

        payment.status = (
            PaymentStatus.REVERSED
        )

        return payment

    @staticmethod
    def process(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:
        """
        Full payment lifecycle.

        Validation
            ↓
        Processing
            ↓
        Settlement
        """

        FedNowEngine.validate(payment)

        FedNowEngine.mark_processing(
            payment
        )

        FedNowEngine.settle(
            payment
        )

        return payment

    @staticmethod
    def healthcheck() -> dict:
        """
        Engine health status.

        Used by:
            - Cockpit
            - Telemetry
            - Operators
            - Treasury dashboards
        """

        return {
            "engine": "fednow",
            "status": "healthy",
            "rail": "real_time",
        }