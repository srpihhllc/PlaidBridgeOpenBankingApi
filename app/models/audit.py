# =============================================================================
# FILE: app/models/audit.py
# PURPOSE: Compatibility shim so callers can import from app.models.audit
# =============================================================================

# Re-export the real model classes from audit_log.py so imports like:
#   from app.models.audit import AuditLog, FinancialAuditLog
# work regardless of the underlying filenames.

from app.models.audit_log import AuditLog  # noqa: F401
from app.models.audit_log import FinancialAuditLog  # noqa: F401

__all__ = ["AuditLog", "FinancialAuditLog"]
