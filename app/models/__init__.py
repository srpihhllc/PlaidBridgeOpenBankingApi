# =============================================================================
# FILE: app/models/__init__.py
# DESCRIPTION: Central model registration. Import this package once at app
#              startup (e.g., in create_app after extensions init) so
#              SQLAlchemy registers all mapped classes exactly once.
# =============================================================================
"""
Canonical model registration for SQLAlchemy.

Usage:
    # in create_app, after extensions initialization
    import app.models  # registers all mapped classes exactly once
"""

from ..extensions import db

# ---------------------------------------------------------------------------
# Base / independent models (safe to import first)
# ---------------------------------------------------------------------------
from .access_token import AccessToken
from .user import User
from .ledger import LedgerEntry

# ---------------------------------------------------------------------------
# Audit / timeline models
# ---------------------------------------------------------------------------
from .audit_log import AuditLog, FinancialAuditLog
from .timeline_event import TimelineEvent

# ---------------------------------------------------------------------------
# Dependent models (order chosen to reduce circular import risk)
# ---------------------------------------------------------------------------
from .bank_institution import BankInstitution
from .plaid_item import PlaidItem
from .bank_account import BankAccount
from .bank_statement import BankStatement
from .bank_transaction import BankTransaction
from .vault_transaction import VaultTransaction

from .borrower_card import BorrowerCard
from .loan_agreement import LoanAgreement
from .lender import Lender
from .lender_risk import LenderRisk
from .underwriter import UnderwriterAgent

from .tradeline import Tradeline
from .credit_ledger import CreditLedger
from .payment_log import PaymentLog

from .dispute_log import DisputeLog
from .complaint_log import ComplaintLog
from .fraud_report import FraudReport

from .registry import Registry
from .schema_event import SchemaEvent
from .trace_events import TraceEvent
from .system import SystemVersion

from .subscriber_profile import SubscriberProfile
from .user_dashboard import UserDashboard
from .todo import Todo
from .transactions import Transaction
from .mfa_code import MFACode

# ---------------------------------------------------------------------------
# Explicit export surface for introspection and tooling
# ---------------------------------------------------------------------------
__all__ = [
    # Core
    "db",
    "User",
    "AccessToken",
    "LedgerEntry",

    # Auth / profile
    "MFACode",
    "SubscriberProfile",
    "UserDashboard",

    # Banking / Plaid
    "BankInstitution",
    "PlaidItem",
    "BankAccount",
    "BankTransaction",
    "BankStatement",
    "VaultTransaction",

    # Credit / lending
    "LoanAgreement",
    "Lender",
    "UnderwriterAgent",
    "BorrowerCard",
    "Tradeline",
    "CreditLedger",
    "PaymentLog",

    # Disputes / complaints / fraud
    "DisputeLog",
    "ComplaintLog",
    "FraudReport",

    # Registry / schema / system
    "Registry",
    "SchemaEvent",
    "TraceEvent",
    "SystemVersion",
    "TimelineEvent",
    "AuditLog",
    "FinancialAuditLog",

    # Misc / UI
    "Todo",
    "Transaction",
]