# =============================================================================
# FILE: app/decorators/__init__.py
# DESCRIPTION: Unified role-based decorators and telemetry helpers
# =============================================================================

import logging

from app.utils.telemetry import log_identity_event

from .access import admin_required, require_admin, roles_required, super_admin_required

logger = logging.getLogger(__name__)

# NOTE:
# - admin_required, roles_required, super_admin_required are now defined
#   ONLY in access.py.
# - They are hybrid: JWT-aware with Flask-Login fallback.
# - This module simply re-exports them for convenience.

__all__ = [
    "require_admin",
    "admin_required",
    "roles_required",
    "super_admin_required",
    "log_identity_event",
]
