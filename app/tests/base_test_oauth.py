# =============================================================================
# FILE: app/tests/base_test_oauth.py
# DESCRIPTION: Base class for OAuth provider tests with shared fixtures
#              and helper assertions.
# =============================================================================

import pytest
from flask import Flask

from app import create_app, db
from app.models import PlaidItem, User
from app.models.trace_events import TraceEvent


class BaseOAuthTest:
    """
    A base class for all OAuth provider tests.
    Provides shared fixtures and helper assertions.
    """

    @pytest.fixture
    def app(self):
        app = create_app()
        app.config.update(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        with app.app_context():
            try:
                db.create_all()
                yield app
            finally:
                db.session.rollback()
                db.session.remove()
                db.drop_all()

    @pytest.fixture
    def client(self, app: Flask):
        return app.test_client()

    # -------------------------------------------------------------------------
    # Shared helper assertions
    # -------------------------------------------------------------------------
    def assert_events(self, expected_types, ordered=False, details=None, exact=True):
        q = TraceEvent.query.order_by(TraceEvent.id) if ordered else TraceEvent.query
        events = q.all()
        types = [e.event_type for e in events]

        if ordered:
            assert types == expected_types
        else:
            assert set(types) == set(expected_types)
            assert len(types) == len(expected_types)

        if details:
            for etype, kv in details.items():
                matching_events = [e for e in events if e.event_type == etype]
                assert matching_events, f"No events of type '{etype}' were found."
                for event in matching_events:
                    for key, expected_value in kv.items():
                        if exact:
                            assert event.details.get(key) == expected_value, (
                                f"Expected detail '{key}' to be '{expected_value}' in "
                                f"event '{etype}'"
                            )
                        else:
                            assert expected_value in (event.details.get(key) or ""), (
                                f"Expected substring '{expected_value}' in detail "
                                f"'{key}' of event '{etype}'"
                            )

        return events

    def assert_user_created(self, email="test@example.com"):
        user = User.query.filter_by(email=email).first()
        assert user is not None
        return user

    def assert_no_user(self):
        assert User.query.count() == 0

    def assert_url_redirect(self, response, endpoint_or_path):
        assert response.status_code == 302
        assert response.headers["Location"].endswith(endpoint_or_path)

    def _assert_provider_item_created(self, item_class, user_id=None, **kwargs):
        """Generic helper to assert a provider item exists and is linked to a user."""
        query = item_class.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        for key, value in kwargs.items():
            query = query.filter(getattr(item_class, key) == value)

        item = query.first()
        assert item is not None
        assert item.user_id is not None
        return item

    def assert_plaid_item_created(self, user_id=None, item_id=None, access_token=None):
        """Asserts that a PlaidItem exists and is linked to a user."""
        return self._assert_provider_item_created(
            PlaidItem,
            user_id=user_id,
            plaid_item_id=item_id,
            plaid_access_token=access_token,
        )

    def setup_mock_user(self, email="test@example.com"):
        """
        Creates and commits a mock user in the database so that
        Plaid callbacks (or other provider flows) can associate items/sessions.
        """
        user = User(email=email, username="Mock User")
        db.session.add(user)
        db.session.commit()
        return user
