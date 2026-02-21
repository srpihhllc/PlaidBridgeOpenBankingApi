# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/bank_institution.py

from app.extensions import db


class BankInstitution(db.Model):
    __tablename__ = "bank_institutions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must be String(36) to match User.id
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name = db.Column(db.String(128), nullable=False)
    institution_id = db.Column(db.String(128), unique=True, nullable=False)

    # ✔ Relationship stays the same
    user = db.relationship("User", back_populates="bank_institutions")
