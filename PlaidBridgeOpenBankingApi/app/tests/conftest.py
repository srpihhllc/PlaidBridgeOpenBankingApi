# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/conftest.py

import pytest
import sqlalchemy as sa
from sqlalchemy import event

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

    # Register an engine-level connect listener so PRAGMA foreign_keys=ON is
    # applied to every new DBAPI connection.  SQLite's FK enforcement is
    # per-connection, so this must be done here (not just inside a test).
    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # For SQLite with StaticPool (in-memory), the single DBAPI connection
        # is created before this fixture runs, so also apply the PRAGMA to any
        # already-established connection in the pool right now.
        if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
            raw = db.engine.raw_connection()
            try:
                cursor = raw.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            finally:
                raw.close()

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