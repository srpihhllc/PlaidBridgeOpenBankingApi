# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/customer_wallet.py

from decimal import Decimal
from uuid import uuid4

from app.extensions import db


class CustomerWallet(db.Model):
    """
    Customer wallet record.

    SQLite-compatible primary key generation is used so that
    pytest/test databases can create wallet records without
    explicitly supplying an id.

    wallet_uuid is automatically generated when not provided.
    """

    __tablename__ = "customer_wallets"

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )

    wallet_uuid = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4()),
    )

    balance = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    is_frozen = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default="active",
        server_default="active",
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<CustomerWallet "
            f"id={self.id} "
            f"user_id={self.user_id} "
            f"balance={self.balance} "
            f"wallet_uuid={self.wallet_uuid}>"
        )