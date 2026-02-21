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
from app.models.access_token import AccessToken
from app.models.user import User
from app.models.ledger import LedgerEntry

# Audit models (use actual module names)
from app.models.audit import AuditLog, FinancialAuditLog
from app.models.timeline_event import TimelineEvent

# Dependent models (order chosen to reduce circular import risk)
from app.models.bank_account import BankAccount
from app.models.bank_institution import BankInstitution
from app.models.bank_statement import BankStatement
from app.models.bank_transaction import BankTransaction
from app.models.borrower_card import BorrowerCard
from app.models.complaint_log import ComplaintLog
from app.models.credit_ledger import CreditLedger
from app.models.dispute_log import DisputeLog
from app.models.fraud_report import FraudReport
from app.models.lender import Lender
from app.models.loan_agreement import LoanAgreement
from app.models.mfa_code import MFACode
from app.models.payment_log import PaymentLog
from app.models.plaid_item import PlaidItem
from app.models.registry import Registry
from app.models.schema_event import SchemaEvent
from app.models.subscriber_profile import SubscriberProfile
from app.models.system import SystemVersion
from app.models.todo import Todo
from app.models.trace_events import TraceEvent
from app.models.tradeline import Tradeline
from app.models.transactions import Transaction
from app.models.underwriter import UnderwriterAgent
from app.models.user_dashboard import UserDashboard
from app.models.vault_transaction import VaultTransaction

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
