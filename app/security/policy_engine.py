# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/security/policy_engine.py
"""
Unified Policy Engine for PlaidBridgeOpenBankingApi.
Provides a single authorization authority across UI sessions and API endpoints.
Calculates SecurityTier hierarchy and enforces short-lived Redis operator ignitions.
"""

from enum import IntEnum
from time import time
from typing import Any, Dict, Optional

from flask import current_app, request, session
from flask_login import current_user


class SecurityTier(IntEnum):
    """Immutable hierarchy of application security tiers."""
    GUEST = 0
    SUBSCRIBER = 10
    ADMIN = 20
    SUPER_ADMIN = 30
    SYSTEM_OPERATOR = 100


ROLE_TIER_MAP: Dict[str, SecurityTier] = {
    "guest": SecurityTier.GUEST,
    "subscriber": SecurityTier.SUBSCRIBER,
    "user": SecurityTier.SUBSCRIBER,
    "admin": SecurityTier.ADMIN,
    "super_admin": SecurityTier.SUPER_ADMIN,
    "system_operator": SecurityTier.SYSTEM_OPERATOR,
    "operator": SecurityTier.SYSTEM_OPERATOR,
}


class PolicyEngine:
    """Central authority for resolving effective privileges and authorizing requests."""

    OPERATOR_SESSION_KEY = "operator_mode"
    ALT_OPERATOR_SESSION_KEY = "operator_ignition_active"
    OPERATOR_REDIS_PREFIX = "operator:ignition:"

    @classmethod
    def resolve_effective_tier(
        cls,
        user: Optional[Any] = None,
        session_obj: Optional[Dict[str, Any]] = None,
        jwt_claims: Optional[Dict[str, Any]] = None,
    ) -> SecurityTier:
        """
        Calculates the highest valid SecurityTier across active JWT claims,
        Flask web session state, database attributes, and Redis ignition TTL.
        """
        evaluated_tiers = [SecurityTier.GUEST]
        active_session = session_obj if session_obj is not None else (session if session else {})

        # 1. Operator Ignition Evaluation (Highest Priority)
        if cls._verify_operator_ignition(active_session, user):
            return SecurityTier.SYSTEM_OPERATOR

        # 2. JWT Claims Evaluation (API Context)
        if jwt_claims and isinstance(jwt_claims, dict):
            raw_roles = jwt_claims.get("roles")

            if raw_roles is None:
                raw_roles = jwt_claims.get("role", "guest")

            if isinstance(raw_roles, str):
                raw_roles = [raw_roles]

            if not isinstance(raw_roles, (list, tuple, set)):
                raw_roles = ["guest"]

            jwt_tier = max(
                (
                    ROLE_TIER_MAP.get(
                        str(role).strip().lower(),
                        SecurityTier.GUEST,
                    )
                    for role in raw_roles
                ),
                default=SecurityTier.GUEST,
            )

            if jwt_claims.get("is_admin"):
                jwt_tier = max(jwt_tier, SecurityTier.ADMIN)

            evaluated_tiers.append(jwt_tier)

        # 3. User Identity Model Evaluation (Session/User Context)
        active_user = user or (
            current_user if getattr(current_user, "is_authenticated", False) else None
        )
        if active_user and getattr(active_user, "is_authenticated", False):
            user_role = str(getattr(active_user, "role", "subscriber")).lower()
            user_tier = ROLE_TIER_MAP.get(user_role, SecurityTier.SUBSCRIBER)

            if getattr(active_user, "is_superuser", False):
                user_tier = max(user_tier, SecurityTier.SUPER_ADMIN)
            elif getattr(active_user, "is_admin", False):
                user_tier = max(user_tier, SecurityTier.ADMIN)

            evaluated_tiers.append(user_tier)

        return max(evaluated_tiers)

    @classmethod
    def evaluate_request(cls, required_tier: SecurityTier) -> bool:
        """Convenience method for direct boolean route checks across current context."""
        jwt_claims = getattr(request, "jwt_claims", None)
        active_user = current_user if getattr(current_user, "is_authenticated", False) else None
        active_session = session if session else None

        effective_tier = cls.resolve_effective_tier(
            user=active_user,
            session_obj=active_session,
            jwt_claims=jwt_claims,
        )
        return effective_tier >= required_tier

    @classmethod
    def _verify_operator_ignition(cls, session_obj: Any, user: Optional[Any]) -> bool:
        """
        Validates operator ignition status against session timestamps and short-lived Redis TTLs.
        Purges invalid or expired operator mode flags from the active session.
        """
        try:
            if not session_obj:
                return False

            is_active = session_obj.get(cls.OPERATOR_SESSION_KEY) or session_obj.get(
                cls.ALT_OPERATOR_SESSION_KEY
            )
            if not is_active:
                return False

            operator_id = session_obj.get("operator_id") or getattr(user, "id", None)

            # 1. Verify Redis TTL if Redis client is attached to application context
            redis_client = getattr(current_app, "redis_client", None) or getattr(
                current_app, "redis", None
            )
            if redis_client and operator_id:
                cache_key = f"{cls.OPERATOR_REDIS_PREFIX}{operator_id}"
                try:
                    ttl_remaining = redis_client.ttl(cache_key)
                    if ttl_remaining <= 0:
                        cls._purge_operator_session(session_obj)
                        return False
                except Exception as cache_err:
                    if current_app:
                        current_app.logger.warning(
                            f"Redis ignition check fallback: {cache_err}"
                        )

            # 2. Verify Session-level TTL timestamp fallback
            start_time = session_obj.get("operator_mode_start_time", 0)
            ttl = session_obj.get("operator_mode_ttl", 0)
            if start_time and ttl and (time() - start_time > ttl):
                cls._purge_operator_session(session_obj)
                return False

            return True
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error verifying operator ignition: {e}")
            return False

    @classmethod
    def _purge_operator_session(cls, session_obj: Any) -> None:
        """Safely strips all operator elevation state from session."""
        if hasattr(session_obj, "pop"):
            session_obj.pop(cls.OPERATOR_SESSION_KEY, None)
            session_obj.pop(cls.ALT_OPERATOR_SESSION_KEY, None)
            session_obj.pop("operator_mode_start_time", None)
            session_obj.pop("operator_mode_ttl", None)