"""Loan applications, consent, and lender-scoped financial snapshots."""

from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


class LoanApplication(db.Model):
    __tablename__ = "loan_applications"

    id = db.Column(db.Integer, primary_key=True)

    # Both parties are Users. The lender must be the logged-in lender
    # before the application or its snapshots can be accessed.
    lender_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscriber_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Keep loan terms explicit; don't put identity or bank credentials here.
    requested_amount = db.Column(db.Numeric(12, 2), nullable=True)
    purpose = db.Column(db.String(255), nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    # Set only after the subscriber explicitly approves sharing with this lender.
    subscriber_consent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    access_revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    snapshots = db.relationship(
        "FinancialSnapshot",
        back_populates="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="FinancialSnapshot.created_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<LoanApplication id={self.id} lender_id={self.lender_id!r} "
            f"subscriber_id={self.subscriber_id!r} status={self.status!r}>"
        )


class FinancialSnapshot(db.Model):
    __tablename__ = "financial_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscriber_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Store only a deliberately prepared, minimal loan-review summary.
    # Never store credentials, full account numbers, or unrestricted dashboard data.
    loan_review_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    application = db.relationship(
        "LoanApplication",
        back_populates="snapshots",
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialSnapshot id={self.id} "
            f"application_id={self.application_id}>"
        )