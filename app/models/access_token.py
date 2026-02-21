# app/models/access_token.py

import uuid
from datetime import datetime

from app.extensions import db


class AccessToken(db.Model):
    """
    Represents an access token linked to a specific user.
    """

    __tablename__ = "access_tokens"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # FIX: user_id must match User.id (String UUID), not Integer
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Relationship back to User
    user = db.relationship("User", back_populates="access_tokens")

    def __repr__(self):
        return f"<AccessToken id='{self.id}' user_id='{self.user_id}'>"
