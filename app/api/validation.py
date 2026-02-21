# =============================================================================
# FILE: app/api/validation.py
# DESCRIPTION: Bulletproof JSON schema validator decorator.
# =============================================================================
from functools import wraps

from flask import jsonify, request
from jsonschema import SchemaError, ValidationError, validate
from werkzeug.exceptions import BadRequest


def validate_json_schema(schema):
    """
    Decorator to enforce that requests contain valid JSON and match a given schema.
    Returns 422 on invalid/missing JSON or schema violations.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # 1) Ensure Content-Type is application/json
            if not request.is_json:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": {
                                "code": "E_VALIDATION",
                                "message": "Request must be JSON",
                            },
                        }
                    ),
                    422,
                )

            # 2) Attempt to parse JSON body
            try:
                payload = request.get_json(force=True)
            except BadRequest:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": {
                                "code": "E_VALIDATION",
                                "message": "Malformed JSON body.",
                            },
                        }
                    ),
                    422,
                )

            # 3) Handle empty or null JSON
            if payload is None:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": {
                                "code": "E_VALIDATION",
                                "message": "Empty or invalid JSON body.",
                            },
                        }
                    ),
                    422,
                )

            # 4) Validate against schema
            try:
                validate(instance=payload, schema=schema)
            except ValidationError as ve:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": {
                                "code": "E_VALIDATION",
                                "message": f"Schema validation failed: {ve.message}",
                            },
                        }
                    ),
                    422,
                )
            except SchemaError as se:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": {
                                "code": "E_SCHEMA",
                                "message": f"Invalid schema definition: {se.message}",
                            },
                        }
                    ),
                    500,
                )  # schema misconfiguration is server error

            # 5) If all good, proceed
            return fn(*args, **kwargs)

        return wrapper

    return decorator
