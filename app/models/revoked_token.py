# =============================================================================
# FILE: app/models/revoked_token.py
# DESCRIPTION: SQLAlchemy model for storing revoked JWTs (JSON Token ID - jti).
#              Used by Flask-JWT-Extended's token_in_blocklist_loader.
# =============================================================================

from datetime import datetime

from sqlalchemy.orm import DeclarativeBase

from ..extensions import db

# Mypy-safe alias: db.Model behaves like a SQLAlchemy declarative base
Model: type[DeclarativeBase] = db.Model  # type: ignore[attr-defined]


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

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
