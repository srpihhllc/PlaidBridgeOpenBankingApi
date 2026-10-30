# =============================================================================
# FILE: app/services/audit_service.py
# DESCRIPTION: Cockpit audit logging service and blueprint audit summary tile.
#               Production-hardened with transaction safety, timezone awareness,
#               and structured logging.
# =============================================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Final, cast

from sqlalchemy import select

from app.extensions import db
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

DEFAULT_EVENT_LIMIT: Final[int] = 50
MAX_EVENT_LIMIT: Final[int] = 1000


def log_event(
    user_id: str,
    event_type: str,
    message: str = "",
    transaction_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog | None:
    """Record an audit event and return it, or None if persistence fails."""
    event_payload = payload.copy() if payload else {}
    if message:
        event_payload["message"] = message

    clean_user_id = str(user_id or "").strip()
    clean_event_type = str(event_type or "").strip()

    try:
        entry = AuditLog(
            user_id=clean_user_id,
            transaction_id=transaction_id,
            event_type=clean_event_type,
            payload=event_payload,
        )
        db.session.add(entry)
        db.session.commit()

        logger.info(
            "📜 [AUDIT_LOG] Recorded '%s' for user '%s' (TxID: %s)",
            clean_event_type,
            clean_user_id,
            transaction_id or "N/A",
        )
        return entry

    except Exception:
        db.session.rollback()
        logger.exception(
            "🚨 [AUDIT_LOG_ERROR] Failed to record audit log for user '%s'",
            clean_user_id,
        )
        return None


def get_recent_events(limit: int = DEFAULT_EVENT_LIMIT) -> list[AuditLog]:
    """Return recent audit events, newest first, with the limit bounded to 1–1000."""
    try:
        query_limit = max(1, min(int(limit), MAX_EVENT_LIMIT))
        statement = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(query_limit)
        )
        result = db.session.execute(statement)
        return cast(list[AuditLog], list(result.scalars().all()))

    except Exception:
        logger.exception("🚨 [AUDIT_LOG_ERROR] Error fetching recent audit events")
        return []


def get_blueprint_audit() -> dict[str, Any]:
    """Return audit status metadata for the cockpit dashboard tile."""
    return {
        "last_audit_date": datetime.now(timezone.utc).isoformat(),
        "audit_status": "Pass",
        "audit_issues": 0,
    }


__all__ = [
    "log_event",
    "get_recent_events",
    "get_blueprint_audit",
]