# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_customer_wallet.py

from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.account_status import AccountStatus
from app.models.customer_wallet import CustomerWallet
from app.models.gl_account import GLAccount
from app.services.wallet_engine import (
    WalletEngine,
    FrozenWalletError,
)


@pytest.fixture
def cash_account(db_session):
    account = GLAccount(
        code=f"TEST-CASH-{uuid4().hex[:8]}",
        name="Test Cash",
        account_type="asset",
    )
    db_session.add(account)
    db_session.flush()
    return account


@pytest.fixture
def wallet_account(db_session):
    account = GLAccount(
        code=f"TEST-WALLET-{uuid4().hex[:8]}",
        name="Test Wallet Liability",
        account_type="liability",
    )
    db_session.add(account)
    db_session.flush()
    return account


def test_wallet_deposit(db_session, cash_account, wallet_account):
    wallet = CustomerWallet(user_id=1)

    db_session.add(wallet)
    db_session.flush()

    WalletEngine.deposit(
        wallet=wallet,
        amount=Decimal("100"),
        reference_id=str(uuid4()),
        cash_account_id=cash_account.id,
        wallet_account_id=wallet_account.id,
    )

    assert wallet.balance == Decimal("100")


def test_wallet_withdraw(db_session, cash_account, wallet_account):
    wallet = CustomerWallet(
        user_id=1,
        balance=Decimal("0"),
    )

    db_session.add(wallet)
    db_session.flush()

    WalletEngine.deposit(
        wallet=wallet,
        amount=Decimal("100"),
        reference_id=str(uuid4()),
        cash_account_id=cash_account.id,
        wallet_account_id=wallet_account.id,
    )

    WalletEngine.withdraw(
        wallet=wallet,
        amount=Decimal("25"),
        reference_id=str(uuid4()),
        cash_account_id=cash_account.id,
        wallet_account_id=wallet_account.id,
    )

    assert wallet.balance == Decimal("75")


def test_wallet_freeze(db_session):
    wallet = CustomerWallet(user_id=1)

    db_session.add(wallet)
    db_session.flush()

    WalletEngine.freeze(wallet)

    assert wallet.status == AccountStatus.FROZEN


def test_frozen_wallet_rejected(
    db_session,
    cash_account,
    wallet_account,
):
    wallet = CustomerWallet(user_id=1)

    db_session.add(wallet)
    db_session.flush()

    WalletEngine.freeze(wallet)

    with pytest.raises(FrozenWalletError):
        WalletEngine.deposit(
            wallet=wallet,
            amount=Decimal("10"),
            reference_id=str(uuid4()),
            cash_account_id=cash_account.id,
            wallet_account_id=wallet_account.id,
        )