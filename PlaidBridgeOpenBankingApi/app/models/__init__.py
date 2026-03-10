# =============================================================================
# FILE: app/models/__init__.py
# DESCRIPTION: Central model registration. Import this package once at app
#              startup (for example in create_app after extensions init)
#              so SQLAlchemy registers all mapped classes exactly once.
# =============================================================================
"""
Canonical model registration for SQLAlchemy.

Usage:
    # in create_app, after extensions initialization
    import app.models  # registers all mapped classes exactly once
"""

from app.extensions import db

# Base / independent models first
from .access_token import AccessToken
from .user import User
from .ledger import LedgerEntry

# Audit models (use actual module names)
from .audit import AuditLog, FinancialAuditLog
from .timeline_event import TimelineEvent

# Dependent models (order chosen to reduce circular import risk)
from .bank_account import BankAccount
from .bank_institution import BankInstitution
from .bank_statement import BankStatement
from .bank_transaction import BankTransaction
from .borrower_card import BorrowerCard
from .complaint_log import ComplaintLog
from .credit_ledger import CreditLedger
from .dispute_log import DisputeLog
from .fraud_report import FraudReport
from .lender import Lender
from .loan_agreement import LoanAgreement
from .mfa_code import MFACode
from .payment_log import PaymentLog
from .plaid_item import PlaidItem
from .registry import Registry
from .schema_event import SchemaEvent
from .subscriber_profile import SubscriberProfile
from .system import SystemVersion
from .todo import Todo
from .trace_events import TraceEvent
from .tradeline import Tradeline
from .transactions import Transaction
from .underwriter import UnderwriterAgent
from .user_dashboard import UserDashboard
from .vault_transaction import VaultTransaction

__all__ = [
    "db",
    "User",
    "Todo",
    "AccessToken",
    "MFACode",
    "SubscriberProfile",
    "UserDashboard",
    "BankInstitution",
    "PlaidItem",
    "BankAccount",
    "BankTransaction",
    "BankStatement",
    "Transaction",
    "VaultTransaction",
    "LoanAgreement",
    "Lender",
    "UnderwriterAgent",
    "BorrowerCard",
    "Tradeline",
    "CreditLedger",
    "PaymentLog",
    "DisputeLog",
    "ComplaintLog",
    "FraudReport",
    "Registry",
    "SchemaEvent",
    "TraceEvent",
    "SystemVersion",
    "TimelineEvent",
    "AuditLog",
    "FinancialAuditLog",
    "LedgerEntry",
]
