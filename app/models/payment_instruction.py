# =============================================================================
# FILE: app/models/payment_instruction.py
# DESCRIPTION:
#     Production-grade payment instruction model.
#
# PURPOSE:
#     Represents a customer-initiated payment request before settlement.
#
# DESIGN:
#     - SQLAlchemy persistence
#     - Idempotency support
#     - Audit timestamps
#     - Concurrency safe
#     - Settlement-ready
# =============================================================================

from __future__ import annotations

from uuid import uuid4

from app.extensions import db


class PaymentStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    SETTLED = "settled"
    FAILED = "failed"
    REVERSED = "reversed"


class PaymentType:
    INTERNAL = "internal"
    ACH = "ach"
    FEDNOW = "fednow"
    RTP = "rtp"
    CARD = "card"


class PaymentInstruction(db.Model):
    __tablename__ = "payment_instructions"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
    )

    payment_uuid = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4()),
    )

    idempotency_key = db.Column(
        db.String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    payment_type = db.Column(
        db.String(32),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )

    debit_wallet_id = db.Column(
        db.BigInteger,
        nullable=False,
        index=True,
    )

    credit_wallet_id = db.Column(
        db.BigInteger,
        nullable=False,
        index=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    currency = db.Column(
        db.String(8),
        nullable=False,
        default="USD",
    )

    memo = db.Column(
        db.String(512),
        nullable=True,
    )

    posted_by = db.Column(
        db.BigInteger,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    settled_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    def mark_processing(self):
        self.status = PaymentStatus.PROCESSING

    def mark_settled(self):
        self.status = PaymentStatus.SETTLED

    def mark_failed(self):
        self.status = PaymentStatus.FAILED

    def mark_reversed(self):
        self.status = PaymentStatus.REVERSED

    def __repr__(self):
        return (
            f"<PaymentInstruction "
            f"uuid={self.payment_uuid} "
            f"status={self.status}>"
        )