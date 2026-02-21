#  /home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/lender.py

from datetime import datetime

from app.extensions import db


class Lender(db.Model):
    __tablename__ = "lenders"

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    business_name = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    ssn_or_ein = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(150), nullable=False)
    institution_name = db.Column(db.String(100))
    verification_status = db.Column(db.String(20), default="pending")
    verification_score = db.Column(db.Integer, default=0)
    bank_linked = db.Column(db.Boolean, default=False)
    linked_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="lender_profiles")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "business_name": self.business_name,
            "owner_name": self.owner_name,
            "ssn_or_ein": self.ssn_or_ein,
            "license_number": self.license_number,
            "address": self.address,
            "institution_name": self.institution_name,
            "verification_status": self.verification_status,
            "verification_score": self.verification_score,
            "bank_linked": self.bank_linked,
            "linked_at": self.linked_at.isoformat() if self.linked_at else None,
            "created_at": self.created_at.isoformat(),
        }
