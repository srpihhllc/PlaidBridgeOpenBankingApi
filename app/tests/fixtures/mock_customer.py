# =============================================================================
# FILE: app/tests/fixtures/mock_customer.py
# =============================================================================

from types import SimpleNamespace

import pytest


@pytest.fixture
def mock_customer():
    """
    Lightweight customer test double.
    """

    return SimpleNamespace(
        id=1,
        first_name="Test",
        last_name="Customer",
        email="test@example.com",
        phone="+15555555555",
        is_active=True,
    )