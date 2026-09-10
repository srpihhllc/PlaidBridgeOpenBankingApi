# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_contracts.py

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate as validate_jsonschema
from openapi_spec_validator import validate as validate_openapi_spec

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SWAGGER_FILE = FIXTURES_DIR / "swagger.json"


@pytest.fixture(scope="session")
def swagger_spec(app):
    """Loads the persisted swagger spec fixture or generates it dynamically if missing."""
    if not SWAGGER_FILE.exists():
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        with app.test_client() as client:
            response = client.get("/apispec_1.json")
            if response.status_code == 200:
                SWAGGER_FILE.write_bytes(response.data)
            else:
                pytest.fail(
                    f"Could not generate swagger spec via /apispec_1.json (Status {response.status_code})"
                )

    with open(SWAGGER_FILE, "r") as f:
        return json.load(f)


def test_swagger_schema_integrity(swagger_spec):
    """Ensures the swagger.json file itself strictly complies with Swagger 2.0 rules."""
    # Will raise an exception if swagger.json structure is invalid
    validate_openapi_spec(swagger_spec)


def validate_response_contract(
    swagger_spec, path: str, method: str, status_code: int, response_data: dict
):
    """Helper to extract a schema from the spec and validate response data against it."""
    endpoint_spec = swagger_spec["paths"][path][method.lower()]
    response_spec = endpoint_spec["responses"][str(status_code)]

    # Skip validation if no schema is defined for this response code
    if "schema" not in response_spec:
        return

    schema = response_spec["schema"]
    try:
        validate_jsonschema(instance=response_data, schema=schema)
    except ValidationError as e:
        pytest.fail(
            f"Contract violation on {method.upper()} {path} ({status_code}): {e.message}"
        )


# --- Endpoint Contract Tests ---


def test_api_ping_contract(client, swagger_spec):
    """Validate /api/ping response against the schema contract."""
    response = client.get("/api/ping")
    assert response.status_code == 200

    validate_response_contract(
        swagger_spec=swagger_spec,
        path="/api/ping",
        method="get",
        status_code=200,
        response_data=response.get_json(),
    )


def test_tradeline_review_contract(client, auth_headers, swagger_spec):
    """Validate POST /api/tradelines/review/1 validation error contract."""
    # Intentional bad payload to trigger 400 response contract
    response = client.post(
        "/api/tradelines/review/1",
        json={"action": "invalid_action"},
        headers=auth_headers,
    )
    assert response.status_code == 400

    validate_response_contract(
        swagger_spec=swagger_spec,
        path="/api/tradelines/review/{tradeline_id}",
        method="post",
        status_code=400,
        response_data=response.get_json(),
    )
