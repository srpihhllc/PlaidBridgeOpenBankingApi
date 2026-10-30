# =============================================================================
# FILE: app/models/registry.py
# DESCRIPTION: Centralized registry model for user configurations.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class Registry(db.Model):
    """A central registry for user configurations and related data."""

    __tablename__ = "registries"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name = db.Column(db.String(128), nullable=False, unique=True)
    config_blob = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "registry_events",
            lazy="dynamic",
            passive_deletes=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<Registry {self.name}>"

    def trace_status(self) -> dict[str, str]:
        created_at = self.created_at
        return {
            "name": self.name,
            "created_at": created_at.isoformat() if created_at else "",
            "config_summary": "loaded" if self.config_blob else "empty",
        }

    def ping(self) -> str:
        return f"Registry {self.name} is operational"