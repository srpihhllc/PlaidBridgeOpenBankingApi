# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/conftest.py

import pytest

from app import create_app
from app.extensions import db
from sqlalchemy import event


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

    # Ensure SQLite enforces foreign keys on every DBAPI connection created by SQLAlchemy.
    # Register the listener while the app/engine are available so PRAGMA runs for all connections.
    try:
        with app.app_context():
            if db.engine and db.engine.dialect.name == "sqlite":
                event.listen(
                    db.engine,
                    "connect",
                    lambda dbapi_conn, _rec: dbapi_conn.execute("PRAGMA foreign_keys=ON")
                )
    except Exception:
        # If engine isn't ready or something unexpected occurs, tests still include
        # defensive DDL/PRAGMA logic in individual tests.
        pass

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
