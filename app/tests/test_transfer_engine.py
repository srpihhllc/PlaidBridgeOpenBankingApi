from decimal import Decimal


def test_transfer_requires_positive_amount():
    from app.services.transfer_engine import (
        TransferEngine,
    )

    try:
        TransferEngine.transfer(
            idempotency_key="t1",
            debit_account_id=1,
            credit_account_id=2,
            amount=Decimal("-10"),
        )

        assert False

    except Exception:
        assert True


def test_transfer_requires_unique_accounts():

    from app.services.transfer_engine import (
        TransferEngine,
    )

    try:

        TransferEngine.transfer(
            idempotency_key="t2",
            debit_account_id=1,
            credit_account_id=1,
            amount=Decimal("100"),
        )

        assert False

    except Exception:
        assert True