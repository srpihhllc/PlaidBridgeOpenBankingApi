# =============================================================================
# FILE: app/models/underwriter.py
# DESCRIPTION: Underwriter agent profiles linked to a User. Supports specialty,
#              status, and cockpit‑grade auditability. UUID FK + cascade‑safe.
# =============================================================================

from datetime import datetime

from ..extensions import db


class UnderwriterAgent(db.Model):
    __tablename__ = "underwriter_agents"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK to users.id
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Core fields
    name = db.Column(db.String(255), nullable=False)
    specialty = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default="active", nullable=False)

    # Audit timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to User
    user = db.relationship("User", back_populates="underwriter_profiles")

    def __repr__(self):
        return (
            f"<UnderwriterAgent id={self.id} user_id={self.user_id} "
            f"name='{self.name}' specialty='{self.specialty}'>"
        )
