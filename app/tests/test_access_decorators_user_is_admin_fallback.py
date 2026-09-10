# app/tests/test_access_decorators_user_is_admin_fallback.py

from unittest.mock import MagicMock, patch
from app.decorators.access import user_is_admin


def test_user_is_admin_final_fallback_returns_false():
    """
    Covers line 18 in access.py:
        return False

    This executes only when current_user has neither is_admin nor role.
    """

    fake_user = MagicMock()

    # Ensure is_admin is missing
    if hasattr(fake_user, "is_admin"):
        delattr(fake_user, "is_admin")

    # Ensure role is missing
    if hasattr(fake_user, "role"):
        delattr(fake_user, "role")

    with patch("app.decorators.access.current_user", fake_user):
        assert user_is_admin() is False
