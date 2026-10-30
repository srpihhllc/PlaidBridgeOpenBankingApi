# app/services/ledger_engine.py

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.models.gl_account import GLAccount
from app.models.journal_entry import JournalEntry


SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD"}


class LedgerError(Exception):
    """Base ledger exception."""


class LedgerValidationError(LedgerError):
    """Ledger validation failure."""


class DuplicateReferenceError(LedgerValidationError):
    """Duplicate accounting reference."""


class LedgerEngine:
    """Ledger operations for the current single-row journal schema."""

    @staticmethod
    def _validate_post(
        *,
        debit_account_id: int,
        credit_account_id: int,
        amount: Decimal | int | float | str,
        reference_id: str,
        currency: str,
    ) -> Decimal:
        try:
            parsed_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise LedgerValidationError("Invalid amount") from exc

        if not parsed_amount.is_finite() or parsed_amount <= Decimal("0"):
            raise LedgerValidationError("Amount must be greater than zero")

        if debit_account_id == credit_account_id:
            raise LedgerValidationError(
                "Debit and credit accounts cannot match"
            )

        if not reference_id or not reference_id.strip():
            raise LedgerValidationError("Reference ID required")

        if currency not in SUPPORTED_CURRENCIES:
            raise LedgerValidationError(f"Unsupported currency: {currency}")

        if db.session.get(GLAccount, debit_account_id) is None:
            raise LedgerValidationError("Invalid debit account")

        if db.session.get(GLAccount, credit_account_id) is None:
            raise LedgerValidationError("Invalid credit account")

        if JournalEntry.query.filter_by(
            reference_id=reference_id
        ).first() is not None:
            raise DuplicateReferenceError(
                f"Reference already posted: {reference_id}"
            )

        return parsed_amount

    @staticmethod
    def post(
        *,
        debit_account_id: int,
        credit_account_id: int,
        amount: Decimal | int | float | str,
        reference_id: str,
        currency: str = "USD",
        description: str | None = None,
        commit: bool = False,
    ) -> JournalEntry:
        amount = LedgerEngine._validate_post(
            debit_account_id=debit_account_id,
            credit_account_id=credit_account_id,
            amount=amount,
            reference_id=reference_id,
            currency=currency,
        )

        entry = JournalEntry(
            debit_account_id=debit_account_id,
            credit_account_id=credit_account_id,
            amount=amount,
            currency=currency,
            reference_id=reference_id,
            description=description,
        )

        try:
            db.session.add(entry)
            # The database unique constraint handles concurrent requests.
            db.session.flush()

            if commit:
                db.session.commit()

            return entry

        except IntegrityError as exc:
            db.session.rollback()
            # This assumes reference_id is the only unique constraint that
            # can fail during this flush. Narrow this if the model has others.
            raise DuplicateReferenceError(
                f"Reference already posted: {reference_id}"
            ) from exc
        except SQLAlchemyError:
            db.session.rollback()
            raise

    @staticmethod
    def account_balance(account_id: int) -> Decimal:
        debit_total = (
            db.session.query(
                func.coalesce(func.sum(JournalEntry.amount), 0)
            )
            .filter(JournalEntry.debit_account_id == account_id)
            .scalar()
        )
        credit_total = (
            db.session.query(
                func.coalesce(func.sum(JournalEntry.amount), 0)
            )
            .filter(JournalEntry.credit_account_id == account_id)
            .scalar()
        )
        return Decimal(str(debit_total)) - Decimal(str(credit_total))

    @staticmethod
    def account_summary(account_id: int) -> dict:
        return {
            "account_id": account_id,
            "balance": str(LedgerEngine.account_balance(account_id)),
            "debit_count": JournalEntry.query.filter_by(
                debit_account_id=account_id
            ).count(),
            "credit_count": JournalEntry.query.filter_by(
                credit_account_id=account_id
            ).count(),
        }

    @staticmethod
    def trial_balance() -> list[dict]:
        accounts = GLAccount.query.order_by(GLAccount.code).all()
        return [
            {
                "id": account.id,
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "balance": str(LedgerEngine.account_balance(account.id)),
            }
            for account in accounts
        ]

    @staticmethod
    def total_posted() -> Decimal:
        total = (
            db.session.query(
                func.coalesce(func.sum(JournalEntry.amount), 0)
            ).scalar()
        )
        return Decimal(str(total))

    @staticmethod
    def is_balanced() -> bool:
        invalid_entry = (
            db.session.query(JournalEntry.id)
            .filter(
                (JournalEntry.amount <= 0)
                | (
                    JournalEntry.debit_account_id
                    == JournalEntry.credit_account_id
                )
                | JournalEntry.debit_account_id.is_(None)
                | JournalEntry.credit_account_id.is_(None)
                | JournalEntry.currency.is_(None)
            )
            .first()
        )
        if invalid_entry is not None:
            return False

        # Each row contributes its amount once to each side. Grouping by
        # currency prevents different currencies from offsetting one another.
        debit_totals = (
            db.session.query(
                JournalEntry.currency,
                func.sum(
                    case(
                        (JournalEntry.debit_account_id.is_not(None),
                         JournalEntry.amount),
                        else_=0,
                    )
                ),
            )
            .group_by(JournalEntry.currency)
            .all()
        )
        credit_totals = (
            db.session.query(
                JournalEntry.currency,
                func.sum(
                    case(
                        (JournalEntry.credit_account_id.is_not(None),
                         JournalEntry.amount),
                        else_=0,
                    )
                ),
            )
            .group_by(JournalEntry.currency)
            .all()
        )

        return dict(debit_totals) == dict(credit_totals)

    @staticmethod
    def healthcheck() -> dict:
        balanced = LedgerEngine.is_balanced()
        return {
            "engine": "ledger",
            "healthy": balanced,
            "balanced": balanced,
            "accounts": GLAccount.query.count(),
            "journal_entries": JournalEntry.query.count(),
            "total_posted": str(LedgerEngine.total_posted()),
        }
