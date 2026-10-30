# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/god_mode_audit_service.py

from typing import Any, Dict, List, Optional

from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models.god_mode_audit_log import GodModeAuditLog


class GodModeAuditService:
    """Record and query audit entries for elevated operator actions."""

    @staticmethod
    def log(
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GodModeAuditLog:
        user_id = getattr(current_user, "id", None)
        if not user_id:
            user_id = 0

        record = GodModeAuditLog(
            user_id=user_id,
            action=action,
            endpoint=request.path if has_request_context() else "unknown",
            ip_address=request.remote_addr if has_request_context() else None,
            metadata_json=metadata or {},
        )

        db.session.add(record)
        db.session.commit()
        return record

    @staticmethod
    def query_logs(
        action: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = GodModeAuditLog.query

        if action:
            query = query.filter_by(action=action)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)

        records = (
            query.order_by(
                GodModeAuditLog.created_at.desc(),
                GodModeAuditLog.id.desc(),
            )
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [record.to_dict() for record in records]
