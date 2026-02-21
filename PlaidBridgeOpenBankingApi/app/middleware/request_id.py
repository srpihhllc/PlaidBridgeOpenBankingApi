# app/middleware/request_id.py

import uuid

from flask import g, request


def before_request():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


def after_request(resp):
    resp.headers["X-Request-ID"] = getattr(g, "request_id", "")
    return resp
