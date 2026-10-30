# =============================================================================
# FILE: app/tests/fixtures/mock_journal_entry.py
# =============================================================================

from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.fixture
def mock_journal_entry():
    """
    JournalEntry test double.
    """

    return SimpleNamespace(
        id=1,
        debit_account_id=1,
        credit_account_id=2,
        amount=Decimal("100.00"),
        reference_id="TEST-REF-001",
        description="Test Journal Entry",
    )