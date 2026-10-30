# =============================================================================
# FILE: app/tests/fixtures/mock_wallet.py
#
# PURPOSE:
#     Reusable wallet test double for WalletEngine tests.
#
# DESIGN:
#     - Lightweight
#     - No database dependency
#     - Decimal-safe starting balance
#     - Compatible with WalletEngine validation rules
# =============================================================================

from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.fixture
def mock_wallet():
    """
    Standard mock wallet used by wallet engine tests.
    """

    return SimpleNamespace(
        id=1,
        balance=Decimal("0.00"),
        is_frozen=False,
        status=None,
        account_id=1,
        customer_id=1,
    )