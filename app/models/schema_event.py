# =============================================================================
# FILE: app/models/schema_event.py
# DESCRIPTION: Records schema-level events tied to a specific user, such as
#              migrations, auto-repairs, or operator-initiated changes.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class SchemaEvent(db.Model):
    """A schema-level event associated with a user."""

    __tablename__ = "schema_event"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type = db.Column(db.String(64), nullable=False)
    detail = db.Column(db.Text, nullable=True)
    origin = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "schema_events",
            lazy="dynamic",
            passive_deletes=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SchemaEvent id={self.id} user_id={self.user_id} "
            f"type={self.event_type}>"
        )