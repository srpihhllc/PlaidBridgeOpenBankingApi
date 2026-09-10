# app/models/lender_risk.py

from datetime import datetime, timezone

from app.extensions import db


class LenderRisk(db.Model):
    __tablename__ = "lender_risk"

    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(
        db.Integer,
        db.ForeignKey("lenders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Core risk metrics
    risk_score = db.Column(db.Float, default=0.0)
    fraud_index = db.Column(db.Float, default=0.0)
    liquidity_exposure = db.Column(db.Float, default=0.0)
    underwriting_quality = db.Column(db.Float, default=0.0)

    # Metadata
    last_evaluated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    lender = db.relationship("Lender", back_populates="risk_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "lender_id": self.lender_id,
            "risk_score": self.risk_score,
            "fraud_index": self.fraud_index,
            "liquidity_exposure": self.liquidity_exposure,
            "underwriting_quality": self.underwriting_quality,
            "last_evaluated_at": (
                self.last_evaluated_at.isoformat()
                if self.last_evaluated_at
                else None
            ),
        }
