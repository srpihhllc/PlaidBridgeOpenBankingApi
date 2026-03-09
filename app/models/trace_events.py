# =============================================================================
# FILE: app/models/trace_events.py
# DESCRIPTION: Records application-level trace events such as restarts,
#              login attempts, boot diagnostics, and operator-visible failures.
#              Supports nullable user_id for pre-login and anonymous events.
# =============================================================================

from datetime import datetime

from ..extensions import db


class TraceEvent(db.Model):
    """
    A model to record application events, such as restarts, login attempts,
    or critical failures. Supports both authenticated and anonymous events.
    """

    __tablename__ = "trace_events"

    id = db.Column(db.Integer, primary_key=True)

    event_id = db.Column(db.String(128), unique=True, nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Nullable FK — some events occur before login or without a user context
    # ✔ Updated to match User.id (String(36))
    # ✔ Changed to ondelete="CASCADE" for consistency (events deleted with user)
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email = db.Column(db.String(120))
    ip = db.Column(db.String(45))
    meta = db.Column(db.Text)  # JSON string for metadata inspection
    detail = db.Column(db.Text)  # Human-readable summary

    # Reverse relationship to User
    user = db.relationship("User", back_populates="trace_events")

    def __repr__(self):
        return f"<TraceEvent {self.event_type} @ {self.timestamp}>"