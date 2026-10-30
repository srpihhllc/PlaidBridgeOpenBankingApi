
import yaml

from openapi_core import OpenAPI

from openapi_core.contrib.flask import (

    FlaskOpenAPIRequest,

    FlaskOpenAPIResponse,

)



_openapi = None





def load_spec(path: str):

    global _openapi



    with open(path, "r", encoding="utf-8") as f:

        raw = yaml.safe_load(f)



    _openapi = OpenAPI.from_dict(raw)





def validate_flask_request(req):

    if _openapi is None:

        raise RuntimeError("OpenAPI spec has not been loaded; call load_spec() first")



    return _openapi.validate_request(FlaskOpenAPIRequest(req))





def validate_flask_response(req, resp):

    if _openapi is None:

        raise RuntimeError("OpenAPI spec has not been loaded; call load_spec() first")



    return _openapi.validate_response(

        FlaskOpenAPIRequest(req),

        FlaskOpenAPIResponse(resp),

    )

