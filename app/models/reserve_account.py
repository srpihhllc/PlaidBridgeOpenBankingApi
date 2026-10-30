# =============================================================================
# FILE: app/models/reserve_account.py
# DESCRIPTION:
#     Production-grade reserve, clearing, FBO, and treasury account model.
#
# PURPOSE:
#     Represents actual banking reserve accounts used to back
#     customer balances, settlement batches, payment rails,
#     treasury operations, and sponsor-bank integrations.
#
# DESIGN GOALS:
#     - SQLAlchemy persistence
#     - Treasury-safe
#     - Audit-ready
#     - Reconciliation-ready
#     - Sponsor-bank ready
#     - ACH/FedNow/RTP compatible
#     - Future FBO support
#
# IMPORTANT:
#     This model DOES NOT maintain customer balances.
#
#     Customer balances belong in:
#         CustomerWallet
#
#     Ledger truth belongs in:
#         JournalEntry
#
#     This model represents reserve-side banking accounts.
# =============================================================================

from __future__ import annotations

from uuid import uuid4

from app.extensions import db


class ReserveAccountType:
    RESERVE = "reserve"
    CLEARING = "clearing"
    SETTLEMENT = "settlement"
    FBO = "fbo"
    TREASURY = "treasury"


class ReserveAccountStatus:
    ACTIVE = "active"
    FROZEN = "frozen"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class ReserveAccount(db.Model):
    __tablename__ = "reserve_accounts"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
    )

    reserve_uuid = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        default=lambda: str(uuid4()),
    )

    account_name = db.Column(
        db.String(128),
        nullable=False,
        index=True,
    )

    account_number = db.Column(
        db.String(128),
        nullable=True,
    )

    routing_number = db.Column(
        db.String(32),
        nullable=True,
    )

    institution_name = db.Column(
        db.String(128),
        nullable=True,
        index=True,
    )

    account_type = db.Column(
        db.String(32),
        nullable=False,
        index=True,
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default=ReserveAccountStatus.ACTIVE,
        index=True,
    )

    currency = db.Column(
        db.String(8),
        nullable=False,
        default="USD",
    )

    external_reference = db.Column(
        db.String(128),
        nullable=True,
        unique=True,
    )

    sponsor_bank_reference = db.Column(
        db.String(128),
        nullable=True,
        index=True,
    )

    gl_account_id = db.Column(
        db.BigInteger,
        db.ForeignKey("gl_accounts.id"),
        nullable=True,
        index=True,
    )

    available_balance = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    ledger_balance = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    pending_debit_amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    pending_credit_amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    last_reconciled_at = db.Column(
        db.DateTime,
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

    notes = db.Column(
        db.Text,
        nullable=True,
    )

    gl_account = db.relationship(
        "GLAccount",
        lazy="joined",
    )

    def is_active(self) -> bool:
        return (
            self.status
            == ReserveAccountStatus.ACTIVE
        )

    def freeze(self) -> None:
        self.status = ReserveAccountStatus.FROZEN

    def suspend(self) -> None:
        self.status = ReserveAccountStatus.SUSPENDED

    def close(self) -> None:
        self.status = ReserveAccountStatus.CLOSED

    @property
    def net_pending(self):
        return (
            self.pending_credit_amount
            - self.pending_debit_amount
        )

    def __repr__(self):
        return (
            f"<ReserveAccount "
            f"uuid={self.reserve_uuid} "
            f"type={self.account_type} "
            f"status={self.status}>"
        )