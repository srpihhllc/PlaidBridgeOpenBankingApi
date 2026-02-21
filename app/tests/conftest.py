# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/conftest.py

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture(scope="session")
def app():
    """Create application for the tests."""
    # Create app with testing config
    # TestingConfig already has RATE_LIMIT_ENABLED=False set
    app = create_app(env_name="testing")

    # These should already be set by TestingConfig, but ensure they're set
    # (in case they get overridden somewhere)
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["TESTING"] = True

    # DO NOT override RATE_LIMIT_ENABLED here - let TestingConfig handle it

    return app


@pytest.fixture(scope="session")
def db_session(app):
    """Provide a DB session for session-scoped fixtures."""
    with app.app_context():
        yield db.session


@pytest.fixture
def templates(app):
    """Record templates rendered during a request."""
    from flask import template_rendered

    recorded = []

    def record(sender, template, context, **extra):
        recorded.append(template)

    template_rendered.connect(record, app)

    yield recorded

    template_rendered.disconnect(record, app)


@pytest.fixture
def client(app):
    """A test client for the app."""
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()