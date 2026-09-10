# =============================================================================
# FILE: app/tests/conftest.py
# =============================================================================
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
- Autouse fixtures dynamically configure environment keys and mock global telemetry.
"""

import datetime
import os
import uuid
from unittest.mock import patch

# Ensure the test environment is set before importing the app so the package
# shim does not detect production at import-time and create the unsafe fallback.
os.environ["FLASK_ENV"] = "testing"

import pytest
from cryptography.fernet import Fernet
from flask import jsonify as _jsonify
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db as _db
from app.extensions import init_extensions
from app.models.trace_events import TraceEvent
from app.models.user import User

# =============================================================================
# GLOBAL AUTO-USE FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def set_plaid_encryption_key(monkeypatch):
    """Automatically supply a valid Fernet key for Plaid token encryption tests."""
    fake_key = Fernet.generate_key().decode()
    monkeypatch.setenv("PLAID_ENCRYPTION_KEY", fake_key)


@pytest.fixture(autouse=True)
def mock_global_ttl_emit():
    """Stub out telemetry calls to avoid signature mismatched errors during tests."""
    with patch(
        "app.blueprints.plaid_routes.ttl_emit", create=True
    ) as mock_emit:
        mock_emit.return_value = None
        yield mock_emit


# =============================================================================
# CORE APPLICATION & DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def app():
    """Create application for the tests and seed a baseline admin user."""
    application = create_app(env_name="testing")

    # Defensive: ensure testing flags are set
    application.config["WTF_CSRF_ENABLED"] = False
    application.config["TESTING"] = True

    # Initialize extensions (ensure extensions like JWT, mail, limiter, etc. are ready)
    try:
        init_extensions(application)
    except Exception:
        # If extensions were already initialized or init fails in this environment,
        # continue — we only need the DB for tests to run.
        pass

    # ------------------------------------------------------------------
    # Flask-Login Robust User Loader Override
    # Converts incoming string IDs to UUID objects if standard lookup fails.
    # ------------------------------------------------------------------
    if hasattr(application, "login_manager"):
        try:

            @application.login_manager.user_loader
            def robust_load_user(user_id):
                if not user_id:
                    return None
                # Modern SQLAlchemy 2.x lookup
                user = _db.session.get(User, user_id)
                if not user:
                    try:
                        # UUID fallback using modern API
                        user = _db.session.get(User, uuid.UUID(str(user_id)))
                    except (ValueError, AttributeError):
                        pass
                return user

        except Exception:
            pass

    # ------------------------------------------------------------------
    # JWT -> Flask-Login Auth Bridge (Type-Resilient Variant)
    # Ensures that when a test sends an explicit Bearer Token header,
    # Flask-Login's current_user state is accurately synchronized.
    # ------------------------------------------------------------------
    @application.before_request
    def load_user_from_jwt_bridge():
        from flask_login import current_user, login_user

        # Skip processing if session cookie auth already successfully hydrated the user
        if current_user.is_authenticated:
            return

        try:
            if (
                hasattr(application, "extensions")
                and "flask-jwt-extended" in application.extensions
            ):
                from flask_jwt_extended import (
                    get_jwt_identity,
                    verify_jwt_in_request,
                )

                # Check for token without raising unhandled exceptions out of context
                verify_jwt_in_request(optional=True)
                identity = get_jwt_identity()

                if identity:
                    # Attempt standard string resolution lookup first
                    user = _db.session.get(User, identity)

                    # Fallback to explicit UUID object coercion if primary key type mismatch occurs
                    if not user:
                        try:
                            user = _db.session.get(
                                User, uuid.UUID(str(identity))
                            )
                        except (ValueError, AttributeError):
                            pass

                    if user:
                        # Log user into the local request-context tracking frame
                        login_user(user, remember=False)
        except Exception:
            # Fallback cleanly to AnonymousUserMixin if token validation fails
            pass

    # ------------------------------------------------------------------
    # Dynamic Test-Only Route Registration
    # ------------------------------------------------------------------
    # Routes are injected into the routing matrix prior to context yield.
    # Flask strictly prohibits runtime registration after the first request.
    # ------------------------------------------------------------------
    from app.api.validation import validate_json_schema as _vjson

    _validation_schema = {
        "type": "object",
        "properties": {"foo": {"type": "string"}},
        "required": ["foo"],
    }
    _existing_endpoints = {
        rule.endpoint for rule in application.url_map.iter_rules()
    }

    # Idempotent declaration matrix for validation smoke targets
    _dummy_routes = [
        ("dummy_invalid", "/dummy_invalid"),
        ("dummy_malformed", "/dummy_malformed"),
        ("dummy_violation", "/dummy_violation"),
        ("dummy_valid", "/dummy_valid"),
    ]

    for endpoint, route_path in _dummy_routes:
        if endpoint not in _existing_endpoints:

            @application.route(route_path, methods=["POST"], endpoint=endpoint)
            @_vjson(_validation_schema)
            def _handler_factory():
                return _jsonify({"status": "ok"}), 200

    with application.app_context():
        # Authoritatively evaluate and register all application models prior to compilation
        import app.models

        # Explicitly touch the imported module and models to satisfy unused import linters (F401)
        _ = (app.models, TraceEvent)

        # Build pristine schema structures for the session lifecycle
        _db.create_all()

        # Seed global admin user under the unified test credentials
        admin_email = os.environ.get(
            "ADMIN_EMAIL", "srpollardsihhllc@gmail.com"
        )
        admin_username = os.environ.get("ADMIN_USERNAME", "srpihhllc")
        # Modern SQLAlchemy 2.x: select + scalar_one_or_none
        from sqlalchemy import select

        stmt = select(User).filter_by(email=admin_email)
        admin = _db.session.execute(stmt).scalar_one_or_none()

        if not admin:
            admin = User(
                id="00000000-0000-0000-0000-000000000001",
                username=admin_username,
                email=admin_email,
                password_hash=generate_password_hash("AdminPass123!"),
                is_admin=True,
            )
            _db.session.add(admin)
            _db.session.commit()

    yield application

    # ------------------------------------------------------------------
    # Global Session Teardown
    # ------------------------------------------------------------------
    with application.app_context():
        try:
            _db.session.remove()
            _db.drop_all()
        except Exception:
            # Defensive catch to shield test result formatting from teardown failures
            pass


@pytest.fixture(scope="session")
def db_session(app):
    """Provide an isolated database session mapping to the session-scoped application."""
    with app.app_context():
        yield _db.session


@pytest.fixture
def db(app):
    """Provide a contextual interface wrapper for the SQLAlchemy instance."""
    with app.app_context():
        yield _db


@pytest.fixture
def templates(app):
    """Interceptors to catch and log templates rendered inside the execution scope."""
    from flask import template_rendered

    recorded = []

    def record(sender, template, context, **extra):
        recorded.append(template)

    template_rendered.connect(record, app)
    yield recorded
    template_rendered.disconnect(record, app)


def _reseed_admin(application):
    """Re-seed baseline admin state contextually when row flushes occur."""
    admin_email = os.environ.get("ADMIN_EMAIL", "srpollardsihhllc@gmail.com")
    admin_username = os.environ.get("ADMIN_USERNAME", "srpihhllc")
    # Modern SQLAlchemy 2.x
    from sqlalchemy import select

    stmt = select(User).filter_by(email=admin_email)
    admin = _db.session.execute(stmt).scalar_one_or_none()

    if not admin:
        admin = User(
            id="00000000-0000-0000-0000-000000000001",
            username=admin_username,
            email=admin_email,
            password_hash=generate_password_hash("AdminPass123!"),
            is_admin=True,
        )
        _db.session.add(admin)
        _db.session.commit()


@pytest.fixture
def client(app):
    """
    HTTP Client context utilizing foreign-key sequence row clearing.
    Maintains extreme speed by evading complete schema drop/re-creation steps.
    """
    with app.app_context():
        _db.create_all()
        test_client = app.test_client()
        try:
            yield test_client
        finally:
            _db.session.remove()

            # Execute explicit target row deletions across all schema components
            for table in reversed(_db.metadata.sorted_tables):
                try:
                    _db.session.execute(table.delete())
                except Exception:
                    _db.session.rollback()

            try:
                _db.session.commit()
            except Exception:
                _db.session.rollback()

            # Restore synchronized global state matrix
            try:
                _reseed_admin(app)
            except Exception:
                _db.session.rollback()


@pytest.fixture
def user_factory(db_session):
    """
    Unified testing factory generating flexible account states.
    Automates multi-tier status and subscription profile links dynamically.
    """

    def _create(**kwargs):
        password = kwargs.pop("password", None)
        role = kwargs.pop("role", None)
        is_active_val = kwargs.pop("is_active", True)

        # Build clean execution parameters
        data = {
            "id": kwargs.pop("id", str(uuid.uuid4())),
            "username": kwargs.pop("username", "testuser"),
            "email": kwargs.pop(
                "email", f"testuser+{uuid.uuid4().hex[:6]}@example.com"
            ),
            "is_admin": kwargs.pop("is_admin", False),
        }
        data.update(kwargs)
        user = User(**data)

        # Resilient mapping framework for user target statuses
        try:
            user.is_active = is_active_val
        except AttributeError:
            if hasattr(user, "active"):
                try:
                    user.active = is_active_val
                except Exception:
                    pass
            elif hasattr(user, "status") and is_active_val:
                try:
                    user.status = "active"
                except Exception:
                    pass

        # Handle cryptographic credential processing
        if password:
            if hasattr(user, "set_password") and callable(user.set_password):
                user.set_password(password)
            else:
                user.password_hash = generate_password_hash(password)

        if role is not None:
            try:
                user.role = role
            except Exception:
                pass
            user.is_admin = (
                True if str(role).lower() == "admin" else user.is_admin
            )

        db_session.add(user)
        db_session.commit()

        # Handle specialized user downstream context bindings
        if role is not None and str(role).lower() == "subscriber":
            try:
                from app.models.subscriptions_and_profiles import (
                    SubscriberProfile,
                )
            except Exception:
                SubscriberProfile = None

            if SubscriberProfile is not None:
                try:
                    profile = SubscriberProfile(user_id=user.id)
                    if hasattr(profile, "onboarding_completed"):
                        profile.onboarding_completed = True
                    if hasattr(profile, "status"):
                        profile.status = "active"

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
    Isolation sentinel clearing system metrics on pre- and post-flight bounds.
    Eliminates cross-contamination parameters during analytics/telemetry tests.
    """
    with app.app_context():
        try:
            # Modern SQLAlchemy 2.x bulk delete
            from sqlalchemy import delete

            stmt = delete(TraceEvent)
            _db.session.execute(stmt)
            _db.session.commit()
        except Exception:
            _db.session.rollback()
    yield
    with app.app_context():
        try:
            from sqlalchemy import delete

            stmt = delete(TraceEvent)
            _db.session.execute(stmt)
            _db.session.commit()
        except Exception:
            _db.session.rollback()


