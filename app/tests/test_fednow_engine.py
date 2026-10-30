from app.services.fednow_engine import (
    FedNowEngine,
)


def test_healthcheck():

    health = (
        FedNowEngine.healthcheck()
    )

    assert (
        health["engine"]
        == "fednow"
    )

    assert (
        health["status"]
        == "healthy"
    )