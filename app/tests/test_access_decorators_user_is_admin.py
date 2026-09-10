# app/tests/test_access_decorators_user_is_admin.py

from unittest.mock import MagicMock, patch
from app.decorators.access import user_is_admin


def test_user_is_admin_true_when_is_admin_attribute_present():
    """
    Covers line 15:
        return current_user.is_admin
    """
    fake_user = MagicMock()
    fake_user.is_admin = True

    with patch("app.decorators.access.current_user", fake_user):
        assert user_is_admin() is True


def test_user_is_admin_true_when_role_is_super_admin():
    """
    Covers line 18:
        return current_user.role in ("admin", "super_admin")
    """
    fake_user = MagicMock()
    # Ensure is_admin is missing so we hit the role branch
    if hasattr(fake_user, "is_admin"):
        delattr(fake_user, "is_admin")

    fake_user.role = "super_admin"

    with patch("app.decorators.access.current_user", fake_user):
        assert user_is_admin() is True
