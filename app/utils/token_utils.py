# =============================================================================
# FILE: app/utils/token_utils.py
# DESCRIPTION: Cockpit‑grade token utilities with SchemaEvent persistence,
#              Redis fallback, and user_id provenance for auditability.
# =============================================================================

import json
import logging

from flask import current_app, has_app_context
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models.schema_event import SchemaEvent
from app.models.user import User
from app.utils.redis_utils import get_redis_client

_logger = logging.getLogger(__name__)


def _emit_schema_event(
    event_type: str, origin: str, detail: str, user_id: int | None = None
) -> None:
    """
    Persist a SchemaEvent row safely, with rollback on error and Redis fallback.
    Always include user_id when available for cockpit‑grade provenance.
    """
    try:
        ev = SchemaEvent(user_id=user_id, event_type=event_type, origin=origin, detail=detail)
        db.session.add(ev)
        db.session.commit()
    except Exception as exc:
        _logger.exception("Failed to persist SchemaEvent %s: %s", event_type, exc)
        try:
            db.session.rollback()
        except Exception:
            _logger.exception("Rollback failed after SchemaEvent failure")
        # Fallback: push a lightweight representation to Redis
        try:
            rc = get_redis_client()
            if rc:
                payload = json.dumps(
                    {
                        "event_type": event_type,
                        "origin": origin,
                        "detail": detail,
                        "user_id": user_id,
                    }
                )
                rc.lpush("schema_event_fallback:token", payload)
                rc.ltrim("schema_event_fallback:token", 0, 199)
        except Exception:
            _logger.exception("Redis fallback for SchemaEvent also failed")


def generate_reset_token(email: str) -> str:
    """
    Create a time‑limited reset token and emit a schema event.
    Returns the token string.
    """
    if not has_app_context():
        raise RuntimeError("generate_reset_token requires a Flask app context")

    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        _emit_schema_event(
            event_type="TOKEN_CONFIG_ERROR",
            origin="token_utils",
            detail="SECRET_KEY not configured",
        )
        raise RuntimeError("SECRET_KEY not configured")

    serializer = URLSafeTimedSerializer(secret)
    token = serializer.dumps(email, salt="password-reset-salt")

    # Resolve user_id for provenance
    user = User.query.filter_by(email=email).first()
    if not user:
        _logger.warning("Reset token issued for non‑existent email: %s", email)

    _emit_schema_event(
        event_type="RESET_TOKEN_ISSUED",
        origin="token_utils",
        detail=f"Password reset token issued for {email}",
        user_id=user.id if user else None,
    )

    return token


def verify_reset_token(token: str, expiration: int | None = None) -> str | None:
    """
    Validate a reset token and emit success/failure events.
    Returns the email on success or None on failure.
    """
    if not has_app_context():
        _logger.error("verify_reset_token called without app context")
        return None

    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        _logger.error("SECRET_KEY not configured for token verification")
        _emit_schema_event(
            event_type="TOKEN_CONFIG_ERROR",
            origin="token_utils",
            detail="SECRET_KEY not configured for verification",
        )
        return None

    expiration = expiration or current_app.config.get("RESET_TOKEN_EXPIRATION", 3600)
    serializer = URLSafeTimedSerializer(secret)

    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=expiration)
        user = User.query.filter_by(email=email).first()

        _emit_schema_event(
            event_type="TOKEN_VERIFIED_SUCCESS",
            origin="token_utils",
            detail=f"Reset token verified for {email}",
            user_id=user.id if user else None,
        )
        return email

    except SignatureExpired:
        _logger.warning("Reset token expired")
        _emit_schema_event(
            event_type="TOKEN_EXPIRED_FAILURE",
            origin="token_utils",
            detail="Reset token expired",
        )
        return None

    except BadSignature:
        _logger.warning("Reset token signature invalid")
        _emit_schema_event(
            event_type="TOKEN_INVALID_FAILURE",
            origin="token_utils",
            detail="Reset token signature invalid",
        )
        return None

    except Exception as exc:
        _logger.exception("Unexpected error verifying reset token: %s", exc)
        _emit_schema_event(
            event_type="TOKEN_VERIFICATION_ERROR",
            origin="token_utils",
            detail=f"Unexpected verification error: {str(exc)}",
        )
        return None
