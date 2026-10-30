# =============================================================================
# FILE: app/models/timeline_event.py
# DESCRIPTION: User-scoped timeline analytics events with UUID user linkage
#              and proper cascade semantics.
#              Uses 'event_type' to align with telemetry and routes.
# =============================================================================

from datetime import datetime, timezone
from typing import Any

from ..extensions import db

# Flask-SQLAlchemy's dynamically provided Model may not be visible to mypy.
Model: Any = db.Model


def _get_naive_utc_now() -> datetime:
    """Return a naive datetime object representing current UTC time."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimelineEvent(Model):
    __tablename__ = "timeline_events"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Must match User.id (String(36)) and use database-level cascade deletion.
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Aligned with app-wide naming in authentication routes and telemetry.
    event_type = db.Column(db.String(255), nullable=False)
    value = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=_get_naive_utc_now)

    # passive_deletes lets the database cascade deletes without SQLAlchemy
    # attempting to set user_id to NULL first.
    user = db.relationship(
        "User",
        backref=db.backref(
            "timeline_events",
            lazy="dynamic",
            passive_deletes=True,
        ),
        lazy=True,
    )

    def __repr__(self) -> str:
        return (
            f"<TimelineEvent id={self.id} user_id={self.user_id} "
            f"event_type='{self.event_type}'>"
        )