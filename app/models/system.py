# =============================================================================
# FILE: app/models/system.py
# DESCRIPTION: System-level models including rate limiting, schema versioning,
#              and boot logs. SystemVersion is tied to a specific User and must
#              align with UUID primary keys and cascade semantics.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class RateLimit(db.Model):
    __tablename__ = "rate_limits"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), unique=True, nullable=False)
    requests = db.Column(db.Integer, default=0)
    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class SystemVersion(db.Model):
    __tablename__ = "system_versions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Must match User.id (String(36)) and cascade when the user is deleted.
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    version_hash = db.Column(db.String(40), nullable=False)
    applied_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "system_events",
            lazy="dynamic",
            passive_deletes=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SystemVersion id={self.id} user_id={self.user_id} "
            f"hash={self.version_hash}>"
        )


class SystemBootLog(db.Model):
    __tablename__ = "system_boot_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer)
    sequence_origin = db.Column(db.String(255))
    ignition_timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    message = db.Column(db.Text)

    def __repr__(self) -> str:
        return (
            f"<SystemBootLog id={self.id} operator_id={self.operator_id}>"
        )