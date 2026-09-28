# =============================================================================
# FILE: app/auth_handlers.py
# DESCRIPTION: Unified identity resolution and authentication lifecycles
#              handling both Stateful (Session UI) and Stateless (JWT API)
#              contexts strictly via persisted User records or SystemOperator intercepts.
# =============================================================================

from __future__ import annotations

import logging

from flask import current_app

from app.extensions import db, jwt, login_manager
from app.models.user import User

logger = logging.getLogger(__name__)


class SystemOperator:
    """Virtual identity principal for system operator / GOD-MODE intercepts."""

    def __init__(
        self,
        identity: str = "TERENCE_CORTEX_PRIME",
        username: str = "OPERATOR_ADMIN",
        role: str = "subscriber",
    ):
        self.id = identity
        self.username = username
        self.role = role
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        self.is_operator = True

    def get_id(self) -> str:
        """Returns the unique identifier string required by Flask-Login user interface contract."""
        return str(self.id)


# -------------------------------------------------------------------
# ⚙️ CORE IDENTITY RESOLUTION ENGINE (INTERNAL ONLY)
# -------------------------------------------------------------------
def _resolve_identity(identity: str | None) -> User | SystemOperator | None:
    """Centralized pipeline for database and system operator identity translation.

    Handles string sanitization, GOD-MODE intercepts, and database principal resolution.
    """
    if not identity:
        return None

    clean_id = str(identity).strip()
    if clean_id.lower() in ("", "none", "null"):
        return None

    # Retrieve system operator settings from active Flask context
    operator_enabled = True
    target_operator_id = "TERENCE_CORTEX_PRIME"
    if current_app:
        operator_enabled = current_app.config.get("SYSTEM_OPERATOR_ENABLED", True)
        target_operator_id = current_app.config.get("SYSTEM_OPERATOR_ID", "TERENCE_CORTEX_PRIME")

    # GOD-MODE / SystemOperator Intercept
    if operator_enabled and (clean_id == target_operator_id or clean_id.startswith("OPERATOR_")):
        return SystemOperator(identity=clean_id, username="OPERATOR_ADMIN", role="subscriber")

    try:
        # 1. Primary Strategy: String/UUID Primary Key lookup
        user = db.session.get(User, clean_id)
        if user:
            return user

        # 2. Migration Strategy: Safe Integer Key parsing fallback
        try:
            int_id = int(clean_id)
            user = db.session.get(User, int_id)
            if user:
                return user
        except (ValueError, TypeError):
            pass

        # 3. Consistency Strategy: Direct ORM query fallback
        return User.query.filter_by(id=clean_id).first()

    except Exception:
        logger.exception(
            "Security Boundary Exception: Failed to resolve identity "
            "mapping for payload '%s'",
            clean_id,
        )
        return None


# -------------------------------------------------------------------
# 🔑 1. SESSION BOUNDARY (Flask-Login Cookie Auth for UI)
# -------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id: str) -> User | SystemOperator | None:
    """Loads a user principal out of a stateful UI session cookie context."""
    return _resolve_identity(user_id)


# -------------------------------------------------------------------
# 🛰️ 2. BEARER BOUNDARY (Flask-JWT-Extended Token Auth for API)
# -------------------------------------------------------------------
@jwt.user_lookup_loader
def user_lookup_callback(
    _jwt_header, jwt_data: dict
) -> User | SystemOperator | None:
    """Loads a user principal out of a stateless JWT bearer token payload."""
    if not jwt_data:
        return None

    raw_sub = jwt_data.get("sub") or jwt_data.get("identity")

    # Unpack nested token claim payload dictionaries if present
    if isinstance(raw_sub, dict):
        identity = raw_sub.get("identity") or raw_sub.get("username") or raw_sub.get("id")
    else:
        identity = raw_sub

    return _resolve_identity(identity)