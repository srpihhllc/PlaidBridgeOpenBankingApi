from app.models.settlement_batch import (
    SettlementBatch,
)

from app.services.settlement_engine import (
    SettlementEngine,
)


def test_create_batch():

    batch = (
        SettlementEngine.create_batch(
            payment_type="ach"
        )
    )

    assert batch is not None


def test_open_batch():

    batch = SettlementBatch(
        batch_reference="b1",
        payment_type="ach",
    )

    SettlementEngine.open_batch(
        batch
    )

    assert (
        batch.status
        == "open"
    )


def test_fail_batch():

    batch = SettlementBatch(
        batch_reference="b2",
        payment_type="ach",
    )

    SettlementEngine.fail_batch(
        batch
    )

    assert (
        batch.status
        == "failed"
    )


def test_reverse_batch():

    batch = SettlementBatch(
        batch_reference="b3",
        payment_type="ach",
    )

    SettlementEngine.reverse_batch(
        batch
    )

    assert (
        batch.status
        == "reversed"
    )