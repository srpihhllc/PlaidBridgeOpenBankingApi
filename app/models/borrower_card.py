# app/models/borrower_card.py

from datetime import datetime, timezone

from sqlalchemy.orm import synonym

from ..extensions import db


class BorrowerCard(db.Model):
    __tablename__ = "borrower_cards"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    card_number = db.Column(db.String(16), nullable=False, unique=True)
    expiration_date = db.Column(db.String(5), nullable=False)
    cvv = db.Column(db.String(3), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(10), nullable=False)
    issued_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_used_at = db.Column(db.DateTime)
    revoked = db.Column(db.Boolean, default=False)

    last_synced_at = db.Column(db.DateTime)
    trace_status = db.Column(db.String(32), default="active")

    user = db.relationship("User", back_populates="borrower_cards")

    # =============================================================================
    # ORM SYNONYM PROXY (Bridges user_id to borrower_id for queries & instances)
    # =============================================================================
    borrower_id = synonym("user_id")
