# =============================================================================
# FILE: app/models/user.py
# DESCRIPTION: User model with explicit role system, fintech relationships,
#              MFA, audit fields, computed metrics, Todo, and Transaction integration.
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

from flask_login import UserMixin
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db

logger = logging.getLogger(__name__)
Model: Any = db.Model


# ---------------------------------------------------------------------------
# Utility Generators & Helpers
# ---------------------------------------------------------------------------


def _generate_uuid_string() -> str:
    return str(uuid.uuid4())


def _generate_secure_fallback_hash() -> str:
    return cast(str, generate_password_hash(uuid.uuid4().hex))


def _get_naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_username_candidate(raw_name: str | None, email: str) -> str:
    base_source = (raw_name or email.split("@", 1)[0] or "user").strip().lower()
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", base_source).strip("._-")
    if not cleaned:
        cleaned = "user"
    return cleaned[:48]


def _generate_unique_username(
    user_cls: type[User],
    raw_name: str | None,
    email: str,
) -> str:
    base = _normalize_username_candidate(raw_name, email)
    candidate = base
    while user_cls.query.filter_by(username=candidate).first() is not None:
        suffix = uuid.uuid4().hex[:6]
        candidate = f"{base[:41]}_{suffix}"
    return candidate


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
        db.String(36),
        primary_key=True,
        default=_generate_uuid_string,
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
        db.String(256),
        nullable=False,
        default=_generate_secure_fallback_hash,
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
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    mfa_pending_setup = db.Column(
        db.Boolean,
        default=False,
        nullable=False,
        index=True,
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
    first_name = db.Column(db.String(128))
    last_name = db.Column(db.String(128))
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
        overlaps="schema_events",
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
    def total_balance_decimal(self) -> Decimal:
        """Return exact Decimal sum of linked bank account balances."""
        total = Decimal("0")
        for account in self.bank_accounts.all():
            balance = getattr(account, "balance", None)
            if balance is None:
                continue
            try:
                total += Decimal(str(balance))
            except (TypeError, ValueError, ArithmeticError) as exc:
                logger.warning(
                    "Skipping invalid bank account balance for user_id=%s account_id=%s: %s",
                    self.id,
                    getattr(account, "id", None),
                    exc,
                )
        return total

    @property
    def total_balance(self) -> float:
        """
        Dynamically calculate the total balance across all linked bank accounts.
        Avoids swallowing unexpected DB/ORM errors while normalizing numeric values.
        """
        try:
            return float(self.total_balance_decimal)
        except (TypeError, ValueError, ArithmeticError) as exc:
            logger.warning(
                "Failed converting total_balance to float for user_id=%s: %s",
                self.id,
                exc,
            )
            return 0.0

    # -----------------------------------------------------------------------
    # Password Hashing & Auth Guards
    # -----------------------------------------------------------------------
    def has_password_configured(self) -> bool:
        """Return True if a non-empty password hash is stored on the account."""
        return bool(self.password_hash and str(self.password_hash).strip())

    def can_login_with_password(self) -> bool:
        """Guard helper for password-based sign-in flows."""
        return bool(
            not self.is_locked
            and self.is_approved
            and self.has_password_configured()
        )

    def set_password(self, password: str) -> None:
        """Hash the provided plaintext password and save it to the database."""
        if not password:
            raise ValueError("Password must not be empty")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored password hash."""
        if not self.has_password_configured():
            return False
        return cast(
            bool,
            check_password_hash(str(self.password_hash), password),
        )

    # -----------------------------------------------------------------------
    # OAuth Resolver
    # -----------------------------------------------------------------------
    @classmethod
    def get_or_create_from_oauth(
        cls,
        provider: Any,
        token_response: Any,
    ) -> User:
        """
        Resolve or create a User from an OAuth provider + token response.
        Requires a verified email when `email_verified` is present in profile,
        generates a collision-free username when creating a new user, and emits
        OAUTH_LOGIN_SUCCESS and SESSION_ESTABLISHED trace events.
        """
        from app.models.trace_events import TraceEvent
        from app.oauth.provider import OAuthProvider

        oauth_client = OAuthProvider(provider)
        profile = oauth_client.fetch_profile(token_response)

        raw_email = profile.get("email")
        email = raw_email.strip().lower() if isinstance(raw_email, str) else None
        sub = profile.get("sub")
        name = profile.get("name")

        if not email:
            raise ValueError("OAuth profile missing email")

        if "email_verified" in profile and profile.get("email_verified") is not True:
            raise ValueError("OAuth profile email is not verified")

        user = cls.query.filter(func.lower(cls.email) == email).first()

        if user is None:
            unique_username = _generate_unique_username(cls, name, email)
            user = cls(
                email=email,
                username=unique_username,
                password_hash=_generate_secure_fallback_hash(),
            )
            db.session.add(user)
            db.session.flush()

        provider_name = getattr(provider, "value", provider)

        def _emit(event_type: str, meta: dict[str, Any]) -> None:
            event = TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                user_id=user.id,
                email=user.email,
                meta=json.dumps(meta),
                detail=meta.get("detail"),
            )
            db.session.add(event)

        _emit(
            "OAUTH_LOGIN_SUCCESS",
            {"provider": provider_name, "sub": sub},
        )
        _emit(
            "SESSION_ESTABLISHED",
            {"provider": provider_name, "sub": sub},
        )

        db.session.commit()
        return user