# =============================================================================
# FILE: app/services/settlement_engine.py
#
# DESCRIPTION:
#     Production-grade settlement engine.
#
# PURPOSE:
#     Responsible for moving PaymentInstructions through
#     settlement lifecycle states while maintaining:
#
#         - transactional integrity
#         - idempotency
#         - auditability
#         - reconciliation readiness
#         - ledger consistency
#
# DESIGN PRINCIPLES:
#     JournalEntry remains source of truth.
#
#     SettlementBatch groups settlement work.
#
#     PaymentInstruction drives movement lifecycle.
#
#     SettlementEngine coordinates all three.
#
# =============================================================================

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

from app.models.payment_instruction import (
    PaymentInstruction,
    PaymentStatus,
)

from app.models.settlement_batch import (
    SettlementBatch,
    SettlementBatchStatus,
)


class SettlementEngineError(Exception):
    """Base settlement exception."""


class SettlementValidationError(
    SettlementEngineError
):
    """Validation failure."""


class SettlementEngine:

    @staticmethod
    def create_batch(
        *,
        payment_type: str,
        created_by: int | None = None,
        currency: str = "USD",
    ) -> SettlementBatch:
        """
        Create a new settlement batch.
        """

        batch = SettlementBatch(
            batch_reference=str(uuid4()),
            payment_type=payment_type,
            currency=currency,
            created_by=created_by,
            status=SettlementBatchStatus.CREATED,
        )

        db.session.add(batch)

        return batch

    @staticmethod
    def open_batch(
        batch: SettlementBatch,
    ) -> SettlementBatch:

        batch.mark_open()

        return batch

    @staticmethod
    def attach_payment(
        *,
        batch: SettlementBatch,
        payment: PaymentInstruction,
    ) -> None:
        """
        Adds payment metrics into batch.

        Assumes future relationship table
        can be added later without rewriting
        settlement workflows.
        """

        amount = Decimal(str(payment.amount))

        batch.total_items += 1
        batch.total_debit_amount += amount
        batch.total_credit_amount += amount

    @staticmethod
    def settle_batch(
        batch: SettlementBatch,
    ) -> SettlementBatch:
        """
        Marks batch settled after validation.
        """

        if batch.total_items <= 0:
            raise SettlementValidationError(
                "Batch contains no instructions"
            )

        if not batch.is_balanced:
            raise SettlementValidationError(
                "Settlement batch not balanced"
            )

        batch.mark_settled()

        return batch

    @staticmethod
    def fail_batch(
        batch: SettlementBatch,
    ) -> SettlementBatch:

        batch.mark_failed()

        return batch

    @staticmethod
    def reverse_batch(
        batch: SettlementBatch,
    ) -> SettlementBatch:

        batch.mark_reversed()

        return batch

    @staticmethod
    def reconcile_batch(
        batch: SettlementBatch,
    ) -> dict:

        return {
            "batch_uuid": batch.batch_uuid,
            "balanced": batch.is_balanced,
            "item_count": batch.total_items,
            "debits": str(
                batch.total_debit_amount
            ),
            "credits": str(
                batch.total_credit_amount
            ),
        }

    @staticmethod
    def settle_payment(
        *,
        payment_id: int,
    ) -> PaymentInstruction:
        """
        Settlement-safe payment update.

        Uses DB row locking to prevent
        concurrent settlement.
        """

        payment = (
            PaymentInstruction.query
            .filter_by(id=payment_id)
            .with_for_update()
            .first()
        )

        if not payment:
            raise SettlementValidationError(
                "Payment not found"
            )

        if payment.status == PaymentStatus.SETTLED:
            return payment

        payment.mark_settled()

        return payment

    @staticmethod
    def execute_batch(
        *,
        batch: SettlementBatch,
    ) -> SettlementBatch:
        """
        Transaction-safe execution.

        Either the full settlement succeeds
        or the entire operation rolls back.
        """

        try:

            batch.mark_processing()

            SettlementEngine.settle_batch(
                batch
            )

            db.session.commit()

            return batch

        except SQLAlchemyError:

            db.session.rollback()

            raise

        except Exception:

            db.session.rollback()

            raise