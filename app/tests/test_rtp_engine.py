from app.services.rtp_engine import (
    RTPEngine,
)


def test_healthcheck():

    health = (
        RTPEngine.healthcheck()
    )

    assert (
        health["engine"]
        == "rtp"
    )

    assert (
        health["status"]
        == "healthy"
    )


def test_metrics_returns_dict():

    metrics = (
        RTPEngine.metrics()
    )

    assert isinstance(
        metrics,
        dict,
    )