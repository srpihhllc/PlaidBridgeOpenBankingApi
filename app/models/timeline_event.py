# =============================================================================
# FILE: app/models/timeline_event.py
# DESCRIPTION: User‑scoped timeline analytics events with UUID user linkage
#              and proper cascade semantics.
#              Updated to use 'event_type' to align with telemetry and routes.
# =============================================================================

from datetime import datetime
from ..extensions import db

class TimelineEvent(db.Model):
    __tablename__ = "timeline_events"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Aligned with app-wide naming convention found in auth_routes and telemetry
    event_type = db.Column(db.String(255), nullable=False)
    value = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # ✔ Relationship back to User
    user = db.relationship("User", back_populates="timeline_events")

    def __repr__(self):
        return f"<TimelineEvent id={self.id} user_id={self.user_id} event_type='{self.event_type}'>"