# =============================================================================
# FILE: app/tests/test_infra.py
# DESCRIPTION: Infrastructure Smoke Tests (Redis, DB, Extensions)
# =============================================================================

import pytest

from app.extensions import db


def test_redis_connection(app):
    """
    Smoke test: Verify Redis is reachable and writable via the app instance.
    """
    # 1. Pull the client from the app object (where init_extensions stored it)
    rc = getattr(app, "redis_client", None)

    assert rc is not None, "Redis client was not found on the app instance. Check init_extensions."

    # 2. Try a basic Write/Read operation
    test_key = "infra_smoke_test"
    test_val = "functional"

    try:
        rc.set(test_key, test_val, ex=10)
        retrieved_val = rc.get(test_key)

        if isinstance(retrieved_val, bytes):
            retrieved_val = retrieved_val.decode("utf-8")

        assert retrieved_val == test_val
        rc.delete(test_key)
    except Exception as e:
        pytest.fail(f"Redis operation failed: {e}")


def test_database_connectivity(app):
    """
    Smoke test: Verify SQLAlchemy can execute a query.
    """
    with app.app_context():
        try:
            # result = db.session.execute(db.text("SELECT 1")).scalar()
            # If 'db' is also giving issues, access it via app.extensions
            result = app.extensions["sqlalchemy"].session.execute(db.text("SELECT 1")).scalar()
            assert result == 1
        except Exception as e:
            pytest.fail(f"Database infrastructure is DOWN: {e}")


def test_jwt_extension_loading(app):
    """
    Verify JWT manager is correctly attached to the app.
    """
    assert "jwt" in app.extensions, "JWT extension failed to register during init_extensions"


def test_user_table_exists(app):
    """
    Verify that the User table was actually created (essential for admin routes).
    """
    with app.app_context():
        from sqlalchemy import inspect

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        assert "user" in tables or "users" in tables, f"User table missing! Found: {tables}"
