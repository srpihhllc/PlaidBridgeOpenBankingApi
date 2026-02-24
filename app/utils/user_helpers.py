# =============================================================================
# FILE: app/utils/user_helpers.py
# DESCRIPTION: Cockpit-grade user helper utilities for role/privilege checks.
# =============================================================================

import logging
from typing import Any

_logger = logging.getLogger(__name__)


def user_is_admin(user: Any | None) -> bool:
    """
    Safely determine if a user has admin privileges.
    - Checks both `is_admin` flag and `role` string.
    - Emits cockpit-grade telemetry when role is missing or unexpected.
    """
    if user is None:
        _logger.warning("user_is_admin called with None user")
        return False

    # Explicit flag check
    if getattr(user, "is_admin", False):
        return True

    # Role string check (null-safe)
    role = getattr(user, "role", None)
    if role is None:
        _logger.warning(
            "User role missing during admin check",
            extra={"user_id": getattr(user, "id", None)},
        )
        return False

    if isinstance(role, str) and role.lower() == "admin":
        return True

    # Unexpected role value — narratable for cockpit dashboards
    _logger.info(
        "User role evaluated",
        extra={"user_id": getattr(user, "id", None), "role": role},
    )
    return False
