# =============================================================================
# FILE: app/models/ledger.py
# DESCRIPTION:
#     Ledger entry persistence model.
#
# RESPONSIBILITIES:
#     - borrower transaction history
#     - reconciliation tracking
#     - audit persistence
#
# NEVER:
#     - accounting calculations
#     - double-entry posting
#     - balance ownership
#
# SOURCE OF TRUTH:
#     app/services/ledger_engine.py
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models.vault_transaction import VaultTransaction

# Import anchor for relationship visibility
_ = VaultTransaction.__tablename__


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        db.Index(
            "ix_ledger_entries_borrower_reconciled",
            "borrower_id",
            "reconciled",
        ),
        {"extend_existing": True},
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    borrower_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    card_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "borrower_cards.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    method = db.Column(
        db.String(64),
        nullable=True,
    )

    received_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    reconciled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    borrower = db.relationship(
        "User",
        back_populates="ledger_entries",
        foreign_keys=[borrower_id],
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerEntry "
            f"id={self.id} "
            f"borrower_id={self.borrower_id} "
            f"amount={self.amount} "
            f"reconciled={self.reconciled}>"
        )