# =============================================================================
# FILE: app/models/banking/tradeline.py
# DESCRIPTION: Tradeline model aligned with UUID User.id, cascade semantics,
#              and cockpit‑grade relationship clarity.
# =============================================================================

from ..extensions import db


class Tradeline(db.Model):
    __tablename__ = "tradelines"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    vendor_name = db.Column(db.String(100), nullable=False)
    tradeline_type = db.Column(db.String(50))
    credit_limit = db.Column(db.Integer)
    annual_fee = db.Column(db.Float)
    reports_to = db.Column(db.String(255))
    terms_url = db.Column(db.String(255))
    status = db.Column(db.String(20))

    # UUID FK — must match User.id (String(36))
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship back to User
    user = db.relationship("User", back_populates="tradelines")

    def __repr__(self):
        return f"<Tradeline id={self.id} user_id={self.user_id} vendor='{self.vendor_name}'>"
