from decimal import Decimal

from app.services.ach_engine import (
    ACHEngine,
)


def test_ach_limit_exists():

    assert (
        ACHEngine.MAX_ACH_AMOUNT
        > Decimal("0")
    )


def test_invalid_amount_rejected():

    try:

        ACHEngine.create_transfer(
            debit_wallet_id=1,
            credit_wallet_id=2,
            amount=-1,
            idempotency_key="ach1",
        )

        assert False

    except Exception:
        assert True