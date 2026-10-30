from app.services.ledger_engine import LedgerEngine


def test_double_entry_balanced():
    """
    Every valid journal row represents both a debit and a credit.
    LedgerEngine is responsible for validating that the journal
    remains balanced.
    """

    assert LedgerEngine.is_balanced() is True


def test_healthcheck_exists():
    """
    Healthcheck should return a standard operational payload.
    """

    health = LedgerEngine.healthcheck()

    assert health["engine"] == "ledger"
    assert "healthy" in health
    assert "balanced" in health
    assert "accounts" in health
    assert "journal_entries" in health
    assert "total_posted" in health