# =============================================================================
# FILE: app/models/schema_event.py
# DESCRIPTION: Records schema‑level events tied to a specific user, such as
#              migrations applied, auto‑repairs, or operator‑initiated changes.
#              Updated to use dynamic backref to prevent KeyError on User mapper.
# =============================================================================

from datetime import datetime

from ..extensions import db


class SchemaEvent(db.Model):
    """
    Records schema-level events tied to a specific user, such as
    migrations applied, auto-repairs, or operator-initiated changes.
    """

    __tablename__ = "schema_event"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type = db.Column(db.String(64), nullable=False)  # e.g. 'REVISION_APPLIED'
    detail = db.Column(db.Text, nullable=True)  # JSON string, freeform notes
    origin = db.Column(db.String(64), nullable=True)  # e.g. 'auto', 'manual', 'cli'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------

    # ⭐ User Fix: Swapped back_populates to dynamic backref since User lacks 'schema_events'
    user = db.relationship(
        "User",
        backref=db.backref("schema_events", lazy="dynamic", passive_deletes=True),
    )

    def __repr__(self):
        return f"<SchemaEvent id={self.id} user_id={self.user_id} type={self.event_type}>"