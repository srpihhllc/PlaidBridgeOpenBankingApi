# =============================================================================
# FILE: app/models/user.py
# DESCRIPTION: User model with explicit role system, fintech relationships,
#              MFA, audit fields, computed metrics, Todo, and Transaction integration.
# =============================================================================

import json
import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db

Model: type[DeclarativeBase] = db.Model  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Utility Generators
# ---------------------------------------------------------------------------


def _generate_uuid_string() -> str:
    return str(uuid.uuid4())


def _generate_secure_fallback_hash() -> str:
    return generate_password_hash(uuid.uuid4().hex)


def _get_naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# User Model
# ---------------------------------------------------------------------------


class User(UserMixin, Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    # -----------------------------------------------------------------------
    # Core Identity
    # -----------------------------------------------------------------------
    id = db.Column(
        db.String(36), primary_key=True, default=_generate_uuid_string
    )
    uuid = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
        default=_generate_uuid_string,
    )

    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(
        db.String(256), nullable=False, default=_generate_secure_fallback_hash
    )

    role = db.Column(db.String(64))
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)

    # -----------------------------------------------------------------------
    # Auth & MFA
    # -----------------------------------------------------------------------
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    is_mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(64))
    has_mfa = db.Column(db.Boolean, default=False, nullable=False)
    mfa_enabled = db.Column(
        db.Boolean, default=False, nullable=False, index=True
    )
    mfa_pending_setup = db.Column(
        db.Boolean, default=False, nullable=False, index=True
    )
    totp_secret = db.Column(db.String(64), index=True)

    mfa_failures = db.Column(db.Integer, default=0, nullable=False)

    # -----------------------------------------------------------------------
    # Audit Timestamps
    # -----------------------------------------------------------------------
    created_at = db.Column(
        db.DateTime,
        default=_get_naive_utc_now,
        server_default=db.text("CURRENT_TIMESTAMP"),
        nullable=False,
        index=True,
    )
    updated_at = db.Column(
        db.DateTime,
        default=_get_naive_utc_now,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=_get_naive_utc_now,
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # Extended Profile
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # Compliance
    # -----------------------------------------------------------------------
    is_locked = db.Column(db.Boolean, default=False, index=True)
    lock_reason = db.Column(db.String(255))
    violation_count = db.Column(db.Integer, default=0)

    # -----------------------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------------------
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
        "Lender", back_populates="user", lazy="dynamic", passive_deletes=True
    )
    underwriter_profiles = db.relationship(
        "UnderwriterAgent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -----------------------------------------------------------------------
    # Core Financial Transactions
    # -----------------------------------------------------------------------
    transactions = db.relationship(
        "Transaction",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # -----------------------------------------------------------------------
    # Ledger Entries
    # -----------------------------------------------------------------------
    ledger_entries = db.relationship(
        "LedgerEntry",
        back_populates="borrower",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -----------------------------------------------------------------------
    # Audit Logs / Events
    # -----------------------------------------------------------------------
    audit_events = db.relationship(
        "SchemaEvent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
        overlaps="schema_events",  # Silences SAWarning conflict with backref/schema_events
    )

    # -----------------------------------------------------------------------
    # Trace Events
    # -----------------------------------------------------------------------
    trace_events = db.relationship(
        "TraceEvent",
        back_populates="user",
        lazy="dynamic",
        passive_deletes=True,
    )

    # -----------------------------------------------------------------------
    # Todo Items
    # -----------------------------------------------------------------------
    todos = db.relationship(
        "Todo",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # -----------------------------------------------------------------------
    # Computed Metrics
    # -----------------------------------------------------------------------
    @property
    def total_balance(self) -> float:
        """
        Dynamically calculate the total balance across all linked bank accounts.
        Gracefully defaults to 0.0 if an anomaly occurs during summation.
        """
        try:
            return sum(
                account.balance
                for account in self.bank_accounts
                if account.balance is not None
            )
        except Exception:
            return 0.0

    # -----------------------------------------------------------------------
    # Password Hashing
    # -----------------------------------------------------------------------
    def set_password(self, password: str) -> None:
        """
        Hash the provided plaintext password and save it to the database.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verify a plaintext password against the stored password hash.
        """
        return check_password_hash(self.password_hash, password)

    # -----------------------------------------------------------------------
    # OAuth Resolver
    # -----------------------------------------------------------------------
    @classmethod
    def get_or_create_from_oauth(cls, provider, token_response):
        """
        Resolve or create a User from an OAuth provider + token response.
        Emits two TraceEvents: OAUTH_LOGIN_SUCCESS and SESSION_ESTABLISHED.
        """
        from app.extensions import db
        from app.models.trace_events import TraceEvent
        from app.oauth.provider import OAuthProvider

        oauth_client = OAuthProvider(provider)
        profile = oauth_client.fetch_profile(token_response)

        email = profile.get("email")
        sub = profile.get("sub")
        name = profile.get("name") or (email.split("@")[0] if email else None)

        if not email:
            raise ValueError("OAuth profile missing email")

        user = cls.query.filter_by(email=email).first()
        if user is None:
            user = cls(email=email, username=name)
            db.session.add(user)
            db.session.commit()

        def _emit(event_type: str, meta: dict):
            ev = TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user.id,
                email=user.email,
                meta=json.dumps(meta),
                detail=meta.get("detail"),
            )
            db.session.add(ev)

        _emit("OAUTH_LOGIN_SUCCESS", {"provider": provider.value, "sub": sub})
        _emit("SESSION_ESTABLISHED", {"provider": provider.value, "sub": sub})

        db.session.commit()
        return user
