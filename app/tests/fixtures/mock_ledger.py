# =============================================================================
# FILE: app/tests/fixtures/mock_ledger.py
# =============================================================================

from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.fixture
def mock_ledger():
    """
    Ledger aggregate test double.
    """

    return SimpleNamespace(
        id=1,
        balance=Decimal("0.00"),
        total_debits=Decimal("0.00"),
        total_credits=Decimal("0.00"),
        entries=[],
    )