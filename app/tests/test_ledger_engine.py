# =============================================================================
# FILE: app/tests/test_ledger_engine.py
# DESCRIPTION: Comprehensive test suite for LedgerEngine and double-entry accounting.
# =============================================================================

from decimal import Decimal
import pytest

from app.extensions import db
from app.models.gl_account import GLAccount, GLAccountType
from app.models.journal_entry import JournalEntry
from app.services.ledger_engine import (
    DuplicateReferenceError,
    LedgerEngine,
)


@pytest.fixture
def two_gl_accounts(app):
    with app.app_context():
        debit = GLAccount(
            code="1000",
            name="Cash",
            account_type=GLAccountType.ASSET.value,
        )

        credit = GLAccount(
            code="2000",
            name="Accounts Payable",
            account_type=GLAccountType.LIABILITY.value,
        )

        db.session.add_all([debit, credit])
        db.session.commit()

        yield debit, credit

        JournalEntry.query.delete()
        GLAccount.query.delete()
        db.session.commit()


def test_duplicate_reference_is_rejected(
    app, db, two_gl_accounts
):
    debit, credit = two_gl_accounts

    with app.app_context():
        LedgerEngine.post(
            debit_account_id=debit.id,
            credit_account_id=credit.id,
            amount="10.00",
            reference_id="payment-123",
            commit=True,
        )

        with pytest.raises(DuplicateReferenceError):
            LedgerEngine.post(
                debit_account_id=debit.id,
                credit_account_id=credit.id,
                amount="10.00",
                reference_id="payment-123",
                commit=True,
            )


def test_balanced_entries_in_multiple_currencies_are_balanced(
    app, db, two_gl_accounts
):
    debit, credit = two_gl_accounts

    with app.app_context():
        db.session.add_all(
            [
                JournalEntry(
                    debit_account_id=debit.id,
                    credit_account_id=credit.id,
                    amount="10.00",
                    currency="USD",
                    reference_id="usd-payment",
                ),
                JournalEntry(
                    debit_account_id=debit.id,
                    credit_account_id=credit.id,
                    amount="25.00",
                    currency="EUR",
                    reference_id="eur-payment",
                ),
            ]
        )

        db.session.commit()

        assert LedgerEngine.is_balanced() is True


def test_nonpositive_entry_makes_ledger_unbalanced(
    app, db, two_gl_accounts
):
    debit, credit = two_gl_accounts

    with app.app_context():
        db.session.add(
            JournalEntry(
                debit_account_id=debit.id,
                credit_account_id=credit.id,
                amount="0.00",
                currency="USD",
                reference_id="invalid-payment",
            )
        )

        db.session.commit()

        assert LedgerEngine.is_balanced() is False


def test_ledger_engine_posting_and_balances(app, db, two_gl_accounts):
    """Verify successful LedgerEngine posting, account balances, and trial balance calculations."""
    debit, credit = two_gl_accounts

    with app.app_context():
        entry = LedgerEngine.post(
            debit_account_id=debit.id,
            credit_account_id=credit.id,
            amount=Decimal("150.00"),
            currency="USD",
            reference_id="ref-balance-test",
            commit=True,
        )

        assert entry is not None
        assert entry.amount == Decimal("150.00")

        # Test account balance calculations
        cash_balance = LedgerEngine.account_balance(debit.id)
        assert cash_balance == Decimal("150.00")

        ap_balance = LedgerEngine.account_balance(credit.id)
        assert ap_balance == Decimal("-150.00")

        # Test trial balance aggregation (returns a list of account records/balances)
        tb = LedgerEngine.trial_balance()
        assert isinstance(tb, (list, tuple))
        assert len(tb) > 0