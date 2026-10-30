# =============================================================================
# FILE: app/models/__init__.py
# DESCRIPTION: Central model registration. Import this package once at app
#              startup (e.g., in create_app after extensions init) so
#              SQLAlchemy registers all mapped classes.
# =============================================================================
"""Canonical model registration for SQLAlchemy.

Usage:
    # In create_app, after extensions are initialized:
    import app.models
"""

from ..extensions import db

# Core and authentication
from .access_token import AccessToken
from .mfa_code import MFACode
from .user import User

# Audit and timeline
from .audit_log import AuditLog, FinancialAuditLog
from .timeline_event import TimelineEvent
from .trace_events import TraceEvent

# Banking and Plaid
from .bank_account import BankAccount
from .bank_institution import BankInstitution
from .bank_statement import BankStatement
from .bank_transaction import BankTransaction
from .plaid_item import PlaidItem
from .vault_transaction import VaultTransaction

# General ledger
from .gl_account import GLAccount, GLAccountType
from .journal_entry import JournalEntry
from .ledger import LedgerEntry

# Credit and lending
from .borrower_card import BorrowerCard
from .credit_ledger import CreditLedger
from .lender import Lender
from .lender_risk import LenderRisk
from .loan import FinancialSnapshot, LoanApplication
from .loan_agreement import LoanAgreement
from .payment_log import PaymentLog
from .tradeline import Tradeline
from .underwriter import UnderwriterAgent

# Disputes, complaints, and fraud
from .complaint_log import ComplaintLog
from .dispute_log import DisputeLog
from .fraud_report import FraudReport

# Registry, schema, and system
from .registry import Registry
from .schema_event import SchemaEvent
from .system import SystemVersion

# Profiles and UI
from .subscriber_profile import SubscriberProfile
from .todo import Todo
from .transactions import Transaction
from .user_dashboard import UserDashboard

__all__ = [
    "db",
    "AccessToken",
    "AuditLog",
    "BankAccount",
    "BankInstitution",
    "BankStatement",
    "BankTransaction",
    "BorrowerCard",
    "ComplaintLog",
    "CreditLedger",
    "DisputeLog",
    "FinancialAuditLog",
    "FinancialSnapshot",
    "FraudReport",
    "GLAccount",
    "GLAccountType",
    "JournalEntry",
    "LedgerEntry",
    "Lender",
    "LenderRisk",
    "LoanAgreement",
    "LoanApplication",
    "MFACode",
    "PaymentLog",
    "PlaidItem",
    "Registry",
    "SchemaEvent",
    "SubscriberProfile",
    "SystemVersion",
    "TimelineEvent",
    "Todo",
    "TraceEvent",
    "Tradeline",
    "Transaction",
    "UnderwriterAgent",
    "User",
    "UserDashboard",
    "VaultTransaction",
]
