# =============================================================================
# FILE: app/models/plaid_item.py
# DESCRIPTION: Plaid item model aligned with the application test suite.
# =============================================================================

from datetime import datetime, timezone

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

    plaid_item_id = db.Column(db.String(128), nullable=False)
    plaid_access_token = db.Column(db.String(256), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship("User", back_populates="plaid_items")

    @property
    def access_token(self) -> str:
        """Legacy alias for plaid_access_token."""
        return str(self.plaid_access_token)

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.plaid_access_token = value