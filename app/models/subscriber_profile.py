# =============================================================================
# FILE: app/models/subscriptions_and_profiles.py
# DESCRIPTION: Normalized Models for Subscription and SubscriberProfile.
#              Identity and financial data live in the User model to ensure
#              a single source of truth and prevent database discrepancies.
# =============================================================================

import secrets
from datetime import datetime

from ..extensions import db


class Subscription(db.Model):
    """
    Represents a subscription instance linked to a subscriber profile.
    """

    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default="active", nullable=False)

    # ✔ Must match SubscriberProfile.id (Integer)
    # ✔ Add ondelete="CASCADE" so deleting a profile deletes its subscriptions
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Subscription id={self.id} status={self.status}>"


class SubscriberProfile(db.Model):
    """
    A lightweight extension of the User model for Subscriber-specific logic.
    Core data (SSN, Bank Details, Password) is managed by the User model.
    """

    __tablename__ = "subscriber_profile"

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "users.id",
            name="fk_subscriber_profile_user",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,  # One-to-One enforcement
    )

    api_key = db.Column(db.String(64), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User", back_populates="subscriber_profile")

    subscriptions = db.relationship(
        "Subscription",
        back_populates="subscriber_profile",
        lazy="dynamic",
        passive_deletes=True,  # ✔ ensures SQLAlchemy does NOT NULL the FK
    )

    # -------------------------------------------------------------------------
    # Proxy Methods (Referencing the User Model)
    # -------------------------------------------------------------------------
    def set_password(self, password: str) -> None:
        """Proxies password setting to the core User model."""
        if self.user:
            self.user.set_password(password)

    def check_password(self, password: str) -> bool:
        """Proxies password verification to the core User model."""
        return self.user.check_password(password) if self.user else False

    def generate_api_key(self) -> None:
        """Generates a new secure hex API key."""
        self.api_key = secrets.token_hex(32)

    # -------------------------------------------------------------------------
    # Computed Properties (Single Source of Truth)
    # -------------------------------------------------------------------------
    @property
    def is_verified(self) -> bool:
        """Returns True if user has provided required identity details in User model."""
        u = self.user
        if not u:
            return False
        return bool(u.ssn_last4 and u.routing_number and u.account_ending)

    @property
    def identity_tip(self) -> str:
        """Returns a masked identity string using data from the User model."""
        u = self.user
        if not u:
            return "No User Linked"
        return f"{u.username} • SSN●●●{u.ssn_last4 or '----'} • ACCT●●●{u.account_ending or '----'}"

    def __repr__(self) -> str:
        return f"<SubscriberProfile id={self.id} user_id={self.user_id}>"
