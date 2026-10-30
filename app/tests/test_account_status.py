from app.models.account_status import AccountStatus


def test_status_values():

    assert AccountStatus.ACTIVE.value == "active"
    assert AccountStatus.FROZEN.value == "frozen"
    assert AccountStatus.CLOSED.value == "closed"