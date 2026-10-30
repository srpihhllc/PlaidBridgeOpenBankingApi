# =============================================================================
# FILE: app/models/subscriber_profile.py
# DESCRIPTION: Normalized models for subscriptions and subscriber profiles.
#              Identity and financial data live in the User model to keep a
#              single source of truth.
# =============================================================================

import secrets
from datetime import datetime, timezone

from ..extensions import db


class Subscription(db.Model):
    """A subscription instance linked to a subscriber profile."""

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default="active", nullable=False)

    subscriber_profile_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "subscriber_profile.id",
            name="fk_subscriptions_subscriber_profile",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    subscriber_profile = db.relationship(
        "SubscriberProfile",
        back_populates="subscriptions",
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} status={self.status}>"


class SubscriberProfile(db.Model):
    """Subscriber-specific functionality linked to the core User model."""

    __tablename__ = "subscriber_profile"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "users.id",
            name="fk_subscriber_profile_user",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    api_key = db.Column(db.String(64), unique=True, nullable=True)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "subscriber_profile",
            uselist=False,
            passive_deletes=True,
        ),
    )

    subscriptions = db.relationship(
        "Subscription",
        back_populates="subscriber_profile",
        lazy="dynamic",
        passive_deletes=True,
    )

    def set_password(self, password: str) -> None:
        """Proxy password setting to the linked User."""
        if self.user:
            self.user.set_password(password)

    def check_password(self, password: str) -> bool:
        """Proxy password verification to the linked User."""
        if not self.user:
            return False
        return bool(self.user.check_password(password))

    def generate_api_key(self) -> None:
        """Generate a new secure hexadecimal API key."""
        self.api_key = secrets.token_hex(32)

    @property
    def is_verified(self) -> bool:
        """Whether the linked User has provided the required identity details."""
        user = self.user
        if not user:
            return False
        return bool(
            user.ssn_last4
            and user.routing_number
            and user.account_ending
        )

    @property
    def identity_tip(self) -> str:
        """Return a masked identity string based on the linked User."""
        user = self.user
        if not user:
            return "No User Linked"

        ssn_last4 = user.ssn_last4 or "----"
        account_ending = user.account_ending or "----"
        return (
            f"{user.username} • SSN●●●{ssn_last4} "
            f"• ACCT●●●{account_ending}"
        )

    def __repr__(self) -> str:
        return f"<SubscriberProfile id={self.id} user_id={self.user_id}>"