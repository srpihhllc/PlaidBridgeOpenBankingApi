# =============================================================================
# FILE: app/models/settlement_batch.py
# DESCRIPTION:
#     Production-grade settlement batch model.
#
# PURPOSE:
#     Represents a settlement grouping used by ACH, FedNow,
#     RTP, card settlement, treasury reconciliation,
#     and internal ledger balancing.
#
# DESIGN GOALS:
#     - SQLAlchemy persistence
#     - Auditability
#     - Treasury-safe
#     - Reconciliation-ready
#     - Batch lifecycle management
#     - Operations visibility
#     - Regulatory reporting support
# =============================================================================

from __future__ import annotations

from uuid import uuid4

from app.extensions import db


class SettlementBatchStatus:
    CREATED = "created"
    OPEN = "open"
    PROCESSING = "processing"
    SETTLED = "settled"
    FAILED = "failed"
    REVERSED = "reversed"
    ARCHIVED = "archived"


class SettlementBatch(db.Model):
    __tablename__ = "settlement_batches"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
    )

    batch_uuid = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4()),
    )

    batch_reference = db.Column(
        db.String(128),
        unique=True,
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default=SettlementBatchStatus.CREATED,
        index=True,
    )

    payment_type = db.Column(
        db.String(32),
        nullable=False,
        index=True,
    )

    currency = db.Column(
        db.String(8),
        nullable=False,
        default="USD",
    )

    total_items = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    total_debit_amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    total_credit_amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    net_amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    settlement_window = db.Column(
        db.String(64),
        nullable=True,
    )

    reconciliation_reference = db.Column(
        db.String(128),
        nullable=True,
        index=True,
    )

    created_by = db.Column(
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

    processing_started_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    settled_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    archived_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    notes = db.Column(
        db.Text,
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # Lifecycle Helpers
    # -------------------------------------------------------------------------

    def mark_open(self) -> None:
        self.status = SettlementBatchStatus.OPEN

    def mark_processing(self) -> None:
        self.status = SettlementBatchStatus.PROCESSING

    def mark_settled(self) -> None:
        self.status = SettlementBatchStatus.SETTLED

    def mark_failed(self) -> None:
        self.status = SettlementBatchStatus.FAILED

    def mark_reversed(self) -> None:
        self.status = SettlementBatchStatus.REVERSED

    def mark_archived(self) -> None:
        self.status = SettlementBatchStatus.ARCHIVED

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    @property
    def is_balanced(self) -> bool:
        return (
            self.total_debit_amount
            == self.total_credit_amount
        )

    def __repr__(self):
        return (
            f"<SettlementBatch "
            f"uuid={self.batch_uuid} "
            f"status={self.status} "
            f"items={self.total_items}>"
        )