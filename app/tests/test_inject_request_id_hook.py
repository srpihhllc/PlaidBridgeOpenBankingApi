from flask import Flask
from app.utils import security_utils

def test_inject_request_id_registers_hooks():
    app = Flask("test_app")
    # ensure no hooks initially
    assert not app.before_request_funcs.get(None)
    assert not app.after_request_funcs.get(None)

    # register
    security_utils.inject_request_id(app)

    # there should be at least one before_request and after_request function for the app (None key)
    before = app.before_request_funcs.get(None) or []
    after = app.after_request_funcs.get(None) or []

    # the actual function object registered as before_request will be security_utils.inject_request_id
    assert any(fn is security_utils.inject_request_id for fn in before)
    # the after_request finalizer should be present
    assert any(fn is security_utils.finalize_request_logging for fn in after)