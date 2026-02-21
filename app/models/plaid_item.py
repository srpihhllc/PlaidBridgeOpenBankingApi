# app/models/plaid_item.py

from datetime import datetime

from app.extensions import db


class PlaidItem(db.Model):
    __tablename__ = "plaid_items"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    plaid_item_id = db.Column(db.String(128), nullable=False)
    access_token = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="plaid_items")
