# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_no_legacy_transactions_route.py


def test_no_legacy_transactions_route(app):
    """Ensure the legacy /api/v1/transactions route never reappears."""
    forbidden = "/api/v1/transactions"

    all_routes = {rule.rule for rule in app.url_map.iter_rules()}

    assert forbidden not in all_routes, (
        f"Forbidden legacy route {forbidden} has reappeared. "
        "This route was intentionally removed to prevent collisions."
    )
