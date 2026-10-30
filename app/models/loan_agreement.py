# =============================================================================
# FILE: app/models/loan_agreement.py
# DESCRIPTION: LoanAgreement model representing the legal and financial bond
#              between two users.
# =============================================================================

from datetime import datetime, timezone

from ..extensions import db


class LoanAgreement(db.Model):
    __tablename__ = "loan_agreement"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    lender_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    borrower_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    terms = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")
    ai_flagged = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    violation_count = db.Column(db.Integer, default=0)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    borrower = db.relationship(
        "User",
        foreign_keys=[borrower_id],
        backref=db.backref(
            "borrowed_loan_agreements",
            lazy="dynamic",
            passive_deletes=True,
        ),
        lazy="joined",
    )
    lender = db.relationship(
        "User",
        foreign_keys=[lender_id],
        backref=db.backref(
            "lent_loan_agreements",
            lazy="dynamic",
            passive_deletes=True,
        ),
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<LoanAgreement id={self.id} status='{self.status}' "
            f"borrower_id='{self.borrower_id}'>"
        )