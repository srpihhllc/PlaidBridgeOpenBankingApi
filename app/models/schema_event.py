# =============================================================================
# FILE: app/models/schema_event.py
# DESCRIPTION: Records schema‑level events tied to a specific user, such as
#              migrations applied, auto‑repairs, or operator‑initiated changes.
# =============================================================================

import datetime

from app.extensions import db


class SchemaEvent(db.Model):
    __tablename__ = "schema_event"

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
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # ✔ Reverse relationship to User
    user = db.relationship("User", back_populates="schema_events")

    def __repr__(self):
        return f"<SchemaEvent id={self.id} user_id={self.user_id} type={self.event_type}>"
