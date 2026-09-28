# =============================================================================
# FILE: app/utils/user_helpers.py
# DESCRIPTION: Cockpit-grade user helper utilities for role/privilege checks.
# Standardized on PolicyEngine to eliminate hybrid checks across entities.
# =============================================================================

import logging
from typing import Any

from app.security.policy_engine import PolicyEngine, SecurityTier

_logger = logging.getLogger(__name__)


def user_is_admin(user: Any | None) -> bool:
    """
    Safely determine if a user has admin privileges (Tier 2 or higher).
    
    - Evaluates privilege through central PolicyEngine logic.
    - Emits cockpit-grade telemetry with user ID and resolved security tier.
    """
    if user is None:
        _logger.warning("user_is_admin called with None user")
        return False

    user_id = getattr(user, "id", None)
    effective_tier = PolicyEngine.resolve_effective_tier(user=user)

    # Cockpit telemetry logging
    _logger.info(
        "User privilege evaluated via PolicyEngine",
        extra={
            "user_id": user_id,
            "resolved_tier": effective_tier.name,
            "tier_level": int(effective_tier),
            "is_admin": effective_tier >= SecurityTier.ADMIN,
        },
    )

    return effective_tier >= SecurityTier.ADMIN


def get_user_effective_tier(user: Any | None) -> SecurityTier:
    """
    Resolves the exact SecurityTier enum for a given user entity via PolicyEngine.
    """
    if user is None:
        _logger.warning("get_user_effective_tier called with None user")
        return SecurityTier.GUEST
    return PolicyEngine.resolve_effective_tier(user=user)


def user_has_tier(user: Any | None, required_tier: SecurityTier) -> bool:
    """
    Checks whether a user entity meets or exceeds a target SecurityTier.
    """
    if user is None:
        return False
    return PolicyEngine.resolve_effective_tier(user=user) >= required_tier