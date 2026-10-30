#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_gl_account.py

from decimal import Decimal
from types import SimpleNamespace

from app.models.gl_account import GLAccount, GLAccountType


def test_asset_debit_increases_balance():
    account = GLAccount(
        code="1000",
        name="Cash",
        account_type=GLAccountType.ASSET,
    )

    # Exercise the balance calculation with one debit and no credits.
    account_with_entries = SimpleNamespace(
        journal_debits=[SimpleNamespace(amount=Decimal("100.00"))],
        journal_credits=[],
    )

    assert account.account_type == GLAccountType.ASSET
    assert GLAccount.balance.fget(account_with_entries) == Decimal("100.00")
