# =============================================================================
# FILE: app/tests/test_validation.py
# DESCRIPTION: Unit tests for the bulletproof JSON schema validator decorator.
# =============================================================================
import pytest
from flask import jsonify

from app.api.validation import validate_json_schema

schema = {
    "type": "object",
    "properties": {"foo": {"type": "string"}},
    "required": ["foo"],
}


# Register all dummy routes once before any tests run
@pytest.fixture(scope="module", autouse=True)
def register_dummy_routes(app):
    @app.route("/dummy_invalid", methods=["POST"])
    @validate_json_schema(schema)
    def dummy_invalid():
        return jsonify({"status": "ok"}), 200

    @app.route("/dummy_malformed", methods=["POST"])
    @validate_json_schema(schema)
    def dummy_malformed():
        return jsonify({"status": "ok"}), 200

    @app.route("/dummy_violation", methods=["POST"])
    @validate_json_schema(schema)
    def dummy_violation():
        return jsonify({"status": "ok"}), 200

    @app.route("/dummy_valid", methods=["POST"])
    @validate_json_schema(schema)
    def dummy_valid():
        return jsonify({"status": "ok"}), 200


def test_validate_json_schema_invalid_json(client):
    """
    Posting non‑JSON with application/json header should return 422
    with 'Malformed JSON body.' message.
    """
    resp = client.post(
        "/dummy_invalid", data="not-json", headers={"Content-Type": "application/json"}
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
