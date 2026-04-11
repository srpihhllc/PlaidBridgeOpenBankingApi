"""
Pytest fixtures for the test suite.

Notes:
- Single canonical session-scoped `app` fixture seeds an admin user at startup.
- No session-scoped fixture depends on a narrower-scoped fixture (avoids ScopeMismatch).
- Tests may still define their own function-scoped fixtures, but they will not
  conflict with the session-scoped app fixture used for global setup.
- The `client` fixture uses row deletion for per-test isolation instead of
  drop_all/create_all, so the session-scoped schema is never destroyed mid-session.
  (SQLAlchemy 2.x removed session.bind; transaction rollback via connection binding
  is not supported in Flask-SQLAlchemy 3.x + SQLAlchemy 2.x.)
- Test-only routes (e.g. for test_validation.py) are registered here inside the
  `app` fixture before yield, guaranteeing they exist before the first request.
"""

import os
import uuid

# Ensure the test environment is set before importing the app so the package
# shim does not detect production at import-time and create the unsafe fallback.
os.environ["FLASK_ENV"] = "testing"

import pytest
from flask import jsonify as _jsonify
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db as _db, init_extensions
from app.models.user import User
from app.models.trace_events import TraceEvent


@pytest.fixture(scope="session")
def app():
    """Create application for the tests and seed a baseline admin user."""
    application = create_app(env_name="testing")

    # Defensive: ensure testing flags are set
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["TESTING"] = True

    # Initialize extensions (ensure extensions like JWT, mail, limiter, etc. are ready)
    # and use app context to create DB and seed admin user once per test session
    try:
        init_extensions(application)
    except Exception:
        # If extensions were already initialized or init fails in this environment,
        # continue — we only need the DB for tests to run.
        pass

    # ------------------------------------------------------------------
    # Register test-only routes BEFORE yield so they exist before the
    # first request. Flask forbids route registration after _got_first_request.
    # These routes are used by test_validation.py.
    # ------------------------------------------------------------------
    from app.api.validation import validate_json_schema as _vjson

    _validation_schema = {
        "type": "object",
        "properties": {"foo": {"type": "string"}},
        "required": ["foo"],
    }
    _existing = {rule.endpoint for rule in application.url_map.iter_rules()}

    if "dummy_invalid" not in _existing:
        @application.route("/dummy_invalid", methods=["POST"])
        @_vjson(_validation_schema)
        def dummy_invalid():
            return _jsonify({"status": "ok"}), 200

    if "dummy_malformed" not in _existing:
        @application.route("/dummy_malformed", methods=["POST"])
        @_vjson(_validation_schema)
        def dummy_malformed():
            return _jsonify({"status": "ok"}), 200

    if "dummy_violation" not in _existing:
        @application.route("/dummy_violation", methods=["POST"])
        @_vjson(_validation_schema)
        def dummy_violation():
            return _jsonify({"status": "ok"}), 200

    if "dummy_valid" not in _existing:
        @application.route("/dummy_valid", methods=["POST"])
        @_vjson(_validation_schema)
        def dummy_valid():
            return _jsonify({"status": "ok"}), 200

    with application.app_context():
        # Ensure schema exists for the session-scoped app fixture
        _db.create_all()

        # Seed admin if missing (id deterministic so other tests can reference it)
        admin_email = "srpollardsihhllc@gmail.com"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            admin = User(
                id="00000000-0000-0000-0000-000000000001",
                username="srpihhllc",
                email=admin_email,
                password_hash=generate_password_hash("adminpass"),
                is_admin=True,
            )
            _db.session.add(admin)
            _db.session.commit()

    yield application

    # Teardown: remove session and drop all tables from the test database
    with application.app_context():
        try:
            _db.session.remove()
            _db.drop_all()
        except Exception:
            # Best-effort teardown; don't raise to avoid masking test results
            pass


@pytest.fixture(scope="session")
def db_session(app):
    """Provide a DB session for session-scoped fixtures that need DB access."""
    with app.app_context():
        yield _db.session


