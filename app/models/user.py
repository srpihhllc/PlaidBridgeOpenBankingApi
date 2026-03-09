# =============================================================================
# FILE: app/models/user.py
# DESCRIPTION: User model with explicit role system, fintech relationships,
#              MFA, audit fields, and computed metrics.
# =============================================================================

import uuid
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db

Model: type[DeclarativeBase] = db.Model  # type: ignore[attr-defined]


class User(UserMixin, Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    # -------------------------------------------------------------------------
    # Core identity fields
    # -------------------------------------------------------------------------
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )

    uuid = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    username = db.Column(db.String(64), index=True, unique=True, nullable=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    role = db.Column(db.String(64), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)

    # -------------------------------------------------------------------------
    # Auth & MFA
    # -------------------------------------------------------------------------
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    is_mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(64), nullable=True)
    has_mfa = db.Column(db.Boolean, default=False, nullable=False)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False, index=True)
    mfa_pending_setup = db.Column(db.Boolean, default=False, nullable=False, index=True)
    totp_secret = db.Column(db.String(64), nullable=True, index=True)

    # -------------------------------------------------------------------------
    # Audit timestamps
    # -------------------------------------------------------------------------
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Extended profile fields
    # -------------------------------------------------------------------------
    ssn_last4 = db.Column(db.String(4))
    primary_phone = db.Column(db.String(20))
    bank_name = db.Column(db.String(128))
    routing_number = db.Column(db.String(20))
    account_ending = db.Column(db.String(8))
    business_address = db.Column(db.String(256))
    ein = db.Column(db.String(32))
    business_city = db.Column(db.String(128))
    business_state = db.Column(db.String(64))
    business_zip = db.Column(db.String(16))
    business_phone = db.Column(db.String(20))
    home_address = db.Column(db.String(256))
    home_same_as_business = db.Column(db.Boolean, default=True)

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    access_tokens = db.relationship(
        "AccessToken",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    plaid_items = db.relationship(
        "PlaidItem",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    bank_accounts = db.relationship(
        "BankAccount",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    bank_statements = db.relationship(
        "BankStatement",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    bank_institutions = db.relationship(
        "BankInstitution",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    tradelines = db.relationship(
        "Tradeline",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    vault_transactions = db.relationship(
        "VaultTransaction",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    borrower_cards = db.relationship(
        "BorrowerCard",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    lender_profiles = db.relationship(
        "Lender",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    underwriter_profiles = db.relationship(
        "UnderwriterAgent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    subscriber_profile = db.relationship(
        "SubscriberProfile",
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )

    user_dashboard = db.relationship(
        "UserDashboard",
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )

    credit_ledger_entries = db.relationship(
        "CreditLedger",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    payment_logs = db.relationship(
        "PaymentLog",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    complaint_logs = db.relationship(
        "ComplaintLog",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    dispute_logs = db.relationship(
        "DisputeLog",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    fraud_reports = db.relationship(
        "FraudReport",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    registry_events = db.relationship(
        "Registry",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    schema_events = db.relationship(
        "SchemaEvent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    system_events = db.relationship(
        "SystemVersion",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    trace_events = db.relationship(
        "TraceEvent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    transactions = db.relationship(
        "Transaction",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    mfa_codes = db.relationship(
        "MFACode",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    todos = db.relationship(
        "Todo",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    borrowed_loan_agreements = db.relationship(
        "LoanAgreement",
        back_populates="borrower",
        foreign_keys="[LoanAgreement.borrower_id]",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    lent_loan_agreements = db.relationship(
        "LoanAgreement",
        foreign_keys="LoanAgreement.lender_id",
        back_populates="lender",
        lazy="dynamic",
        passive_deletes=True,
    )

    ledger_entries = db.relationship(
        "LedgerEntry",
        back_populates="borrower",
        foreign_keys="[LedgerEntry.borrower_id]",
        lazy="dynamic",
        passive_deletes=True,
    )

    timeline_events = db.relationship(
        "TimelineEvent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -------------------------------------------------------------------------
    # AuditLog (User ↔ AuditLog)
    # -------------------------------------------------------------------------
    audit_events = db.relationship(
        "AuditLog",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -------------------------------------------------------------------------
    # Properties & Helpers
    # -------------------------------------------------------------------------
    @property
    def is_subscriber(self) -> bool:
        return not self.is_admin and not self.is_super_admin

    @property
    def is_operator(self) -> bool:
        return self.is_admin or self.is_super_admin

    @property
    def role_label(self) -> str:
        if self.is_super_admin:
            return "super_admin"
        if self.is_admin:
            return "admin"
        return "subscriber"

    @property
    def total_balance(self) -> float:
        try:
            return float(sum((acct.balance or 0.0) for acct in self.bank_accounts))
        except Exception:
            return 0.0

    @hybrid_property
    def is_recently_updated(self) -> bool:
        return (datetime.utcnow() - self.updated_at).days < 7

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' role='{self.role_label}'>"

    # -------------------------------------------------------------------------
    # Compliance & Audit
    # -------------------------------------------------------------------------
    is_locked = db.Column(db.Boolean, default=False, index=True)
    lock_reason = db.Column(db.String(255))
    violation_count = db.Column(db.Integer, default=0)

    audit_actions = db.relationship(
        "FinancialAuditLog",
        foreign_keys="FinancialAuditLog.actor_id",
        backref="actor",
        lazy="dynamic",
        passive_deletes=True,
    )


from .ledger import LedgerEntry  # noqa: F401,E402
