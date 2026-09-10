# app/tests/test_route_cleanup.py

from flask import Flask

from app import _cleanup_premature_oauth_registrations


def test_cleanup_removes_premature_oauth_endpoint(monkeypatch):
    # Create a minimal Flask app and simulate a premature oauth.* view registration
    app = Flask("test_app")
    app.config["TESTING"] = True

    # Simulate a view function that looks oauth-related
    def fake_oauth_view():
        return "ok"

    fake_oauth_view.__module__ = "app.blueprints.oauth_routes"
    # Register the premature endpoint directly into view_functions and url_map
    app.view_functions["oauth.premature"] = fake_oauth_view

    # Create a dummy rule object by using add_url_rule (keeps url_map consistent)
    with app.test_request_context():
        app.add_url_rule(
            "/callback/premature",
            endpoint="oauth.premature",
            view_func=fake_oauth_view,
        )

    # Ensure the endpoint exists before cleanup
    assert "oauth.premature" in app.view_functions

    # Run cleanup (should remove the premature oauth.* endpoint)
    _cleanup_premature_oauth_registrations(app)

    # After cleanup, the endpoint should be gone
    assert "oauth.premature" not in app.view_functions
