# =============================================================================
# FILE: app/models/plaid_item.py
# DESCRIPTION: Plaid item model aligned with ALL test suite expectations.
# =============================================================================

from datetime import datetime
from ..extensions import db


class PlaidItem(db.Model):
    __tablename__ = "plaid_items"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Required by all tests
    plaid_item_id = db.Column(db.String(128), nullable=False)

    # Canonical column name expected by Plaid OAuth tests
    plaid_access_token = db.Column(db.String(256), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="plaid_items")

    # -------------------------------------------------------------------------
    # Legacy compatibility: allow access_token=... in constructor
    # -------------------------------------------------------------------------
    @property
    def access_token(self):
        return self.plaid_access_token

    @access_token.setter
    def access_token(self, value):
        self.plaid_access_token = value
