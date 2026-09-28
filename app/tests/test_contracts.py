#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_contracts.py

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate as validate_jsonschema
from openapi_spec_validator import validate as validate_openapi_spec


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SWAGGER_FILE = FIXTURES_DIR / "swagger.json"


@pytest.fixture(scope="session")
def swagger_spec(app):
    """Dynamically generates the swagger spec from the app instance to avoid stale cached fixtures."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with app.test_client() as client:
        response = client.get("/apispec_1.json")
        if response.status_code == 200:
            spec_data = response.get_json()
            # Cache spec on disk for inspection and offline validation tools
            SWAGGER_FILE.write_text(json.dumps(spec_data, indent=2))
            return spec_data
        
        # Fallback to cached fixture if endpoint generation fails
        if SWAGGER_FILE.exists():
            with open(SWAGGER_FILE, "r") as f:
                return json.load(f)

        pytest.fail(
            f"Could not generate swagger spec via /apispec_1.json (Status {response.status_code})"
        )


def test_swagger_schema_integrity(swagger_spec):
    """Ensures the swagger spec strictly complies with Swagger 2.0 / OpenAPI rules."""
    validate_openapi_spec(swagger_spec)


def validate_response_contract(
    swagger_spec, path: str, method: str, status_code: int, response_data: dict
):
    """Helper to extract a schema from the spec and validate response data against it."""
    paths = swagger_spec.get("paths", {})
    assert path in paths, f"Path '{path}' not found in Swagger spec. Available paths: {list(paths.keys())}"

    methods = paths[path]
    method_lower = method.lower()
    assert method_lower in methods, f"Method '{method_lower}' not found for path '{path}'. Available methods: {list(methods.keys())}"

    endpoint_spec = methods[method_lower]
    response_spec = endpoint_spec.get("responses", {}).get(str(status_code), {})

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
    """Validate POST /api/v1/tradelines/review/1 validation error contract."""
    # Intentional bad payload to trigger 400 response contract
    response = client.post(
        "/api/v1/tradelines/review/1",
        json={"action": "invalid_action"},
        headers=auth_headers,
    )
    assert response.status_code == 400

    validate_response_contract(
        swagger_spec=swagger_spec,
        path="/api/v1/tradelines/review/{tradeline_id}",
        method="post",
        status_code=400,
        response_data=response.get_json(),
    )