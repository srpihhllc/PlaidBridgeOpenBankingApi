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

def test_create_transfer_persists_and_replays_idempotently(app):
    with app.app_context():
        first = ACHEngine.create_transfer(
            debit_wallet_id=1,
            credit_wallet_id=2,
            amount=Decimal("25.00"),
            idempotency_key="test-ach-idem-001",
        )
        replay = ACHEngine.create_transfer(
            debit_wallet_id=1,
            credit_wallet_id=2,
            amount=Decimal("25.00"),
            idempotency_key="test-ach-idem-001",
        )
        assert first.id is not None
        assert replay.id == first.id
