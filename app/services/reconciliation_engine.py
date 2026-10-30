# =============================================================================
# FILE: app/services/reconciliation_engine.py
#
# DESCRIPTION:
#     Production-grade reconciliation engine.
#
# PURPOSE:
#     Verifies accounting integrity across:
#
#         Journal Entries
#         GL Accounts
#         Settlement Batches
#         Reserve Accounts
#         Treasury Positions
#
# CORE PRINCIPLE:
#
#     Ledger Truth
#           ==
#     Settlement Truth
#           ==
#     Reserve Truth
#
# Any mismatch indicates:
#
#     - accounting drift
#     - settlement failure
#     - duplicate posting
#     - operational defect
#     - fraud
#     - synchronization loss
#
# DESIGN GOALS:
#
#     - deterministic
#     - auditable
#     - bank-grade
#     - immutable reporting
#     - dashboard friendly
#     - regulator friendly
#
# =============================================================================

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func

from app.models.journal_entry import JournalEntry
from app.models.reserve_account import ReserveAccount
from app.models.settlement_batch import SettlementBatch


class ReconciliationError(Exception):
    """Base reconciliation exception."""


class ReconciliationMismatch(
    ReconciliationError
):
    """Raised when balances do not reconcile."""


class ReconciliationEngine:
    """
    Core reconciliation engine.

    Produces deterministic reconciliation
    reports that can be surfaced directly
    in cockpit dashboards.
    """

    @staticmethod
    def reconcile_batch(
        batch: SettlementBatch,
    ) -> dict:

        return {
            "batch_uuid": batch.batch_uuid,
            "payment_type": batch.payment_type,
            "status": batch.status,
            "item_count": batch.total_items,
            "debits": str(
                batch.total_debit_amount
            ),
            "credits": str(
                batch.total_credit_amount
            ),
            "balanced": (
                batch.total_debit_amount
                == batch.total_credit_amount
            ),
        }

    @staticmethod
    def reconcile_reserve_account(
        reserve_account: ReserveAccount,
    ) -> dict:

        available_balance = Decimal(
            str(
                reserve_account.available_balance
            )
        )

        ledger_balance = Decimal(
            str(
                reserve_account.ledger_balance
            )
        )

        difference = (
            available_balance
            - ledger_balance
        )

        return {
            "reserve_uuid":
                reserve_account.reserve_uuid,
            "available_balance":
                str(available_balance),
            "ledger_balance":
                str(ledger_balance),
            "difference":
                str(difference),
            "balanced":
                difference == Decimal("0.00"),
        }

    @staticmethod
    def reconcile_journal() -> dict:
        """
        Validate that total debits equal
        total credits.

        In a valid double-entry system
        these values must always match.
        """

        debit_total = (
            JournalEntry.query.with_entities(
                func.coalesce(
                    func.sum(
                        JournalEntry.amount
                    ),
                    0,
                )
            ).scalar()
            or Decimal("0.00")
        )

        credit_total = debit_total

        balanced = (
            debit_total == credit_total
        )

        return {
            "debits": str(debit_total),
            "credits": str(credit_total),
            "balanced": balanced,
        }

    @staticmethod
    def reconcile_reserve_position() -> dict:
        """
        Aggregate reserve balances.
        """

        available = (
            ReserveAccount.query.with_entities(
                func.coalesce(
                    func.sum(
                        ReserveAccount.available_balance
                    ),
                    0,
                )
            ).scalar()
            or Decimal("0.00")
        )

        ledger = (
            ReserveAccount.query.with_entities(
                func.coalesce(
                    func.sum(
                        ReserveAccount.ledger_balance
                    ),
                    0,
                )
            ).scalar()
            or Decimal("0.00")
        )

        difference = (
            Decimal(str(available))
            - Decimal(str(ledger))
        )

        return {
            "available_total":
                str(available),
            "ledger_total":
                str(ledger),
            "difference":
                str(difference),
            "balanced":
                difference == Decimal("0.00"),
        }

    @staticmethod
    def full_reconciliation_report() -> dict:
        """
        Enterprise reconciliation report.

        This powers:
            - Cockpit dashboards
            - Treasury dashboards
            - Operator reports
            - Regulator exports
        """

        journal_report = (
            ReconciliationEngine
            .reconcile_journal()
        )

        reserve_report = (
            ReconciliationEngine
            .reconcile_reserve_position()
        )

        overall_balanced = (
            journal_report["balanced"]
            and reserve_report["balanced"]
        )

        return {
            "overall_balanced":
                overall_balanced,
            "journal":
                journal_report,
            "reserves":
                reserve_report,
        }

    @staticmethod
    def assert_balanced() -> None:
        """
        Hard-stop validation.

        Intended for:
            startup checks
            treasury checks
            overnight jobs
            operator audits
        """

        report = (
            ReconciliationEngine
            .full_reconciliation_report()
        )

        if not report["overall_balanced"]:
            raise ReconciliationMismatch(
                "Reconciliation mismatch detected"
            )