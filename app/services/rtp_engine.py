# =============================================================================
# FILE: app/services/rtp_engine.py
#
# DESCRIPTION:
#     Production-grade RTP (Real-Time Payments) orchestration engine.
#
# PURPOSE:
#     Provides real-time payment lifecycle management for
#     The Clearing House RTP rail.
#
# DESIGN GOALS:
#
#     - idempotent
#     - concurrency-safe
#     - settlement-safe
#     - audit-friendly
#     - treasury-ready
#     - sponsor-bank ready
#     - reconciliation-friendly
#
# IMPORTANT:
#
#     This engine DOES NOT:
#
#         - adjust wallet balances
#         - post journal entries
#         - perform reconciliation
#         - connect directly to TCH RTP
#
#     Those concerns belong to:
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


class RTPError(Exception):
    """
    Base RTP exception.
    """


class RTPValidationError(
    RTPError
):
    """
    RTP validation failure.
    """


class RTPEngine:

    MAX_RTP_AMOUNT = Decimal(
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
        """
        Create RTP payment instruction.

        Idempotent by design.
        """

        amount = Decimal(str(amount))

        if amount <= 0:
            raise RTPValidationError(
                "Amount must be positive"
            )

        if amount > RTPEngine.MAX_RTP_AMOUNT:
            raise RTPValidationError(
                "RTP transfer exceeds maximum"
            )

        if (
            debit_wallet_id
            == credit_wallet_id
        ):
            raise RTPValidationError(
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
            payment_type=PaymentType.RTP,
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
        Validate RTP payment.
        """

        if payment.amount <= 0:
            raise RTPValidationError(
                "Invalid RTP amount"
            )

        if (
            payment.debit_wallet_id
            == payment.credit_wallet_id
        ):
            raise RTPValidationError(
                "Invalid RTP participants"
            )

        if (
            payment.payment_type
            != PaymentType.RTP
        ):
            raise RTPValidationError(
                "Payment is not RTP"
            )

        return True

    @staticmethod
    def mark_processing(
        payment: PaymentInstruction,
    ) -> PaymentInstruction:

        RTPEngine.validate(
            payment
        )

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
        RTP settlement path.

        RTP is real-time.
        Settlement should occur
        immediately after validation.
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
        Full RTP lifecycle.

        Validation
            ↓
        Processing
            ↓
        Settlement
        """

        RTPEngine.validate(
            payment
        )

        RTPEngine.mark_processing(
            payment
        )

        RTPEngine.settle(
            payment
        )

        return payment

    @staticmethod
    def healthcheck() -> dict:
        """
        Engine telemetry endpoint.
        """

        return {
            "engine": "rtp",
            "status": "healthy",
            "rail": "real_time",
        }

    @staticmethod
    def metrics() -> dict:
        """
        Dashboard metrics payload.

        Safe for telemetry
        and cockpit widgets.
        """

        pending_count = (
            PaymentInstruction.query
            .filter_by(
                payment_type=PaymentType.RTP,
                status=PaymentStatus.PENDING,
            )
            .count()
        )

        processing_count = (
            PaymentInstruction.query
            .filter_by(
                payment_type=PaymentType.RTP,
                status=PaymentStatus.PROCESSING,
            )
            .count()
        )

        settled_count = (
            PaymentInstruction.query
            .filter_by(
                payment_type=PaymentType.RTP,
                status=PaymentStatus.SETTLED,
            )
            .count()
        )

        failed_count = (
            PaymentInstruction.query
            .filter_by(
                payment_type=PaymentType.RTP,
                status=PaymentStatus.FAILED,
            )
            .count()
        )

        return {
            "pending": pending_count,
            "processing": processing_count,
            "settled": settled_count,
            "failed": failed_count,
        }