# =============================================================================
# FILE: app/models/registry.py
# DESCRIPTION: Centralized registry model for user configurations.
# =============================================================================

from datetime import datetime

from ..extensions import db


class Registry(db.Model):
    """
    Represents a central registry for all users and their data within the system.
    This model acts as a core reference point, holding key user attributes.
    """

    __tablename__ = "registries"

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name = db.Column(db.String(128), nullable=False, unique=True)
    config_blob = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✔ Reverse relationship to User
    user = db.relationship("User", back_populates="registry_events")

    def __repr__(self):
        return f"<Registry {self.name}>"

    def trace_status(self):
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "config_summary": "loaded" if self.config_blob else "empty",
        }

    def ping(self):
        return f"Registry {self.name} is operational"
