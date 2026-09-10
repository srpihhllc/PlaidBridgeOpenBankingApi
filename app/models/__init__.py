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

# ---------------------------------------------------------------------------
# Audit / timeline models
# ---------------------------------------------------------------------------
from .audit_log import AuditLog, FinancialAuditLog
from .bank_account import BankAccount

# ---------------------------------------------------------------------------
# Dependent models (order chosen to reduce circular import risk)
# ---------------------------------------------------------------------------
from .bank_institution import BankInstitution
from .bank_statement import BankStatement
from .bank_transaction import BankTransaction
from .borrower_card import BorrowerCard
from .complaint_log import ComplaintLog
from .credit_ledger import CreditLedger
from .dispute_log import DisputeLog
from .fraud_report import FraudReport
from .ledger import LedgerEntry
from .lender import Lender
from .lender_risk import LenderRisk
from .loan_agreement import LoanAgreement
from .mfa_code import MFACode
from .payment_log import PaymentLog
from .plaid_item import PlaidItem
from .registry import Registry
from .schema_event import SchemaEvent
from .subscriber_profile import SubscriberProfile
from .system import SystemVersion
from .timeline_event import TimelineEvent
from .todo import Todo
from .trace_events import TraceEvent
from .tradeline import Tradeline
from .transactions import Transaction
from .underwriter import UnderwriterAgent
from .user import User
from .user_dashboard import UserDashboard
from .vault_transaction import VaultTransaction

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
    "LenderRisk",
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