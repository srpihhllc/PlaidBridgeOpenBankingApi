# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_journal_entry.py

from decimal import Decimal

from app.models.journal_entry import JournalEntry


def test_valid_entry():
    entry = JournalEntry(
        debit_account_id=1,
        credit_account_id=2,
        amount=Decimal("50.00"),
        currency="USD",
        reference_id="test-ref-001",
    )

    assert entry.amount == Decimal("50.00")
    assert entry.debit_account_id == 1
    assert entry.credit_account_id == 2
    assert entry.currency == "USD"
    assert entry.reference_id == "test-ref-001"


def test_journal_entry_repr():
    entry = JournalEntry(
        debit_account_id=1,
        credit_account_id=2,
        amount=Decimal("50.00"),
        currency="USD",
        reference_id="test-ref-002",
    )

    representation = repr(entry)

    assert "JournalEntry" in representation
    assert "test-ref-002" in representation