@pytest.fixture
def db(app):
    """Provide the SQLAlchemy db object (convenience alias for tests)."""
    with app.app_context():
        yield _db


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


def _reseed_admin(application):
    """Re-insert the deterministic admin user if it was deleted during a test."""
    admin_email = "srpollardsihhllc@gmail.com"
    admin = User.query.filter_by(email=admin_email).first()
    if not admin:
        admin = User(
            id="00000000-0000-0000-0000-000000000001",
            username="srpihhllc",
            email=admin_email,
            password_hash=generate_password_hash("adminpass"),
            is_admin=True,
        )
        _db.session.add(admin)
        _db.session.commit()


@pytest.fixture
def client(app):
    """A test client for the app. Uses row deletion for per-test isolation.

    Compatible with SQLAlchemy 2.x and Flask-SQLAlchemy 3.x.
    Does NOT call drop_all(), so the session-scoped schema is never destroyed.
    The seeded admin user is restored after each test so subsequent tests that
    depend on it remain unaffected.
    """
    with app.app_context():
        # no-op if schema already exists from the session-scoped app fixture
        _db.create_all()

        test_client = app.test_client()
        try:
            yield test_client
        finally:
            _db.session.remove()

            # Delete all rows in reverse FK order — preserves schema, no drop_all
            for table in reversed(_db.metadata.sorted_tables):
                try:
                    _db.session.execute(table.delete())
                except Exception:
                    _db.session.rollback()

            try:
                _db.session.commit()
            except Exception:
                _db.session.rollback()

            # Restore the seeded admin so session-scoped fixtures stay consistent
            try:
                _reseed_admin(app)
            except Exception:
                _db.session.rollback()


@pytest.fixture
def user_factory(db_session):
    """Return a callable that creates and returns User rows.

    Usage:
        user = user_factory(username="alice", password="Password123!", role="subscriber")
    """
    def _create(**kwargs):
        # Extract test-only args that should not be passed into User()
        password = kwargs.pop("password", None)
        role = kwargs.pop("role", None)

        # Defaults
        data = {
            "id": kwargs.pop("id", str(uuid.uuid4())),
            "username": kwargs.pop("username", "testuser"),
            # unique email to avoid unique-constraint collisions
            "email": kwargs.pop("email", f"testuser+{uuid.uuid4().hex[:6]}@example.com"),
            "is_admin": kwargs.pop("is_admin", False),
        }
        # Merge any other mapped fields provided by caller
        data.update(kwargs)

        user = User(**data)

        # Apply password via helper if available, otherwise set password_hash directly
        if password:
            if hasattr(user, "set_password") and callable(user.set_password):
                user.set_password(password)
            else:
                user.password_hash = generate_password_hash(password)

        # Apply role if requested
        if role is not None:
            try:
                user.role = role
            except Exception:
                pass
            user.is_admin = True if str(role).lower() == "admin" else user.is_admin

        db_session.add(user)
        db_session.commit()

        # Best-effort: create SubscriberProfile only if the model is importable
        if role is not None and str(role).lower() == "subscriber":
            try:
                from app.models.subscriptions_and_profiles import SubscriberProfile
            except Exception:
                SubscriberProfile = None

            if SubscriberProfile is not None:
                try:
                    profile = SubscriberProfile(user_id=user.id)
                    db_session.add(profile)
                    db_session.commit()
                    user.subscriber_profile = profile
                except Exception:
                    db_session.rollback()

        return user

    return _create


@pytest.fixture(autouse=True)
def clear_trace_events_between_tests(app):
    """
    Autouse fixture that clears TraceEvent rows before and after each test to avoid
    cross-test pollution for tests that assert on trace events.
    """
    with app.app_context():
        try:
            TraceEvent.query.delete()
            _db.session.commit()
        except Exception:
            _db.session.rollback()
    yield
    with app.app_context():
        try:
            TraceEvent.query.delete()
            _db.session.commit()
        except Exception:
            _db.session.rollback()