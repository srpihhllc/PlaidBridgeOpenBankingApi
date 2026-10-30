# =============================================================================
# FILE: app/tests/test_wallet_engine.py
# =============================================================================

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.wallet_engine import (
    FrozenWalletError,
    InsufficientFundsError,
    WalletEngine,
)


@pytest.fixture(autouse=True)
def wallet_engine_mocks():
    """
    Unit-test isolation layer.

    Prevent WalletEngine tests from invoking:
        - LedgerEngine
        - SQLAlchemy persistence
        - Flask application context requirements
        - GL account validation
    """

    with (
        patch("app.services.wallet_engine.LedgerEngine.post"),
        patch("app.services.wallet_engine.db.session.add"),
    ):
        yield


def test_deposit(mock_wallet):
    WalletEngine.deposit(
        wallet=mock_wallet,
        amount=Decimal("25.00"),
        reference_id="DEP-001",
        cash_account_id=1,
        wallet_account_id=2,
    )

    assert mock_wallet.balance == Decimal("25.00")


def test_withdraw(mock_wallet):
    mock_wallet.balance = Decimal("100.00")

    WalletEngine.withdraw(
        wallet=mock_wallet,
        amount=Decimal("40.00"),
        reference_id="WDR-001",
        cash_account_id=1,
        wallet_account_id=2,
    )

    assert mock_wallet.balance == Decimal("60.00")


def test_withdraw_insufficient_funds(mock_wallet):
    mock_wallet.balance = Decimal("25.00")

    with pytest.raises(InsufficientFundsError):
        WalletEngine.withdraw(
            wallet=mock_wallet,
            amount=Decimal("100.00"),
            reference_id="FAIL-001",
            cash_account_id=1,
            wallet_account_id=2,
        )


def test_transfer():
    sender = SimpleNamespace(
        id=1,
        balance=Decimal("100.00"),
        is_frozen=False,
        status=None,
    )

    receiver = SimpleNamespace(
        id=2,
        balance=Decimal("20.00"),
        is_frozen=False,
        status=None,
    )

    result = WalletEngine.transfer(
        sender_wallet=sender,
        receiver_wallet=receiver,
        amount=Decimal("25.00"),
        reference_id="TRF-001",
    )

    assert sender.balance == Decimal("75.00")
    assert receiver.balance == Decimal("45.00")

    assert result["reference_id"] == "TRF-001"
    assert result["sender_wallet_id"] == 1
    assert result["receiver_wallet_id"] == 2


def test_transfer_insufficient_funds():
    sender = SimpleNamespace(
        id=1,
        balance=Decimal("10.00"),
        is_frozen=False,
        status=None,
    )

    receiver = SimpleNamespace(
        id=2,
        balance=Decimal("50.00"),
        is_frozen=False,
        status=None,
    )

    with pytest.raises(InsufficientFundsError):
        WalletEngine.transfer(
            sender_wallet=sender,
            receiver_wallet=receiver,
            amount=Decimal("100.00"),
            reference_id="TRF-FAIL-001",
        )


def test_freeze(mock_wallet):
    WalletEngine.freeze(mock_wallet)

    assert mock_wallet.is_frozen is True


def test_unfreeze(mock_wallet):
    mock_wallet.is_frozen = True

    WalletEngine.unfreeze(mock_wallet)

    assert mock_wallet.is_frozen is False


def test_frozen_wallet_rejects_deposit(mock_wallet):
    mock_wallet.is_frozen = True

    with pytest.raises(FrozenWalletError):
        WalletEngine.deposit(
            wallet=mock_wallet,
            amount=Decimal("10.00"),
            reference_id="FRZ-DEP-001",
            cash_account_id=1,
            wallet_account_id=2,
        )


def test_frozen_wallet_rejects_withdrawal(mock_wallet):
    mock_wallet.is_frozen = True
    mock_wallet.balance = Decimal("100.00")

    with pytest.raises(FrozenWalletError):
        WalletEngine.withdraw(
            wallet=mock_wallet,
            amount=Decimal("10.00"),
            reference_id="FRZ-WDR-001",
            cash_account_id=1,
            wallet_account_id=2,
        )


def test_zero_deposit_rejected(mock_wallet):
    with pytest.raises(ValueError):
        WalletEngine.deposit(
            wallet=mock_wallet,
            amount=Decimal("0.00"),
            reference_id="DEP-ZERO",
            cash_account_id=1,
            wallet_account_id=2,
        )


def test_negative_withdraw_rejected(mock_wallet):
    mock_wallet.balance = Decimal("100.00")

    with pytest.raises(ValueError):
        WalletEngine.withdraw(
            wallet=mock_wallet,
            amount=Decimal("-5.00"),
            reference_id="NEG-WDR",
            cash_account_id=1,
            wallet_account_id=2,
        )