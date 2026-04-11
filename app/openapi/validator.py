from openapi_core import create_spec
from openapi_core.validation.request.validators import RequestValidator
from openapi_core.validation.response.validators import ResponseValidator
from openapi_core.contrib.flask import FlaskOpenAPIRequest, FlaskOpenAPIResponse
import yaml
from pathlib import Path

_spec = None
_request_validator = None
_response_validator = None

def load_spec(path: str):
    global _spec, _request_validator, _response_validator
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    _spec = create_spec(raw)
    _request_validator = RequestValidator(_spec)
    _response_validator = ResponseValidator(_spec)

def validate_flask_request(req):
    openapi_req = FlaskOpenAPIRequest(req)
    result = _request_validator.validate(openapi_req)
    result.raise_for_errors()  # raises exception on first error
    return result

def validate_flask_response(req, resp):
    openapi_req = FlaskOpenAPIRequest(req)
    openapi_resp = FlaskOpenAPIResponse(resp)
    result = _response_validator.validate(openapi_req, openapi_resp)
    result.raise_for_errors()
    return result