# =============================================================================
# FILE: app/tests/fixtures/mock_gl_account.py
# =============================================================================

from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.fixture
def mock_gl_account():
    """
    General Ledger account test double.
    """

    return SimpleNamespace(
        id=1,
        code="1000",
        name="Mock Cash Account",
        balance=Decimal("0.00"),
        is_active=True,
    )