# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_redirect_for_role.py

import pytest
from flask import Flask

from app.blueprints.auth_routes import redirect_for_role
from app.models.user import User


@pytest.fixture
def app():
    app = Flask(__name__)

    # Register dummy endpoints to simulate your blueprints
    @app.route("/admin/cockpit", endpoint="admin.cockpit")
    def admin_cockpit():
        return "Admin Cockpit"

    @app.route("/dashboard", endpoint="main.dashboard")
    def main_dashboard():
        return "Main Dashboard"

    @app.route("/subscriber/dashboard", endpoint="sub_ui.dashboard")
    def subscriber_dashboard():
        return "Subscriber Dashboard"

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(role):
    """Helper to create a mock User with a given role."""
    u = User(email="test@example.com", username="tester")
    u.role = role
    return u


def test_admin_redirect(app, client):
    with app.test_request_context():
        u = make_user("admin")
        resp = redirect_for_role(u)
        assert resp.location.endswith("/admin/cockpit")


def test_super_admin_redirect(app, client):
    with app.test_request_context():
        u = make_user("super_admin")
        resp = redirect_for_role(u)
        assert resp.location.endswith("/admin/cockpit")


def test_subscriber_redirect(app, client):
    with app.test_request_context():
        u = make_user("subscriber")
        resp = redirect_for_role(u)
        assert resp.location.endswith("/subscriber/dashboard")


def test_default_user_redirect(app, client):
    with app.test_request_context():
        u = make_user("user")
        resp = redirect_for_role(u)
        assert resp.location.endswith("/dashboard")
