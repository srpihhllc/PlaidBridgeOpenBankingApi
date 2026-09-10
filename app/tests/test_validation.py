# =============================================================================
# FILE: app/tests/test_validation.py
# DESCRIPTION: Unit tests for the bulletproof JSON schema validator decorator.
# Dummy routes are registered in conftest.py inside the session-scoped `app`
# fixture, before any request is handled, so Flask allows route registration.
# =============================================================================


def test_validate_json_schema_invalid_json(client):
    """
    Posting non-JSON with application/json header should return 422
    with 'Malformed JSON body.' message.
    """
    resp = client.post(
        "/dummy_invalid",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert b"Malformed JSON body." in resp.data


def test_validate_json_schema_malformed_json(client):
    """Posting broken JSON syntax should return 422 with 'Malformed JSON body.' message."""
    resp = client.post(
        "/dummy_malformed",
        data="{foo: bar}",  # invalid JSON syntax
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert b"Malformed JSON body." in resp.data


def test_validate_json_schema_schema_violation(client):
    """Posting valid JSON that violates schema should return 422 with schema error message."""
    resp = client.post(
        "/dummy_violation",
        json={"bar": "baz"},  # Missing required field 'foo'
    )
    assert resp.status_code == 422
    assert b"Schema validation failed" in resp.data


def test_validate_json_schema_valid_json(client):
    """Posting valid JSON that satisfies schema should return 200 with success."""
    resp = client.post("/dummy_valid", json={"foo": "bar"})
    assert resp.status_code == 200
    assert b"ok" in resp.data
