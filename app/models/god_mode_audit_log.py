# =============================================================================
# FILE: app/models/god_mode_audit_log.py
# DESCRIPTION:
#     - Immutable append-only forensic audit log model for all treasury-grade
#       and high-risk operator actions.
# =============================================================================

from datetime import datetime, timezone
from typing import Any, Dict

from app.extensions import db


class GodModeAuditLog(db.Model):
    __tablename__ = "god_mode_audit_logs"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user_id = db.Column(
        db.BigInteger,
        nullable=False,
        index=True,
    )

    action = db.Column(
        db.String(128),
        nullable=False,
        index=True,
    )

    endpoint = db.Column(
        db.String(255),
        nullable=False,
    )

    ip_address = db.Column(
        db.String(64),
        nullable=True,
    )

    request_id = db.Column(
        db.String(128),
        nullable=True,
    )

    metadata_json = db.Column(
        db.JSON,
        nullable=True,
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the audit record for administrative compliance inspection."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "user_id": self.user_id,
            "action": self.action,
            "endpoint": self.endpoint,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "metadata": self.metadata_json or {},
        }
