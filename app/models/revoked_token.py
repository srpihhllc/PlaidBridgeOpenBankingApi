# =============================================================================
# FILE: app/models/revoked_token.py
# DESCRIPTION: SQLAlchemy model for storing revoked JWTs (JSON Token ID - jti).
#              Used by Flask-JWT-Extended's token_in_blocklist_loader.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..extensions import db

Model: Any = db.Model


class RevokedToken(Model):
    """
    Model to store the JTI of revoked tokens (refresh or access) for blocklisting.
    Provides an audit trail by linking each revoked token to a user.
    """

    __tablename__ = "revoked_tokens"

    id = db.Column(db.Integer, primary_key=True)

    # Unique JWT ID (jti)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to User
    user = db.relationship(
        "User",
        backref=db.backref(
            "revoked_tokens",
            lazy="dynamic",
            cascade="all, delete-orphan",
            passive_deletes=True,  # ✔ required to prevent NULL-updates
        ),
    )

    @classmethod
    def is_jti_blocklisted(cls, jti: str) -> bool:
        return cls.query.filter_by(jti=jti).first() is not None

    def __repr__(self) -> str:
        return f"<RevokedToken jti='{self.jti}' user_id={self.user_id}>"