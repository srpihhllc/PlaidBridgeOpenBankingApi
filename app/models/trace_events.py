# =============================================================================
# FILE: app/models/trace_events.py
# DESCRIPTION: Records application-level trace events such as restarts,
#              login attempts, boot diagnostics, and operator-visible failures.
#              Supports nullable user_id for pre-login and anonymous events.
#              Adds a backwards-compatible `details` property that parses the
#              JSON `meta` column (used by tests).
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, Dict, Any

from app.extensions import db


class TraceEvent(db.Model):
    """
    A model to record application events, such as restarts, login attempts,
    or critical failures. Supports both authenticated and anonymous events.

    The `details` property provides a parsed dict view of the `meta` JSON
    payload for backwards-compatibility with tests that expect event.details.
    """

    __tablename__ = "trace_events"

    id: int = db.Column(db.Integer, primary_key=True)

    # External event UUID used for correlation
    event_id: str = db.Column(db.String(128), unique=True, nullable=False)
    event_type: str = db.Column(db.String(64), nullable=False)
    timestamp: datetime = db.Column(db.DateTime, default=datetime.utcnow)

    # Nullable FK — some events occur before login or without a user context
    # Matches User.id (String(36)); keep ondelete cascade for cleanup where supported
    user_id: Optional[str] = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email: Optional[str] = db.Column(db.String(120))
    ip: Optional[str] = db.Column(db.String(45))
    meta: Optional[str] = db.Column(db.Text)  # JSON string for metadata inspection
    detail: Optional[str] = db.Column(db.Text)  # Human-readable summary

    # Define relationship to User using a string target to avoid import-time cycles.
    # This matches User.trace_events back_populates and allows mappers to configure.
    user = db.relationship("User", back_populates="trace_events", foreign_keys=[user_id])  # type: ignore

    def __repr__(self) -> str:
        return f"<TraceEvent {self.event_type} event_id={self.event_id} user_id={self.user_id}>"

    @property
    def details(self) -> Dict[str, Any]:
        """
        Backwards-compatible accessor used by tests and callers who expect a dict.

        Returns:
            Parsed JSON object from the `meta` column, or an empty dict on missing/invalid JSON.
        """
        if not self.meta:
            return {}
        try:
            return json.loads(self.meta)
        except Exception:
            return {}