# =============================================================================
# INJECTED SECURITY CONTEXT FIXTURES
# =============================================================================


@pytest.fixture
def auth_headers(client, app, user_factory):
    """
    Creates a valid subscriber user (with an attached profile), injects a synchronized
    Flask-Login session context into the client cookie jar, and returns the canonical
    auth headers (including a fresh JWT token) required by the application's test context.
    """
    # 1. Generate a true subscriber to satisfy subscriber-guarded backend routes
    test_subscriber = user_factory(
        username="dashboard_tester", role="subscriber"
    )

    # 2. Build a real Flask-Login session inside a request context to match production identifiers
    sess_id = None
    if hasattr(app, "login_manager"):
        with app.test_request_context(headers={"User-Agent": "pytest"}):
            from flask_login import login_user

            login_user(test_subscriber, remember=False, fresh=True)
            try:
                sess_id = app.login_manager._session_identifier_generator()
            except AttributeError:
                pass

    # 3. Inject matching session keys into the test client's session cookie transaction
    # Prefer signing serializer when available so the cookie matches production format
    s = app.session_interface.get_signing_serializer(app)
    if s is not None:
        session_dict = {"_user_id": str(test_subscriber.id), "_fresh": True}
        if sess_id:
            session_dict["_id"] = sess_id
        cookie_val = s.dumps(session_dict)

        # Safely fall back to "localhost" if SERVER_NAME key exists as None
        server_name = app.config.get("SERVER_NAME") or "localhost"
        host = server_name.split(":")[0]
        cookie_name = app.config.get("SESSION_COOKIE_NAME", "session")

        # Safe cross-version syntax via explicit keyword assignment
        client.set_cookie(
            key=cookie_name, value=cookie_val, domain=host, path="/"
        )
    else:
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_subscriber.id)
            sess["_fresh"] = True
            if sess_id:
                sess["_id"] = sess_id

    # 4. Build canonical request headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "pytest",
    }

    # 5. Inject Token-Based Header Auth (Fully synchronized with session state)
    with app.app_context():
        if (
            hasattr(app, "extensions")
            and "flask-jwt-extended" in app.extensions
        ):
            from flask_jwt_extended import create_access_token

            # Set fresh=True to satisfy endpoints requiring fresh tokens or strict checks
            token = create_access_token(
                identity=str(test_subscriber.id), fresh=True
            )
            headers["Authorization"] = f"Bearer {token}"

        elif hasattr(test_subscriber, "generate_auth_token"):
            token = test_subscriber.generate_auth_token()
            headers["Authorization"] = f"Bearer {token}"

        else:
            try:
                import jwt as pyjwt

                # Fail fast if SECRET_KEY is not configured for the test app
                secret = app.config.get("SECRET_KEY")
                assert (
                    secret
                ), "Test app must set SECRET_KEY for pyjwt fallback"
                token = pyjwt.encode(
                    {
                        "sub": str(test_subscriber.id),
                        "iat": datetime.datetime.now(datetime.timezone.utc),
                        "fresh": True,
                    },
                    secret,
                    algorithm=app.config.get("JWT_ALGORITHM", "HS256"),
                )
                # Normalize bytes -> str for header safety
                if isinstance(token, bytes):
                    token = token.decode("utf-8")
                headers["Authorization"] = f"Bearer {token}"
            except Exception:
                headers["Authorization"] = (
                    "Bearer mock-subscriber-token-xyz123"
                )

    return headers
