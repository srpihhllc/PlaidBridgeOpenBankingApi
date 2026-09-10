# app/tests/test_access_decorators_user_is_admin_line18.py

from unittest.mock import MagicMock, patch
from app.decorators.access import user_is_admin


def test_user_is_admin_role_super_admin_branch():
    """
    Covers line 18 in access.py:
        return current_user.role in ("admin", "super_admin")
    """

    fake_user = MagicMock()

    # Ensure is_admin is missing so the role branch is used
    if hasattr(fake_user, "is_admin"):
        delattr(fake_user, "is_admin")

    # Trigger the exact uncovered branch
    fake_user.role = "super_admin"

    with patch("app.decorators.access.current_user", fake_user):
        assert user_is_admin() is True
